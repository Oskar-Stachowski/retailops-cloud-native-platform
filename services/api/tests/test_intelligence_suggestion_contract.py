"""Reject suggestion identity/scope/lifetime poison before any SQL or acknowledgment."""

import copy
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from intelligence_suggestion_fixture import (
    enable_suggestions as enable_suggestions,
    rebind,
    suggestion_event,
)

from app.main import app
from app.services.intelligence_contract import TOPIC, validate_event
from app.services.intelligence_suggestion_contract import CONTRACT_DIR
from app.services.intelligence_suggestion_reader import read_suggestion
from app.services.realtime_consumer import InvalidRealtimeEventError


def test_frozen_owner_fixture_and_equivalent_utc_serialization():
    frozen = json.loads((CONTRACT_DIR / "recommendation_generated.fixture.json").read_bytes())
    validate_event(frozen, transport_topic=TOPIC)
    event = suggestion_event()
    for key in ("source_as_of", "created_at", "expires_at"):
        event["payload"][key] = event["payload"][key].replace("Z", "+00:00")
    rebind(event)
    validate_event(event, transport_topic=TOPIC)


def test_fixture_transport_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("RETAILOPS_ENABLE_SUGGESTION_FIXTURE_TRANSPORT", raising=False)
    with pytest.raises(InvalidRealtimeEventError):
        validate_event(suggestion_event(), transport_topic=TOPIC)


@pytest.mark.parametrize(
    "field,value",
    [
        ("requires_human_review", False),
        ("requires_human_review", 1),
        ("status", "accepted"),
        ("freshness_status", "stale"),
        ("origin", "other"),
        ("recommendation_type", "execute_order"),
        ("evidence_refs", []),
        ("evidence_refs", ["same", "same"]),
        ("model_release_refs", ["same", "same"]),
        ("candidate_id", "candidate-sha256-" + "0" * 64),
        ("store_id", str(uuid4())),
        ("recommendation_id", str(uuid4())),
        ("answer_id", str(uuid4())),
        ("trace_id", str(uuid4())),
        ("source_as_of", "2026-10-04T18:00:00+01:00"),
        ("extra", "operational_command"),
        ("priority", "critical"),
    ],
)
def test_payload_poison_rejected(field, value):
    event = suggestion_event()
    event["payload"][field] = value
    with pytest.raises(InvalidRealtimeEventError, match="intelligence_v2_contract_invalid"):
        validate_event(event, transport_topic=TOPIC)


@pytest.mark.parametrize(
    "variant", ["long", "zero", "before_source", "at_expiry", "uppercase_uuid"]
)
def test_cross_field_lifetime_and_uuid_rules(variant):
    event = suggestion_event()
    payload = event["payload"]
    source = datetime.fromisoformat(payload["source_as_of"])
    if variant in {"long", "zero"}:
        payload["expires_at"] = (
            source + timedelta(seconds=301 if variant == "long" else 0)
        ).isoformat()
    elif variant == "before_source":
        payload["created_at"] = (source - timedelta(seconds=1)).isoformat()
    elif variant == "at_expiry":
        payload["created_at"] = payload["expires_at"]
    else:
        payload["trace_id"] = payload["trace_id"].upper()
    rebind(event)
    with pytest.raises(InvalidRealtimeEventError):
        validate_event(event, transport_topic=TOPIC)


@pytest.mark.parametrize(
    "field,value",
    [
        ("event_id", str(uuid4())),
        ("correlation_id", str(uuid4())),
        ("schema_version", "3.0"),
        ("source", "other"),
        ("topic", "other"),
        ("occurred_at", "2020-01-01T00:00:00Z"),
        ("ingested_at", "2020-01-01T00:00:00Z"),
    ],
)
def test_envelope_binding_and_transport_topic(field, value):
    event = suggestion_event()
    event[field] = value
    with pytest.raises(InvalidRealtimeEventError):
        validate_event(event, transport_topic=TOPIC)
    with pytest.raises(InvalidRealtimeEventError):
        validate_event(suggestion_event(), transport_topic="other")


def test_read_time_expiry_and_future_never_mutate_original_payload():
    event = suggestion_event()
    payload = event["payload"]
    now = datetime.fromisoformat(payload["expires_at"])
    from app.services.intelligence_contract import content_hash

    row = {
        "recommendation_id": payload["recommendation_id"],
        "payload": payload,
        "payload_sha256": content_hash(payload),
        "received_at": now,
    }
    before = copy.deepcopy(payload)
    assert read_suggestion(row, now=now)["freshness"]["reason"] == "suggestion_expired"
    assert (
        read_suggestion(row, now=now - timedelta(seconds=300))["freshness"]["status"] == "unknown"
    )
    assert read_suggestion(row, now=now - timedelta(seconds=1))["freshness"]["status"] == "current"
    assert read_suggestion(row, now=now)["execution_authorized"] is False
    assert payload == before
    row["payload_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="suggestion_projection_corrupt"):
        read_suggestion(row, now=now)


def test_openapi_exact_owner_schema_and_no_write_routes():
    owner = json.loads((CONTRACT_DIR / "suggestion.v1.schema.json").read_bytes())
    with TestClient(app) as client:
        schema = client.get("/openapi.json").json()
        assert schema["components"]["schemas"]["AI12_PersistedSuggestion"] == owner
        paths = {
            key: value
            for key, value in schema["paths"].items()
            if key.startswith("/intelligence/v2/recommendations")
        }
        assert len(paths) == 2 and all(set(value) == {"get"} for value in paths.values())
        assert client.post("/intelligence/v2/recommendations").status_code == 405
