"""Real Source SQL and TLS/SCRAM prefix capture preserves a resend absent from publisher receipts."""

import json
import os
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
        rt.passed(
            "complete_source_capture_crash_retry_correction_and_immutable_later_replay"
        )
    finally:
        reader.close()
