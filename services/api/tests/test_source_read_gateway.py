import hashlib
import json
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.auth import source_reads as auth
from app.main import app

PRODUCT = "85710dbe-1aea-50ac-a155-fb216e12ab97"
OTHER = "00000000-0000-4000-8000-000000000001"
TOKEN = "explicit-test-source-token-" + "a" * 40
HEADERS = {"Authorization": "Bearer " + TOKEN}
client = TestClient(app)
PARAMS = {
    "products": {"product_id": PRODUCT},
    "sales": {
        "product_id": PRODUCT,
        "channel": "store",
        "sold_from": "2026-09-01T00:00:00Z",
        "sold_to": "2026-10-01T00:00:00Z",
    },
    "inventory-snapshots": {
        "product_id": PRODUCT,
        "warehouse_code": "WH-01",
        "recorded_from": "2026-09-01T00:00:00Z",
        "recorded_to": "2026-10-01T00:00:00Z",
    },
    "forecasts": {"product_id": PRODUCT, "date_from": "2026-09-01", "date_to": "2026-10-01"},
    "inventory-risks": {"product_id": PRODUCT},
}


@pytest.fixture(autouse=True)
def private_policy(tmp_path, monkeypatch):
    policy = tmp_path / "source-policy.json"
    policy.write_text(
        json.dumps(
            {
                "version": "retailops-source-access-1.0",
                "principals": [
                    {
                        "principal_id": "source-test",
                        "credential_sha256": hashlib.sha256(TOKEN.encode()).hexdigest(),
                        "resources": list(PARAMS),
                        "product_ids": [PRODUCT],
                        "channels": ["store"],
                        "warehouse_codes": ["WH-01"],
                    }
                ],
            }
        )
    )
    policy.chmod(0o600)
    monkeypatch.setenv("RETAILOPS_SOURCE_ACCESS_POLICY", str(policy))
    auth.access_policy.cache_clear()
    yield policy
    auth.access_policy.cache_clear()


@pytest.mark.parametrize("resource", PARAMS)
def test_each_read_is_authenticated_scoped_and_bounded(resource, monkeypatch):
    received = []

    def reader(query):
        received.append(query)
        return {
            "items": [],
            "pagination": {"limit": query.limit, "offset": query.offset, "total": 0},
        }

    monkeypatch.setattr("app.api.source_reads.read_page", reader)
    url = "/integration/v2/" + resource
    assert client.get(url, params=PARAMS[resource]).status_code == 401
    assert not received
    response = client.get(url, params=PARAMS[resource], headers=HEADERS)
    assert response.status_code == 200
    assert response.json()["pagination"] == {"limit": 50, "offset": 0, "total": 0}
    assert response.headers["x-retailops-read-mode"] == "bounded-live"
    assert response.headers["x-retailops-snapshot-supported"] == "false"
    assert len(response.headers["x-retailops-source-contract-sha256"]) == 64
    assert len(received) == 1
    bad = dict(PARAMS[resource], product_id=OTHER)
    assert client.get(url, params=bad, headers=HEADERS).status_code == 403
    assert len(received) == 1


@pytest.mark.parametrize("resource", PARAMS)
@pytest.mark.parametrize(
    "invalid",
    [
        {"store_id": OTHER},
        {"user_id": OTHER},
        {"limit": 101},
        {"offset": 10001},
        {"sort_by": "not-a-column"},
    ],
)
def test_invalid_or_authority_changing_query_never_reads_db(resource, invalid, monkeypatch):
    def no_read(query):
        pytest.fail("invalid query reached database")

    monkeypatch.setattr("app.api.source_reads.read_page", no_read)
    response = client.get(
        "/integration/v2/" + resource, params=dict(PARAMS[resource], **invalid), headers=HEADERS
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    "resource,invalid",
    [
        ("sales", {"channel": "online"}),
        ("inventory-snapshots", {"warehouse_code": "WH-02"}),
    ],
)
def test_other_channel_and_warehouse_are_denied(resource, invalid, monkeypatch):
    def no_read(query):
        pytest.fail("foreign scope reached database")

    monkeypatch.setattr("app.api.source_reads.read_page", no_read)
    assert (
        client.get(
            "/integration/v2/" + resource, params=dict(PARAMS[resource], **invalid), headers=HEADERS
        ).status_code
        == 403
    )


@pytest.mark.parametrize(
    "invalid",
    [
        {"sold_from": "2026-01-01T00:00:00Z"},
        {"sold_from": "2026-10-02T00:00:00Z"},
        {"sold_from": "2026-09-01T00:00:00"},
    ],
)
def test_period_requires_timezone_order_and_90_day_bound(invalid):
    assert (
        client.get(
            "/integration/v2/sales", params=dict(PARAMS["sales"], **invalid), headers=HEADERS
        ).status_code
        == 422
    )


def test_capabilities_and_snapshot_explicitly_report_unsupported():
    response = client.get("/integration/v2/capabilities", headers=HEADERS)
    assert response.status_code == 200
    body = response.json()
    assert body["immutable_snapshot"] is False and body["snapshot_replay_handoff"] is False
    assert body["sales_full_ml_grain"] is False
    assert "ingested_at" in body["missing_sales_fields"]
    assert body["legacy_risk_semantics"] == "product_heuristic_not_ml_probability"
    assert client.get("/integration/v2/snapshot", headers=HEADERS).status_code == 409
    assert client.get("/integration/v2/snapshot").status_code == 401


def test_policy_permissions_and_symlinks_fail_closed(private_policy, tmp_path):
    private_policy.chmod(0o644)
    assert client.get("/integration/v2/capabilities", headers=HEADERS).status_code == 503
    private_policy.chmod(0o600)
    link = tmp_path / "link"
    link.symlink_to(private_policy)
    import os

    os.environ["RETAILOPS_SOURCE_ACCESS_POLICY"] = str(link)
    auth.access_policy.cache_clear()
    assert client.get("/integration/v2/capabilities", headers=HEADERS).status_code == 503


def test_database_outage_returns_safe_503_without_connection_details(monkeypatch):
    def unavailable(query):
        raise psycopg.OperationalError("private-host password=do-not-show")

    monkeypatch.setattr("app.api.source_reads.read_page", unavailable)
    response = client.get("/integration/v2/products", params=PARAMS["products"], headers=HEADERS)
    assert response.status_code == 503
    assert "private-host" not in response.text and "do-not-show" not in response.text


def test_executable_contract_matches_query_and_response_schemas():
    contract = json.loads(
        (Path(__file__).parents[1] / "app/contracts/source-reads-v2/openapi.json").read_text()
    )
    actual = app.openapi()
    for path, operations in contract["paths"].items():
        assert operations == actual["paths"][path]
    for name, schema in contract["components"]["schemas"].items():
        assert schema == actual["components"]["schemas"][name]
