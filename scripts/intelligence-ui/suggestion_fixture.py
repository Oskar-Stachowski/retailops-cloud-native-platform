"""Invented suggestion fixture for the owned disposable PostgreSQL/UI drill only."""

# ruff: noqa: INP001, PLC0415

from __future__ import annotations

import hashlib
import json
import os
import secrets
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def fixtures() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    sys.path[:0] = [str(ROOT / "services/api"), str(ROOT / "services/api/tests")]
    from intelligence_suggestion_fixture import suggestion_event

    products = [f"suggestion-product-{index:02}" for index in range(10)]
    source = datetime.now(UTC) - timedelta(seconds=10)
    current = [
        suggestion_event(
            source=source,
            product_id=products[index % 10],
            action=f"Fixture review {index:02}: ask an operator to inspect source freshness.",
            summary=f"Mechanics fixture {index:02}: human review only.",
            evidence_refs=[
                f"fixture:operations:review-{index:02}",
                "<script>window.fixtureLeak=1</script>",
            ],
            model_release_refs=["fixture:approved-model-release"],
        )
        for index in range(70)
    ]
    history = [
        suggestion_event(source=source - timedelta(seconds=400), product_id=products[0]),
        suggestion_event(source=source + timedelta(seconds=600), product_id=products[0]),
        suggestion_event(source=source, product_id="foreign-suggestion-product"),
        suggestion_event(
            source=source, product_id=products[0], model_release_refs=["foreign:model"]
        ),
    ]
    return current, history


def seed(control: Path) -> dict[str, Any]:
    current, history = fixtures()
    from intelligence_suggestion_fixture import access_document

    from app.repositories.intelligence_repository import IntelligenceRepository
    from app.services.intelligence_contract import TOPIC, validate_event

    repository = IntelligenceRepository()
    for event in [*current, *history]:
        validate_event(event, transport_topic=TOPIC)
        repository.project(event)
    current.sort(
        key=lambda event: (event["payload"]["created_at"], event["payload"]["recommendation_id"]),
        reverse=True,
    )
    secret = secrets.token_urlsafe(48)
    access = access_document(hashlib.sha256(secret.encode()).hexdigest())
    access["principals"][0]["product_ids"] = [
        f"suggestion-product-{index:02}" for index in range(10)
    ]
    for name, value in (
        ("suggestion-credential", secret),
        ("suggestion-access.json", json.dumps(access)),
        ("suggestion-expected.json", json.dumps([event["payload"] for event in current])),
        ("suggestion-history.json", json.dumps([event["payload"] for event in history[:2]])),
    ):
        path = control / name
        path.write_text(value)
        path.chmod(0o600)
    return {
        "current_rows": 70,
        "history_rows": 72,
        "foreign_rows": 2,
        "assistant_emitter": False,
        "model_qualification": False,
    }


def short_lived() -> dict[str, Any]:
    if os.environ.get("RETAILOPS_UI_DISPOSABLE_DB") != "1":
        msg = "owned_disposable_database_required"
        raise RuntimeError(msg)
    sys.path[:0] = [str(ROOT / "services/api"), str(ROOT / "services/api/tests")]
    from intelligence_suggestion_fixture import rebind, suggestion_event

    from app.repositories.intelligence_repository import IntelligenceRepository
    from app.services.intelligence_contract import TOPIC, validate_event

    source = datetime.now(UTC) - timedelta(seconds=1)
    event = suggestion_event(
        source=source,
        product_id="suggestion-product-00",
        action="Fixture with short expiry; review only.",
    )
    event["payload"]["expires_at"] = (source + timedelta(seconds=9)).isoformat()
    rebind(event)
    validate_event(event, transport_topic=TOPIC)
    IntelligenceRepository().project(event)
    return event["payload"]


if __name__ == "__main__":
    sys.stdout.write(json.dumps(short_lived()) + "\n")
