"""Suggestion credentials are personal, revocable and separate from forecast/demo scope."""

import hashlib
import json
import os

import pytest
from fastapi.testclient import TestClient
from intelligence_suggestion_fixture import access_document

from app.main import app

READ = "/intelligence/v2/recommendations"
TOKEN = "fixture-personal-suggestion-key-" + "r" * 32


@pytest.fixture
def policy(tmp_path, monkeypatch):
    path = tmp_path / "suggestion.json"
    raw = access_document(hashlib.sha256(TOKEN.encode()).hexdigest())
    path.write_text(json.dumps(raw))
    path.chmod(0o600)
    monkeypatch.setenv("RETAILOPS_INTELLIGENCE_SUGGESTION_ACCESS_POLICY", str(path))
    monkeypatch.setattr(
        "app.api.intelligence_suggestions.read_suggestions",
        lambda *args, **kwargs: {
            "items": [],
            "pagination": {"limit": 50, "offset": 0, "total": 0, "next_offset": None},
            "selection": "current",
            "view_sha256": "a" * 64,
            "generated_at": "2026-10-04T00:00:00Z",
            "data_status": "no_data",
            "execution_authorized": False,
        },
    )
    return path, raw


def test_missing_invalid_and_revoked_credentials(policy):
    path, raw = policy
    with TestClient(app) as client:
        assert client.get(READ).status_code == 401
        assert client.get(READ, headers={"Authorization": "Bearer short"}).status_code == 401
        assert client.get(READ, headers={"Authorization": "Bearer " + "x" * 64}).status_code == 401
        headers = {"Authorization": "Bearer " + TOKEN}
        response = client.get(READ, headers=headers)
        assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
        assert "Authorization" in response.headers["vary"]
        assert (
            client.get(READ + "/12345678-1234-4234-8234-123456789012", headers=headers).status_code
            == 404
        )
        raw["principals"][0]["credential_sha256"] = "0" * 64
        replacement = path.with_suffix(".new")
        replacement.write_text(json.dumps(raw))
        replacement.chmod(0o600)
        os.replace(replacement, path)
        response = client.get(READ, headers=headers)
        assert response.status_code == 401 and TOKEN not in response.text
        assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    "mode",
    [
        "world",
        "symlink",
        "hardlink",
        "fifo",
        "oversized",
        "malformed",
        "duplicate",
        "wrong_capability",
    ],
)
def test_unsafe_policy_fails_closed(policy, mode):
    path, raw = policy
    if mode == "world":
        path.chmod(0o644)
    elif mode == "hardlink":
        os.link(path, path.with_suffix(".link"))
    elif mode in {"symlink", "fifo"}:
        path.unlink()
        if mode == "symlink":
            path.symlink_to(path.with_suffix(".missing"))
        else:
            os.mkfifo(path, 0o600)
    elif mode == "oversized":
        path.write_bytes(b"x" * 65537)
    elif mode == "malformed":
        path.write_text("{}")
    else:
        if mode == "duplicate":
            raw["principals"].append(raw["principals"][0])
        else:
            raw["principals"][0]["capabilities"] = ["forecast:read"]
        path.write_text(json.dumps(raw))
    with TestClient(app) as client:
        response = client.get(READ, headers={"Authorization": "Bearer " + TOKEN})
        assert response.status_code == 503 and TOKEN not in response.text


@pytest.mark.parametrize(
    "query",
    [
        "user_id=platform-admin",
        "limit=1&limit=2",
        "selection=accepted",
        "trace_id=other",
        "limit=51",
        "offset=501",
        "view_sha256=other",
        "product_id=fixture-product&product_id=other",
    ],
)
def test_unknown_repeated_and_unbounded_query_rejected(policy, query):
    with TestClient(app) as client:
        headers = {"Authorization": "Bearer " + TOKEN}
        assert client.get(READ + "?" + query, headers=headers).status_code == 422
        assert (
            client.get(
                READ + "/12345678-1234-4234-8234-123456789012?user_id=platform-admin",
                headers=headers,
            ).status_code
            == 422
        )


def test_no_configured_policy_and_no_demo_fallback(monkeypatch):
    monkeypatch.delenv("RETAILOPS_INTELLIGENCE_SUGGESTION_ACCESS_POLICY", raising=False)
    with TestClient(app) as client:
        response = client.get(
            READ + "?user_id=platform-admin", headers={"Authorization": "Bearer " + TOKEN}
        )
        assert response.status_code == 401
