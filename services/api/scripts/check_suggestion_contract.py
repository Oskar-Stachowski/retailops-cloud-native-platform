"""Verify unchanged owner bytes, generated envelope and explicit fixture qualification."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from app.services.intelligence_contract import TOPIC, validate_event
from app.services.intelligence_suggestion_contract import CONTRACT_DIR, suggestion_validator


def check(owner_root: Path) -> None:
    pin = json.loads((CONTRACT_DIR / "owner.json").read_bytes())
    if (
        pin["event_adapter_status"] != "fixture_only"
        or pin["real_assistant_outbox_publication"] is not False
        or pin["model_quality_qualification"] is not False
    ):
        msg = "suggestion_adapter_qualification_changed"
        raise ValueError(msg)
    for relative, expected in pin["upstream_sha256"].items():
        if hashlib.sha256((owner_root / relative).read_bytes()).hexdigest() != expected:
            msg = "suggestion_owner_pin_changed"
            raise ValueError(msg)
    for name, relative in pin["upstream_paths"].items():
        if (CONTRACT_DIR / name).read_bytes() != (owner_root / relative).read_bytes():
            msg = "suggestion_owner_schema_changed"
            raise ValueError(msg)
    for name, expected in pin["local_sha256"].items():
        if hashlib.sha256((CONTRACT_DIR / name).read_bytes()).hexdigest() != expected:
            msg = "suggestion_local_contract_changed"
            raise ValueError(msg)
    if suggestion_validator().schema["properties"]["payload"] != json.loads(
        (CONTRACT_DIR / "suggestion.v1.schema.json").read_bytes()
    ):
        msg = "suggestion_envelope_payload_changed"
        raise ValueError(msg)
    validate_event(
        json.loads((CONTRACT_DIR / "recommendation_generated.fixture.json").read_bytes()),
        transport_topic=TOPIC,
    )
    sys.stdout.write(
        json.dumps(
            {
                "status": "passed",
                "owner_commit": pin["commit"],
                "event_adapter_status": "fixture_only",
            }
        )
        + "\n"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--owner-root", type=Path, required=True)
    check(parser.parse_args().owner_root)
