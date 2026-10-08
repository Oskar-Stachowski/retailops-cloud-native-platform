"""Independent validation of native model schemas; these inputs are mechanics fixtures."""

import copy
import json
from datetime import UTC, datetime, timedelta

import pytest

from app.services.intelligence_contract import CONTRACT_DIR, TOPIC, content_hash, validate_event
from app.services.intelligence_model_contract import model_partition_key
from app.services.intelligence_model_reader import read_model_item
from app.services.realtime_consumer import InvalidRealtimeEventError


@pytest.fixture(params=["anomaly_detected", "stockout_risk_scored"])
def model_event(request):
    return json.loads((CONTRACT_DIR / (request.param + ".fixture.json")).read_bytes())


def test_native_payload_read_preserves_publication_and_recomputes_only_read_freshness(model_event):
    validate_event(model_event, transport_topic=TOPIC)
    item = model_event["payload"]
    identity = item.get("anomaly_id", item.get("risk_id"))
    now = datetime.fromisoformat(item["generated_at"]) + timedelta(days=8)
    result = read_model_item({
        "event_type": model_event["event_type"], "result_id": identity, "payload": item,
        "payload_sha256": content_hash(item), "received_at": now,
    }, now=now)
    assert result["result"] == item
    assert result["result_id"] == identity
    assert result["source"] == "retailops-ai"
    assert result["freshness"]["status"] == "stale"
    assert len(model_partition_key(model_event)) == 64


@pytest.mark.parametrize("change", ["major", "minor", "topic", "identity", "grain", "time", "run", "unknown", "status"])
def test_forged_native_envelope_is_rejected(model_event, change):
    event = copy.deepcopy(model_event)
    if change in {"major", "minor"}:
        event["schema_version"] = "3.0" if change == "major" else "2.1"
    elif change == "topic":
        event["topic"] = "retailops.events.v1"
    elif change == "identity":
        event["event_id"] = "11111111-1111-4111-8111-111111111111"
    elif change == "grain":
        event["payload"]["product_id"] = "foreign-product"
    elif change == "time":
        event["occurred_at"] = "2026-10-06T00:00:00Z"
    elif change == "run":
        event["correlation_id"] = "run-" + "f" * 32
    elif change == "unknown":
        event["payload"]["demo_admin"] = True
    elif event["event_type"] == "anomaly_detected":
        event["payload"]["status"] = "insufficient_data"
        event["payload"]["alert"] = True
    else:
        event["payload"]["status"] = "insufficient_data"
        event["payload"]["probability"] = 0.1
    with pytest.raises(InvalidRealtimeEventError):
        validate_event(event, transport_topic=TOPIC)


def test_stored_payload_corruption_is_rejected_before_http_response(model_event):
    item = model_event["payload"]
    with pytest.raises(ValueError, match="stored_binding"):
        read_model_item({
            "event_type": model_event["event_type"], "result_id": item.get("anomaly_id", item.get("risk_id")),
            "payload": item, "payload_sha256": "f" * 64,
            "received_at": datetime.now(UTC),
        }, now=datetime.now(UTC))
