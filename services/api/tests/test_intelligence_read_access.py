"""Read-policy revocation and private browser responses without a running database."""

import hashlib
import json
import os

import pytest
from fastapi.testclient import TestClient

from app.main import app

READ = "/intelligence/v2/forecasts"
TOKEN = "fixture-personal-read-credential-" + "x" * 32


@pytest.fixture
def policy(tmp_path, monkeypatch):
    path = tmp_path / "access.json"
    raw = {
        "version": "retailops-intelligence-access-1.0",
        "principals": [
            {
                "principal_id": "fixture-personal-reader",
                "credential_sha256": hashlib.sha256(TOKEN.encode()).hexdigest(),
                "capabilities": ["forecast:read"],
                "product_ids": ["fixture-product"],
                "selling_location_ids": ["fixture-store"],
                "channels": ["store"],
                "release_ids": ["v12-model-release-sha256-" + "a" * 64],
            }
        ],
    }
    path.write_text(json.dumps(raw))
    path.chmod(0o600)
    monkeypatch.setenv("RETAILOPS_INTELLIGENCE_ACCESS_POLICY", str(path))
    monkeypatch.setattr(
        "app.api.intelligence.read_forecasts",
        lambda principal, *args, **kwargs: {
            "items": [],
            "pagination": {"limit": 50, "offset": 0, "total": 0, "next_offset": None},
            "view_sha256": "a" * 64,
            "selection": "immutable_history",
            "generated_at": "2026-10-04T00:00:00Z",
            "data_status": "no_data",
        },
    )
    return path, raw


def test_read_scope_and_revocation_are_reloaded_without_restart(policy):
    path, raw = policy
    headers = {"Authorization": "Bearer " + TOKEN}
    with TestClient(app) as client:
        assert client.get(READ, headers=headers).status_code == 200
        raw["principals"][0]["credential_sha256"] = "0" * 64
        replacement = path.with_suffix(".replacement")
        replacement.write_text(json.dumps(raw))
        replacement.chmod(0o600)
        os.replace(replacement, path)
        response = client.get(READ, headers=headers)
        assert response.status_code == 401
        assert TOKEN not in response.text


@pytest.mark.parametrize("mode", ["world_readable", "symlink", "hardlink", "fifo", "duplicate"])
def test_unsafe_replacement_policy_fails_closed(policy, mode):
    path, raw = policy
    if mode == "world_readable":
        path.chmod(0o644)
    elif mode == "hardlink":
        os.link(path, path.with_suffix(".link"))
    elif mode == "duplicate":
        raw["principals"].append(raw["principals"][0])
        path.write_text(json.dumps(raw))
    else:
        path.unlink()
        if mode == "fifo":
            os.mkfifo(path, 0o600)
        else:
            path.symlink_to(path.with_suffix(".missing"))
    with TestClient(app) as client:
        response = client.get(READ, headers={"Authorization": "Bearer " + TOKEN})
        assert response.status_code == 503
        assert TOKEN not in response.text


def test_private_success_and_errors_never_inherit_demo_identity(policy):
    with TestClient(app) as client:
        for headers, query, status in [
            ({}, "?user_id=platform-admin", 401),
            ({"Authorization": "Bearer " + TOKEN}, "", 200),
            ({"Authorization": "Bearer " + TOKEN}, "?product_id=a&product_id=b", 422),
            ({"Authorization": "Bearer " + TOKEN}, "?user_id=platform-admin", 422),
        ]:
            response = client.get(READ + query, headers=headers)
            assert response.status_code == status
            assert response.headers["cache-control"] == "no-store"
            assert "Authorization" in response.headers["vary"]
        assert client.get("/health").headers.get("cache-control") != "no-store"
