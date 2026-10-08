"""Explicitly invented suggestion fixture, never an assistant/model acceptance result."""

import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4, uuid5

import pytest

from app.services.intelligence_contract import EVENT_NAMESPACE, content_hash
from app.services.intelligence_suggestion_contract import CONTRACT_DIR, candidate_fields

LOCATION = "12345678-1234-4234-8234-123456789012"


@pytest.fixture(autouse=True)
def enable_suggestions(monkeypatch):
    monkeypatch.setenv("RETAILOPS_ENABLE_SUGGESTION_FIXTURE_TRANSPORT", "1")


def rebind(event):
    payload = event["payload"]
    value = {key: payload[key] for key in candidate_fields() if key != "candidate_id"}
    for key in ("source_as_of", "expires_at"):
        value[key] = datetime.fromisoformat(value[key]).isoformat().replace("+00:00", "Z")
    payload["candidate_id"] = "candidate-sha256-" + content_hash(value)
    payload["recommendation_id"] = str(uuid5(UUID(payload["trace_id"]), payload["candidate_id"]))
    payload["answer_id"] = str(uuid5(UUID(payload["trace_id"]), "answer"))
    event.update(
        event_id=str(
            uuid5(EVENT_NAMESPACE, "recommendation_generated:" + payload["recommendation_id"])
        ),
        correlation_id=payload["trace_id"],
        occurred_at=payload["created_at"],
        ingested_at=payload["created_at"],
    )
    return event


def suggestion_event(*, source=None, **updates):
    event = json.loads((CONTRACT_DIR / "recommendation_generated.fixture.json").read_bytes())
    source = source or datetime.now(UTC) - timedelta(seconds=10)
    event["payload"].update(
        source_as_of=source.isoformat().replace("+00:00", "Z"),
        created_at=(source + timedelta(seconds=1)).isoformat().replace("+00:00", "Z"),
        expires_at=(source + timedelta(seconds=300)).isoformat().replace("+00:00", "Z"),
        trace_id=str(uuid4()),
        **updates,
    )
    return rebind(event)


def access_document(digest):
    return {
        "version": "retailops-suggestion-access-1.0",
        "principals": [
            {
                "principal_id": "fixture-suggestion-reader",
                "credential_sha256": digest,
                "capabilities": ["suggestion:read"],
                "product_ids": ["fixture-product"],
                "selling_location_ids": [LOCATION],
                "channels": ["store"],
                "policy_sha256s": ["b" * 64],
                "agent_config_versions": ["fixture-agent-v1"],
                "model_release_refs": ["fixture:approved-model-release"],
            }
        ],
    }
