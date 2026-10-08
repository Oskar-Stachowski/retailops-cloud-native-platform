"""Shared ML payload and v1/v2 isolation; the example is a mechanics fixture."""

import copy
import hashlib
import json
from unittest.mock import Mock

import pytest

from app.main import app
from app.services.intelligence_contract import CONTRACT_DIR, TOPIC, validate_event
from app.services.intelligence_contract import content_hash
from app.services.realtime_consumer import InvalidRealtimeEventError
from app.services.realtime_contract import validate_event as validate_legacy
from app.services.realtime_quarantine import replay_quarantined_message


@pytest.fixture
def forecast_event():
    return json.loads((CONTRACT_DIR / "forecast_generated.fixture.json").read_bytes())


def test_pinned_contract_hashes_and_openapi_payload_match():
    upstream = json.loads((CONTRACT_DIR / "upstream.json").read_bytes())
    for name, digest in upstream["sha256"].items():
        assert hashlib.sha256((CONTRACT_DIR / name).read_bytes()).hexdigest() == digest
    schema = app.openapi()
    definitions = json.loads((CONTRACT_DIR / "forecast_generated.schema.json").read_bytes())["$defs"]
    for name, document in definitions.items():
        expected = json.loads(json.dumps(document).replace("#/$defs/", "#/components/schemas/AI10_"))
        assert schema["components"]["schemas"]["AI10_" + name] == expected
    assert schema["paths"]["/intelligence/v2/forecasts"]["get"]["security"] == [
        {"IntelligenceCredential": []}
    ]


def test_forecast_does_not_enter_the_legacy_noop_consumer(forecast_event):
    validate_event(forecast_event, transport_topic=TOPIC)
    assert forecast_event["payload"]["model_name"].endswith("-mechanics")
    with pytest.raises(ValueError):
        validate_legacy(forecast_event, transport_topic=TOPIC)
    with pytest.raises(InvalidRealtimeEventError):
        validate_event(forecast_event, transport_topic="retailops.intelligence.v1")


@pytest.mark.parametrize("change", [
    "major", "minor", "topic", "missing_topic", "type", "empty_payload", "id", "grain",
    "functional", "interval", "freshness", "unknown_field", "numeric_boolean", "timestamp",
])
def test_bad_or_unsupported_events_are_rejected(forecast_event, change):
    event = copy.deepcopy(forecast_event)
    if change in {"major", "minor"}:
        event["schema_version"] = "3.0" if change == "major" else "2.1"
    elif change == "topic":
        event["topic"] = "retailops.intelligence.v1"
    elif change == "missing_topic":
        del event["topic"]
    elif change == "type":
        event["event_type"] = "stockout_risk_scored"
    elif change == "empty_payload":
        event["payload"] = {}
    elif change == "id":
        event["event_id"] = "11111111-1111-4111-8111-111111111111"
    elif change == "grain":
        event["payload"]["horizon_days"] = 2
    elif change == "functional":
        event["payload"]["prediction"]["candidate"]["median"] = 11.0
    elif change == "interval":
        for functional in ("candidate", "baseline"):
            event["payload"]["prediction"][functional]["interval"]["upper"] = 9.0
    elif change == "freshness":
        event["payload"]["freshness"]["status"] = "current"
    elif change == "unknown_field":
        event["payload"]["probability"] = 0.4
    elif change == "numeric_boolean":
        event["payload"]["prediction"]["metadata"]["exact_reference_median"] = 1
    else:
        event["occurred_at"] = "2026-10-02T00:00:00+02:00"
    with pytest.raises(InvalidRealtimeEventError, match="intelligence_v2_contract_invalid"):
        validate_event(event, transport_topic=TOPIC)


def test_reviewed_v2_replay_preserves_result_identity_and_grain_key(forecast_event):
    repository, producer = Mock(), Mock()
    repository.get.return_value = {"topic": TOPIC}
    repository.prepare_replay.return_value = {"payload": {"replay": {}}}
    producer.flush.return_value = 0

    def produce(topic, **kwargs):
        assert topic == TOPIC
        kwargs["on_delivery"](None, Mock(partition=lambda: 2, offset=lambda: 17))

    producer.produce.side_effect = produce
    result = replay_quarantined_message(
        "quarantine-fixture", event=forecast_event, operator="fixture-operator",
        bootstrap_servers="fixture-broker:9092", repository=repository, producer=producer,
    )
    sent = producer.produce.call_args.kwargs
    assert json.loads(sent["value"]) == forecast_event
    assert sent["key"] == content_hash({name: forecast_event["payload"][name] for name in (
        "product_id", "selling_location_id", "channel",
    )}).encode()
    assert result["event_id"] == forecast_event["event_id"]
    repository.confirm_replay.assert_called_once_with("quarantine-fixture", partition=2, offset=17)
