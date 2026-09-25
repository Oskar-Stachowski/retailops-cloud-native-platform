# ruff: noqa: INP001
"""Validate the deployed API through its real Nginx proxy and inspect stored data."""

import importlib.util
import json
import sys
from urllib.request import Request, urlopen

spec = importlib.util.spec_from_file_location("recovery_checks", "/recovery/checks.py")
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)


def api(path: str, body: dict | None = None) -> dict:
    request = Request(
        "http://frontend:8080/api" + path,
        data=None if body is None else json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urlopen(request, timeout=10) as response:  # noqa: S310 -- fixed private Compose origin
        recovery.require(response.status == 200, "Deployed API returned an error")
        return json.load(response)


def validate(expected: dict) -> dict:
    recovery.require(
        recovery.snapshot() == expected["snapshot"], "Deployment changed stored data/schema"
    )
    recovery.require(api("/health")["status"] == "ok", "API health failed")
    recovery.require(api("/ready")["database"] == "ok", "API readiness failed")
    for entity in expected["entities"]:
        detail = api(f"/products/{entity['product_id']}/360?limit=50")
        matching = [r for r in detail[entity["resource"]] if r["id"] == entity["id"]]
        recovery.require(
            len(matching) == 1 and matching[0]["status"] == entity["status"],
            "Stored decision is missing from the deployed API",
        )
    for mutation in expected["mutations"]:
        recovery.require(
            api(mutation["path"], mutation["body"]) == mutation["response"],
            "Idempotent replay differs from its original response",
        )
    recovery.require(recovery.snapshot() == expected["snapshot"], "Replay duplicated audit history")
    return {
        "http_health_readiness": "passed",
        "decisions": 3,
        "idempotent_actions": 5,
        "data_schema_unchanged": True,
    }


def write(expected: dict, stage: str) -> dict:
    alert = expected["entities"][0]
    result = api(
        f"/alerts/{alert['id']}/comment?user_id=platform-admin",
        {
            "comment": f"Release drill: write after {stage}",
            "idempotency_key": "release-drill-" + stage,
        },
    )
    recovery.require(result["status"] == "resolved", "Comment changed the decision")
    after = recovery.snapshot()
    for table in ("workflow_actions", "workflow_audit_log"):
        recovery.require(
            after["tables"][table]["rows"] == expected["snapshot"]["tables"][table]["rows"] + 1,
            "New write did not append exactly one audit/history row",
        )
    return {**expected, "snapshot": after}


if __name__ == "__main__":
    expected = json.load(sys.stdin)
    result = validate(expected) if sys.argv[1] == "validate" else write(expected, sys.argv[2])
    sys.stdout.write(json.dumps(result) + "\n")
