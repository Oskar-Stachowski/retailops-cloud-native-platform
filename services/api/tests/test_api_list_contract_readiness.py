"""Production-readiness checks for list endpoint pagination/filtering contracts."""

from __future__ import annotations

from typing import Any

from app.main import app

LIST_ENDPOINT_CONTRACTS: dict[str, set[str]] = {
    "/products": {"limit", "offset", "sort_by", "sort_order", "category", "status", "search"},
    "/forecasts": {"limit", "offset", "sort_by", "sort_order", "product_id", "status", "method"},
    "/forecast-runs": {
        "limit",
        "offset",
        "sort_by",
        "sort_order",
        "status",
        "model_version",
        "feature_dataset_id",
    },
    "/inventory-snapshots": {
        "limit",
        "offset",
        "sort_by",
        "sort_order",
        "product_id",
        "warehouse_code",
        "unit_of_measure",
    },
    "/sales": {"limit", "offset", "sort_by", "sort_order", "product_id", "channel", "currency"},
    "/inventory-risks": {"limit", "offset", "sort_by", "sort_order", "risk_status", "category"},
    "/notifications": {"limit", "offset", "user_id"},
}


def _get_get_operation(path: str) -> dict[str, Any]:
    openapi = app.openapi()
    return openapi["paths"][path]["get"]


def _parameters_by_name(operation: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {parameter["name"]: parameter for parameter in operation.get("parameters", [])}


def test_list_endpoints_publish_expected_query_contracts() -> None:
    for path, required_parameters in LIST_ENDPOINT_CONTRACTS.items():
        operation = _get_get_operation(path)
        parameters = _parameters_by_name(operation)

        missing = required_parameters.difference(parameters)
        assert not missing, f"{path} is missing query parameters: {sorted(missing)}"


def test_list_endpoints_publish_standard_pagination_bounds() -> None:
    for path in LIST_ENDPOINT_CONTRACTS:
        parameters = _parameters_by_name(_get_get_operation(path))

        limit_schema = parameters["limit"]["schema"]
        offset_schema = parameters["offset"]["schema"]

        assert limit_schema["minimum"] == 1, path
        assert limit_schema["maximum"] <= 200, path
        assert offset_schema["minimum"] == 0, path


def test_core_list_endpoints_use_stable_response_models() -> None:
    expected_models = {
        "/products": "ProductListResponse",
        "/forecasts": "ForecastListResponse",
        "/forecast-runs": "ForecastRunListResponse",
        "/inventory-snapshots": "InventorySnapshotListResponse",
        "/sales": "SaleListResponse",
        "/inventory-risks": "StockRiskListResponse",
        "/notifications": "NotificationListResponse",
    }

    for path, model_name in expected_models.items():
        operation = _get_get_operation(path)
        response_schema = operation["responses"]["200"]["content"]["application/json"]["schema"]

        assert response_schema["$ref"].endswith(f"/{model_name}"), path
