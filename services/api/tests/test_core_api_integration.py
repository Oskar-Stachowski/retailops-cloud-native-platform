"""Integration tests for Sprint 4 core API list/detail/filter endpoints.

These tests intentionally do not mock services or repositories. They exercise the
real FastAPI app against the configured PostgreSQL database and seeded demo data.

Run from services/api after migrations and seed data are available:

    PYTHONPATH=. DATABASE_URL=postgresql://retailops:retailops@localhost:5432/retailops pytest tests/test_core_api_integration.py

Why this file exists:
- Contract tests prove response shape with fake services.
- These integration tests prove the real path works:
  FastAPI -> service -> repository -> PostgreSQL -> JSON response.
"""

from __future__ import annotations

import os
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import app


pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason=(
        "Integration tests require DATABASE_URL and a migrated/seeded PostgreSQL "
        "database. Run docker compose, alembic upgrade head and seed_demo_data.py first."
    ),
)

client = TestClient(app)
ZERO_UUID = "00000000-0000-0000-0000-000000000000"


def get_json(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    response = client.get(path, params=params or {})
    assert response.status_code == 200, response.text
    return response.json()


def assert_list_contract(
    payload: dict[str, Any],
    *,
    expected_limit: int,
    expected_offset: int = 0,
) -> list[dict[str, Any]]:
    assert set(payload.keys()) == {"items", "pagination"}
    assert isinstance(payload["items"], list)

    pagination = payload["pagination"]
    assert pagination["limit"] == expected_limit
    assert pagination["offset"] == expected_offset
    assert isinstance(pagination["total"], int)
    assert pagination["total"] >= 0
    assert len(payload["items"]) <= expected_limit
    assert pagination["total"] >= len(payload["items"])

    return payload["items"]


def require_seeded_items(path: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    payload = get_json(path, {"limit": 5, "offset": 0, **(params or {})})
    items = assert_list_contract(payload, expected_limit=5)
    assert items, (
        f"Expected seeded demo data for {path}. "
        "Run migrations and services/api/scripts/seed_demo_data.py before this integration test."
    )
    return items


def assert_detail_roundtrip(collection_path: str, id_field: str = "id") -> dict[str, Any]:
    first_item = require_seeded_items(collection_path)[0]
    resource_id = first_item[id_field]

    detail_response = client.get(f"{collection_path}/{resource_id}")
    assert detail_response.status_code == 200, detail_response.text

    detail = detail_response.json()
    assert detail[id_field] == resource_id
    return detail


def assert_not_found(path: str) -> None:
    response = client.get(path)
    assert response.status_code == 404, response.text
    body = response.json()
    assert "error" in body
    assert body["error"]["code"] == "not_found"


# -----------------------------------------------------------------------------
# Products
# -----------------------------------------------------------------------------


def test_products_list_pagination_sorting_detail_and_filters() -> None:
    payload = get_json(
        "/products",
        {
            "limit": 5,
            "offset": 0,
            "sort_by": "sku",
            "sort_order": "asc",
        },
    )
    items = assert_list_contract(payload, expected_limit=5)
    assert items, "Expected seeded products."

    skus = [item["sku"] for item in items]
    assert skus == sorted(skus)

    first = items[0]

    detail = assert_detail_roundtrip("/products")
    assert detail["id"] == first["id"]
    assert detail["sku"] == first["sku"]

    by_status = require_seeded_items("/products", {"status": first["status"]})
    assert all(item["status"] == first["status"] for item in by_status)

    if first.get("category"):
        by_category = require_seeded_items("/products", {"category": first["category"]})
        assert all(item["category"] == first["category"] for item in by_category)

    by_search = require_seeded_items("/products", {"search": first["sku"]})
    assert any(item["id"] == first["id"] for item in by_search)

    assert_not_found(f"/products/{ZERO_UUID}")


# -----------------------------------------------------------------------------
# Forecasts
# -----------------------------------------------------------------------------


def test_forecasts_list_pagination_detail_and_filters() -> None:
    items = require_seeded_items(
        "/forecasts",
        {
            "sort_by": "forecast_period_start",
            "sort_order": "asc",
        },
    )
    first = items[0]

    detail = assert_detail_roundtrip("/forecasts")
    assert detail["id"] == first["id"]
    assert detail["product_id"] == first["product_id"]

    by_product = require_seeded_items("/forecasts", {"product_id": first["product_id"]})
    assert all(item["product_id"] == first["product_id"] for item in by_product)

    by_status = require_seeded_items("/forecasts", {"status": first["status"]})
    assert all(item["status"] == first["status"] for item in by_status)

    by_method = require_seeded_items("/forecasts", {"method": first["method"]})
    assert all(item["method"] == first["method"] for item in by_method)

    by_date_window = require_seeded_items(
        "/forecasts",
        {
            "date_from": first["forecast_period_start"],
            "date_to": first["forecast_period_end"],
        },
    )
    assert any(item["id"] == first["id"] for item in by_date_window)

    assert_not_found(f"/forecasts/{ZERO_UUID}")


# -----------------------------------------------------------------------------
# Inventory snapshots
# -----------------------------------------------------------------------------


def test_inventory_snapshots_list_pagination_detail_and_filters() -> None:
    items = require_seeded_items(
        "/inventory-snapshots",
        {
            "sort_by": "recorded_at",
            "sort_order": "desc",
        },
    )
    first = items[0]

    detail = assert_detail_roundtrip("/inventory-snapshots")
    assert detail["id"] == first["id"]
    assert detail["product_id"] == first["product_id"]

    by_product = require_seeded_items(
        "/inventory-snapshots",
        {"product_id": first["product_id"]},
    )
    assert all(item["product_id"] == first["product_id"] for item in by_product)

    by_warehouse = require_seeded_items(
        "/inventory-snapshots",
        {"warehouse_code": first["warehouse_code"]},
    )
    assert all(item["warehouse_code"] == first["warehouse_code"] for item in by_warehouse)

    by_unit = require_seeded_items(
        "/inventory-snapshots",
        {"unit_of_measure": first["unit_of_measure"]},
    )
    assert all(item["unit_of_measure"] == first["unit_of_measure"] for item in by_unit)

    assert_not_found(f"/inventory-snapshots/{ZERO_UUID}")


# -----------------------------------------------------------------------------
# Sales
# -----------------------------------------------------------------------------


def test_sales_list_pagination_detail_and_filters() -> None:
    items = require_seeded_items(
        "/sales",
        {
            "sort_by": "sold_at",
            "sort_order": "desc",
        },
    )
    first = items[0]

    detail = assert_detail_roundtrip("/sales")
    assert detail["id"] == first["id"]
    assert detail["product_id"] == first["product_id"]

    by_product = require_seeded_items("/sales", {"product_id": first["product_id"]})
    assert all(item["product_id"] == first["product_id"] for item in by_product)

    if first.get("channel"):
        by_channel = require_seeded_items("/sales", {"channel": first["channel"]})
        assert all(item["channel"] == first["channel"] for item in by_channel)

    by_currency = require_seeded_items("/sales", {"currency": first["currency"]})
    assert all(item["currency"] == first["currency"] for item in by_currency)

    assert_not_found(f"/sales/{ZERO_UUID}")


# -----------------------------------------------------------------------------
# Stock risk / inventory risk
# -----------------------------------------------------------------------------


def test_inventory_risks_list_pagination_and_filters() -> None:
    payload = get_json(
        "/inventory-risks",
        {
            "limit": 5,
            "offset": 0,
            "sort_by": "risk_status",
            "sort_order": "asc",
        },
    )
    items = assert_list_contract(payload, expected_limit=5)
    assert items, "Expected stock-risk items generated from products + inventory + forecasts."

    first = items[0]

    by_risk_status = require_seeded_items(
        "/inventory-risks",
        {"risk_status": first["risk_status"]},
    )
    assert all(item["risk_status"] == first["risk_status"] for item in by_risk_status)

    if first.get("category"):
        by_category = require_seeded_items(
            "/inventory-risks",
            {"category": first["category"]},
        )
        assert all(item["category"] == first["category"] for item in by_category)


# -----------------------------------------------------------------------------
# Input validation smoke checks
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "/products",
        "/forecasts",
        "/inventory-snapshots",
        "/sales",
        "/inventory-risks",
    ],
)
def test_core_list_endpoints_reject_invalid_pagination(path: str) -> None:
    response = client.get(path, params={"limit": 0, "offset": 0})
    assert response.status_code == 422, response.text


@pytest.mark.parametrize(
    "path,invalid_sort_by",
    [
        ("/products", "total_amount"),
        ("/forecasts", "sku"),
        ("/inventory-snapshots", "sku"),
        ("/sales", "sku"),
        ("/inventory-risks", "created_at"),
    ],
)
def test_core_list_endpoints_reject_unknown_sort_fields(
    path: str,
    invalid_sort_by: str,
) -> None:
    response = client.get(path, params={"sort_by": invalid_sort_by})
    assert response.status_code == 422, response.text
