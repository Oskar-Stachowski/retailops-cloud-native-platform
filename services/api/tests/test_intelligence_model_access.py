"""Private model grants reload on each read and never inherit a demo principal."""

import hashlib
import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.intelligence_contract import CONTRACT_DIR
from app.services.intelligence_model_reader import model_scope

TOKEN = "fixture-model-personal-read-" + "x" * 32


def model_policy():
    anomaly = json.loads((CONTRACT_DIR / "anomaly_detected.fixture.json").read_bytes())["payload"]
    risk = json.loads((CONTRACT_DIR / "stockout_risk_scored.fixture.json").read_bytes())["payload"]
    return {"version": "retailops-model-intelligence-access-1.0", "principals": [{
        "principal_id": "fixture-model-reader", "credential_sha256": hashlib.sha256(TOKEN.encode()).hexdigest(),
        "capabilities": ["anomaly:read", "stockout:read"],
        "anomaly_scope": {"product_ids": [anomaly["product_id"]], "selling_location_ids": [anomaly["selling_location_id"]], "channels": [anomaly["channel"]], "currencies": [anomaly["currency"]], "release_ids": [anomaly["release_id"]]},
        "stockout_scope": {"product_ids": [risk["product_id"]], "stock_location_ids": [risk["stock_location_id"]], "release_ids": [risk["release_id"]]},
    }]}


@pytest.fixture
def policy(tmp_path, monkeypatch):
    path = tmp_path / "access.json"
    raw = model_policy()
    path.write_text(json.dumps(raw)); path.chmod(0o600)
    monkeypatch.setenv("RETAILOPS_INTELLIGENCE_MODEL_ACCESS_POLICY", str(path))

    def empty(principal, kind, filters, *, limit, offset, view_sha256):
        scope = model_scope(principal, kind)
        from fastapi import HTTPException
        if any(filters.get(field) is not None and filters[field] not in allowed for field, allowed in scope.items()):
            raise HTTPException(403, detail="intelligence_model_scope_denied")
        return {"items": [], "pagination": {"limit": limit, "offset": offset, "total": 0, "next_offset": None}, "view_sha256": "a" * 64, "selection": "immutable_history", "generated_at": "2026-10-07T00:00:00Z", "data_status": "no_data"}

    monkeypatch.setattr("app.api.intelligence_models.read_models", empty)
    return path, raw


@pytest.mark.parametrize("resource", ["anomalies", "stockout-risks"])
def test_auth_unknown_filters_and_private_caching(policy, resource):
    with TestClient(app) as client:
        path = "/intelligence/v2/" + resource
        for headers, query, status in [
            ({}, "?user_id=platform-admin", 401),
            ({"Authorization": "Bearer " + TOKEN}, "", 200),
            ({"Authorization": "Bearer " + TOKEN}, "?user_id=platform-admin", 422),
            ({"Authorization": "Bearer " + TOKEN}, "?product_id=foreign", 403),
            ({"Authorization": "Bearer " + TOKEN}, "?product_id=a&product_id=b", 422),
            ({"Authorization": "Bearer " + TOKEN}, "?limit=101", 422),
        ]:
            response = client.get(path + query, headers=headers)
            assert response.status_code == status
            assert response.headers["cache-control"] == "no-store"
            assert "Authorization" in response.headers["vary"]
            assert TOKEN not in response.text


def test_sales_scope_does_not_grant_physical_scope_and_revocation_is_immediate(policy):
    path, raw = policy
    principal = raw["principals"][0]
    principal["capabilities"] = ["anomaly:read"]; principal["stockout_scope"] = None
    path.write_text(json.dumps(raw))
    headers = {"Authorization": "Bearer " + TOKEN}
    with TestClient(app) as client:
        assert client.get("/intelligence/v2/anomalies", headers=headers).status_code == 200
        assert client.get("/intelligence/v2/stockout-risks", headers=headers).status_code == 403
        principal["credential_sha256"] = "f" * 64
        path.write_text(json.dumps(raw))
        assert client.get("/intelligence/v2/anomalies", headers=headers).status_code == 401


def test_world_readable_or_duplicate_policy_is_unavailable(policy):
    path, raw = policy
    headers = {"Authorization": "Bearer " + TOKEN}
    with TestClient(app) as client:
        path.chmod(0o644)
        assert client.get("/intelligence/v2/anomalies", headers=headers).status_code == 503
        path.chmod(0o600)
        raw["principals"].append(raw["principals"][0]); path.write_text(json.dumps(raw))
        assert client.get("/intelligence/v2/anomalies", headers=headers).status_code == 503


def test_read_openapi_exposes_both_owner_payloads_with_separate_names(policy):
    schema = app.openapi()
    assert "AI10_ANOMALY_Item" in schema["components"]["schemas"]
    assert "AI10_STOCKOUT_RiskItem" in schema["components"]["schemas"]
    for resource in ("anomalies", "stockout-risks"):
        assert schema["paths"]["/intelligence/v2/" + resource]["get"]["security"] == [{"ModelIntelligenceCredential": []}]
