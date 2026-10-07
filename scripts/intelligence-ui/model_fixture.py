"""Native-shaped fixtures for SQL/API/browser mechanics; no model qualification claim."""

# ruff: noqa: INP001, PLC0415

from __future__ import annotations

import hashlib
import json
import secrets
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def seed(control: Path) -> dict[str, Any]:
    sys.path[:0] = [str(ROOT / "services/api"), str(ROOT / "services/api/tests")]
    from test_intelligence_model_access import model_policy
    from test_intelligence_model_durability import KINDS, bind, fixture_event

    from app.repositories.intelligence_repository import IntelligenceRepository

    expected = {}
    repository = IntelligenceRepository()
    for kind in KINDS:
        events = [fixture_event(kind) for _ in range(70)]
        if kind == "stockout_risk_scored":
            events[0]["payload"].update(
                status="already_stockout",
                status_reason="already_stockout",
                probability=None,
                risk_band=None,
            )
            bind(events[0])
        foreign = fixture_event(kind)
        foreign["payload"]["product_id"] = "foreign-model-product"
        bind(foreign)
        for event in [*events, foreign]:
            repository.project(event)
        id_field = "anomaly_id" if kind == "anomaly_detected" else "risk_id"
        events.sort(
            key=lambda event: (
                event["payload"]["as_of"],
                event["payload"]["generated_at"],
                event["payload"][id_field],
            ),
            reverse=True,
        )
        expected[kind] = [event["payload"] for event in events]
    token = secrets.token_urlsafe(48)
    policy = model_policy()
    policy["principals"][0]["credential_sha256"] = hashlib.sha256(token.encode()).hexdigest()
    for name, value in (
        ("model-access.json", json.dumps(policy)),
        ("model-credential", token),
        ("model-expected.json", json.dumps(expected)),
    ):
        path = control / name
        path.write_text(value)
        path.chmod(0o600)
    return {
        "scoped_rows_per_kind": 70,
        "foreign_rows_per_kind": 1,
        "scope": "synthetic_contract_mechanics_only",
        "model_qualification": False,
    }
