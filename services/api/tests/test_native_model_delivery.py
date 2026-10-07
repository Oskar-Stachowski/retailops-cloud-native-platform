"""A transport receipt must bind every native identity and original SQL ACK position."""

import copy
import hashlib
import json
from types import SimpleNamespace

import native_model_delivery
import pytest
from app.services.intelligence_checkpoint import TransportRecord
from app.services.intelligence_contract import CONTRACT_DIR, TOPIC
from native_model_delivery import validate_original_receipts


@pytest.fixture(params=["stockout_risk_scored", "anomaly_detected"])
def original(request):
    kind = request.param
    event = json.loads((CONTRACT_DIR / (kind + ".fixture.json")).read_bytes())
    raw = json.dumps(event, sort_keys=True, separators=(",", ":")).encode()
    acceptance = dict(
        commit="a" * 40,
        workflow_run_id=123,
        native_outbox_census_id="native-model-outbox-sha256-" + "b" * 64,
    )
    report = dict(
        status="passed",
        original_AI_database_publisher_attested=True,
        producer_commit=acceptance["commit"],
        workflow_run_id=123,
        census_id=acceptance["native_outbox_census_id"],
        model_kind=kind,
        delivered=1,
        receipts=[
            dict(
                event_id=event["event_id"],
                event_sha256=hashlib.sha256(raw).hexdigest(),
                wire_sha256="c" * 64,
                partition=0,
                offset=7,
            )
        ],
    )
    return report, acceptance, [(event, raw)], kind


def test_original_wire_bytes_are_bound_to_exact_sql_ack_positions(original):
    report, acceptance, events, kind = original
    assert validate_original_receipts(report, acceptance, events, kind) == {
        (0, 7): "c" * 64
    }


@pytest.mark.parametrize(
    "change",
    [
        "false_attestation",
        "commit",
        "run",
        "census",
        "missing",
        "event",
        "digest",
        "offset",
        "wire_digest",
    ],
)
def test_unbound_or_incomplete_original_publisher_receipt_refused(original, change):
    report, acceptance, events, kind = copy.deepcopy(original)
    if change == "false_attestation":
        report["original_AI_database_publisher_attested"] = False
    elif change == "commit":
        report["producer_commit"] = "d" * 40
    elif change == "run":
        report["workflow_run_id"] = 456
    elif change == "census":
        report["census_id"] = "foreign-census"
    elif change == "missing":
        report["receipts"] = []
    elif change == "event":
        report["receipts"][0]["event_id"] = "foreign-event"
    elif change == "digest":
        report["receipts"][0]["event_sha256"] = "f" * 64
    elif change == "offset":
        report["receipts"][0]["offset"] = -1
    else:
        report["receipts"][0]["wire_sha256"] = "invalid"
    with pytest.raises(ValueError):
        validate_original_receipts(report, acceptance, events, kind)


@pytest.mark.parametrize(
    "change", [None, "value", "key", "headers", "timestamp", "offset"]
)
def test_original_ACK_read_binds_value_and_complete_SQL_transport_without_commits(
    monkeypatch, change
):
    raw = b'{"original":"native-publication"}'
    original = TransportRecord(
        0, 7, raw, b"native-grain", (("trace", b"original"),), 123
    )
    values = dict(
        value=raw,
        key=b"native-grain",
        headers=[("trace", b"original")],
        timestamp=123,
        offset=7,
    )
    if change == "value":
        values["value"] = b'{"substituted":"native-publication"}'
    elif change == "key":
        values["key"] = b"foreign-grain"
    elif change == "headers":
        values["headers"] = [("trace", b"changed")]
    elif change == "timestamp":
        values["timestamp"] = 456
    elif change == "offset":
        values["offset"] = 8
    message = SimpleNamespace(
        value=lambda: values["value"],
        key=lambda: values["key"],
        headers=lambda: values["headers"],
        timestamp=lambda: (0, values["timestamp"]),
        topic=lambda: TOPIC,
        partition=lambda: 0,
        offset=lambda: values["offset"],
        error=lambda: None,
    )
    state = {}

    def reader(config):
        assert config["enable.auto.commit"] is False
        assert config["enable.auto.offset.store"] is False
        return SimpleNamespace(
            assign=lambda partitions: state.update(
                assigned=[
                    (part.topic, part.partition, part.offset) for part in partitions
                ]
            ),
            poll=lambda _: message,
            close=lambda: state.update(closed=True),
        )

    monkeypatch.setattr(native_model_delivery, "Consumer", reader)
    positions = {(0, 7): hashlib.sha256(raw).hexdigest()}
    receipts = [(0, 7, "projected", original.fingerprint())]
    if change is None:
        native_model_delivery.verify_original_consumed_records(
            "owned-loopback:9092", positions, receipts
        )
    else:
        with pytest.raises(ValueError):
            native_model_delivery.verify_original_consumed_records(
                "owned-loopback:9092", positions, receipts
            )
    assert state == dict(assigned=[(TOPIC, 0, 7)], closed=True)
