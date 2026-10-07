"""Pinned AI12 suggestion payload and a fixture-only v2 transport adapter."""

from __future__ import annotations

import json
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import UUID, uuid5

from jsonschema import Draft202012Validator, FormatChecker

from app.services.intelligence_contract import EVENT_NAMESPACE, content_hash

CONTRACT_DIR = Path(__file__).resolve().parents[1] / "contracts" / "intelligence-suggestions-v1"


@lru_cache
def suggestion_validator() -> Draft202012Validator:
    schema = json.loads((CONTRACT_DIR / "recommendation_generated.schema.json").read_bytes())
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


@lru_cache
def payload_validator() -> Draft202012Validator:
    return Draft202012Validator(
        suggestion_validator().schema["properties"]["payload"], format_checker=FormatChecker()
    )


@lru_cache
def candidate_fields() -> tuple[str, ...]:
    schema = json.loads((CONTRACT_DIR / "suggestion-candidate.v1.schema.json").read_bytes())
    return tuple(schema["required"])


def validate_suggestion(event: dict[str, Any]) -> None:
    if next(suggestion_validator().iter_errors(event), None) is not None:
        msg = "suggestion_schema_invalid"
        raise ValueError(msg)
    payload = event["payload"]
    validate_payload(payload)
    created = datetime.fromisoformat(payload["created_at"])
    if (
        datetime.fromisoformat(event["occurred_at"]) != created
        or datetime.fromisoformat(event["ingested_at"]) != created
        or event["correlation_id"] != payload["trace_id"]
        or event["event_id"]
        != str(uuid5(EVENT_NAMESPACE, "recommendation_generated:" + payload["recommendation_id"]))
    ):
        msg = "suggestion_event_binding"
        raise ValueError(msg)


def validate_payload(payload: dict[str, Any]) -> None:
    """Reproduce owner model/service relationships beyond generated JSON Schema."""
    candidate = {name: payload[name] for name in candidate_fields() if name != "candidate_id"}
    for field in ("source_as_of", "expires_at"):
        candidate[field] = (
            datetime.fromisoformat(candidate[field]).isoformat().replace("+00:00", "Z")
        )
    source = datetime.fromisoformat(payload["source_as_of"])
    created = datetime.fromisoformat(payload["created_at"])
    expires = datetime.fromisoformat(payload["expires_at"])
    uuids = [
        UUID(payload[field]) for field in ("trace_id", "answer_id", "recommendation_id", "store_id")
    ]
    if (
        any(
            str(value) != payload[field] or value.version not in {1, 2, 3, 4, 5}
            for value, field in zip(
                uuids, ("trace_id", "answer_id", "recommendation_id", "store_id"), strict=True
            )
        )
        or type(payload["requires_human_review"]) is not bool
        or payload["requires_human_review"] is not True
        or payload["candidate_id"] != "candidate-sha256-" + content_hash(candidate)
        or not 0 < (expires - source).total_seconds() <= 300
        or not source <= created < expires
        or payload["store_id"] != payload["selling_location_id"]
        or payload["recommendation_id"] != str(uuid5(uuids[0], payload["candidate_id"]))
        or payload["answer_id"] != str(uuid5(uuids[0], "answer"))
        or len(set(payload["evidence_refs"])) != len(payload["evidence_refs"])
        or len(set(payload["model_release_refs"])) != len(payload["model_release_refs"])
    ):
        msg = "suggestion_identity_scope_or_expiry"
        raise ValueError(msg)
