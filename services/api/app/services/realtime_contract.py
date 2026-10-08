"""Executable legacy v1 event contract shared by the consumer and API image."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

CONTRACT_DIR = Path(__file__).resolve().parents[1] / "contracts"
CONTRACT_PATH = CONTRACT_DIR / "retailops-realtime-events.v1.contract.json"


@lru_cache(maxsize=1)
def event_contract() -> dict[str, Any]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def event_validator() -> Draft202012Validator:
    schema_path = CONTRACT_DIR / event_contract()["schema_file"]
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


EVENT_TOPICS: dict[str, str] = event_contract()["event_type_topics"]
SUPPORTED_EVENT_TYPES = frozenset(EVENT_TOPICS)
REQUIRED_EVENT_FIELDS = tuple(event_contract()["envelope"]["required_fields"])


def validate_event(event: dict[str, Any], *, transport_topic: str | None = None) -> None:
    """Validate the declared route, transport route and every legacy payload."""
    if not isinstance(event, dict):
        msg = "Event envelope must be a JSON object."
        raise TypeError(msg)

    missing = [name for name in REQUIRED_EVENT_FIELDS if name not in event]
    if missing:
        msg = f"Missing required event fields: {', '.join(missing)}"
        raise ValueError(msg)

    event_type = event.get("event_type")
    if event_type not in EVENT_TOPICS:
        msg = "Unsupported event type."
        raise ValueError(msg)

    version = event.get("schema_version")
    if version not in event_contract()["supported_schema_versions"]:
        msg = "Unsupported event schema version."
        raise ValueError(msg)

    expected_topic = EVENT_TOPICS[event_type]
    if event.get("topic") != expected_topic:
        msg = f"Event topic mismatch for {event_type}: expected {expected_topic}"
        raise ValueError(msg)
    if transport_topic is not None and transport_topic != expected_topic:
        msg = f"Transport topic mismatch for {event_type}: expected {expected_topic}"
        raise ValueError(msg)

    error = next(event_validator().iter_errors(event), None)
    if error is not None:
        path = ".".join(str(part) for part in error.absolute_path) or "envelope"
        # jsonschema messages (notably anyOf) can contain the complete payload.
        # Keep the reason safe for quarantine summaries and diagnostic logs.
        msg = f"Invalid realtime event at {path}: failed schema rule {error.validator}"
        raise ValueError(msg)
