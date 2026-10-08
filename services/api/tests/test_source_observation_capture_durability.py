"""Real Source SQL and TLS/SCRAM prefix capture preserves a resend absent from publisher receipts."""

import json
import os
import subprocess
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from app.services.source_observation_broker import build_producer
from app.services.source_observation_capture import CaptureReader, capture_source
from app.services.source_observation_outbox import (
    ObservationError,
    ObservationOutbox,
    ObservationPublisher,
)
from pydantic import SecretStr
from source_observation_runtime import capture_runtime  # noqa: F401 - pytest fixture
from test_source_observation_outbox import fact

pytestmark = pytest.mark.integration_broker


def test_actual_source_capture_binds_complete_prefix_retry_correction_and_later_replay(
    capture_runtime,  # noqa: F811 - pytest resolves imported module fixture
    tmp_path,
):
    rt = capture_runtime
    producer, topology = build_producer(rt.config)
    stream, partitions = topology.inspect()
    database = rt.engine.url.render_as_string(hide_password=False).replace(
        "postgresql+psycopg://", "postgresql://"
    )
    outbox = ObservationOutbox(database)
    outbox.bind(stream, partitions)
    first = fact()
    outbox.append(stream, partitions, first)

    def interrupt_after_actual_delivery():
        raise ObservationError("acceptance_interrupted_after_real_broker_delivery")

    with pytest.raises(ObservationError, match="publication_unavailable"):
        ObservationPublisher(
            outbox, producer, topology, after_delivery=interrupt_after_actual_delivery
        ).once()
    reader_config = rt.config.model_copy(
        update={
            "username": SecretStr("reader"),
            "password": SecretStr(rt.passwords["reader"]),
        }
    )
    reader = CaptureReader(reader_config)
    output = tmp_path / "capture.json"
    try:
        with pytest.raises(ObservationError, match="capture_unavailable"):
            capture_source(outbox, reader, output)
        assert not output.exists()
        assert ObservationPublisher(outbox, producer, topology).once()
        correction = first.model_copy(
            update={
                "id": str(uuid4()),
                "version": 2,
                "observed_units": 4,
                "available_at": first.available_at + timedelta(days=1),
            }
        )
        outbox.append(stream, partitions, correction)
        assert ObservationPublisher(outbox, producer, topology).once()
        report = capture_source(outbox, reader, output)
        original_bytes = output.read_bytes()
        captured = json.loads(original_bytes)
        assert report["status"] == "passed"
        assert report["rows"] == 2 and report["receipts"] == 3
        assert len(report["boundaries"]) == partitions == 3
        assert sum(report["boundaries"]) == 3
        assert [receipt["offset"] for receipt in captured["receipts"]] == [0, 1, 2]
        assert (
            captured["receipts"][0]["event_id"] == captured["receipts"][1]["event_id"]
        )
        assert output.stat().st_mode & 0o777 == 0o600
        with pytest.raises(FileExistsError):
            capture_source(outbox, reader, output)
        assert output.read_bytes() == original_bytes
        later = correction.model_copy(
            update={
                "id": str(uuid4()),
                "version": 3,
                "observed_units": 7,
                "available_at": correction.available_at + timedelta(days=1),
            }
        )
        outbox.append(stream, partitions, later)
        assert ObservationPublisher(outbox, producer, topology).once()
        boundaries = reader.boundaries(partitions)
        replay = reader.prefix(boundaries)
        assert len(replay) == 4 and sum(boundaries) == 4
        assert output.read_bytes() == original_bytes
        receipt_path = os.getenv("SOURCE_OBSERVATION_CAPTURE_REPORT")
        if receipt_path:
            target = Path(receipt_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.with_name("source-observation-capture.json").write_bytes(
                original_bytes
            )
            target.with_name("source-observation-capture-replay.json").write_text(
                json.dumps(
                    {
                        "stream": stream.model_dump(mode="json"),
                        "records": [
                            {
                                "partition": record.partition,
                                "offset": record.offset,
                                "envelope": json.loads(record.raw),
                            }
                            for record in replay
                        ],
                    }
                )
            )
            target.write_text(
                json.dumps(
                    {
                        **report,
                        "actual_source_sql_tls_scram_broker": True,
                        "later_replay_receipts": len(replay),
                        "model_qualification": False,
                        "acceptance_inputs": "explicit generated observation fixtures",
                        "no_broker_commits_or_offset_stores_by_capture_reader": True,
                    },
                    indent=2,
                )
                + "\n"
            )
            # Dedicated AI10 handoff keeps this original broker and Source SQL
            # alive while the independently installed AI receiver persists/ACKs it.
            receiver = os.getenv("AI10_SOURCE_CAPTURE_RECEIVER_PYTHON")
            receiver_script = os.getenv("AI10_SOURCE_CAPTURE_RECEIVER_SCRIPT")
            if receiver or receiver_script:
                assert receiver and receiver_script
                control = tmp_path / "ai-receiver-broker.json"
                control.write_text(
                    json.dumps(
                        {
                            "source_authority_id": reader_config.source_authority_id,
                            "bootstrap_servers": reader_config.bootstrap_servers,
                            "security_protocol": reader_config.security_protocol,
                            "sasl_mechanism": reader_config.sasl_mechanism,
                            "username": reader_config.username.get_secret_value(),
                            "password": reader_config.password.get_secret_value(),
                            "ca_file": reader_config.ca_file,
                        }
                    )
                )
                control.chmod(0o600)
                sql_report = target.with_name("independent-ai-sql-handoff.json")
                try:
                    subprocess.run(
                        [
                            receiver,
                            receiver_script,
                            "--broker-config",
                            str(control),
                            "--capture",
                            str(target.with_name("source-observation-capture.json")),
                            "--replay",
                            str(
                                target.with_name(
                                    "source-observation-capture-replay.json"
                                )
                            ),
                            "--source-root",
                            str(Path(__file__).resolve().parents[3]),
                            "--report",
                            str(sql_report),
                        ],
                        check=True,
                        timeout=300,
                    )
                    received = json.loads(sql_report.read_text())
                    assert received["status"] == "passed"
                    assert received["actual_AI_SQL_or_ACK"] is True
                    assert received["capture_id"] == report["capture_id"]
                    assert received["full_equals_capture_overlap"] is True
                    assert received["quantity_before_correction"] == 4
                    assert received["quantity_after_correction"] == 7
                    assert received["final_facts"] == 3
                    assert received["final_receipts"] == 4
                    assert received["actual_original_broker_overlap_records"] == 3
                finally:
                    control.unlink()
        rt.passed(
            "complete_source_capture_crash_retry_correction_and_immutable_later_replay"
        )
    finally:
        reader.close()
