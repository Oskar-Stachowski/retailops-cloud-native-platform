from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def sample_summary() -> dict:
    return {
        "products_count": 3,
        "sales_count": 12,
        "inventory_snapshots_count": 6,
        "forecasts_count": 2,
        "anomalies_count": 1,
        "recommendations_count": 1,
        "open_anomalies_count": 1,
        "open_recommendations_count": 1,
        "open_work_items_count": 2,
        "last_refresh_at": "2026-05-01T10:00:00+00:00",
    }


def sample_sales_trend() -> list[dict]:
    return [
        {
            "date": "2026-05-01",
            "units_sold": 10,
            "revenue": 199.90,
        },
        {
            "date": "2026-05-02",
            "units_sold": 15,
            "revenue": 299.50,
        },
    ]


def sample_work_item(source: str = "anomaly") -> dict:
    return {
        "id": "11111111-1111-1111-1111-111111111111",
        "source": source,
        "product_id": "22222222-2222-2222-2222-222222222222",
        "sku": "ELEC-HEAD-001",
        "type": "stockout_risk",
        "severity": "high",
        "priority": "high",
        "status": "open",
        "title": "Potential stockout risk",
        "description": "Forecast demand is higher than current stock.",
        "created_at": "2026-05-01T10:00:00+00:00",
        "updated_at": "2026-05-01T11:00:00+00:00",
        "detected_at": "2026-05-01T09:30:00+00:00",
    }


def sample_stock_risk_summary() -> dict:
    return {
        "total_risk_items": 4,
        "normal_count": 1,
        "stockout_risk_count": 2,
        "overstock_risk_count": 1,
        "unknown_count": 0,
    }


def test_dashboard_summary_endpoint_returns_expected_shape(monkeypatch):
    monkeypatch.setattr(
        "app.api.dashboard.dashboard_service.get_summary",
        lambda: {"summary": sample_summary()},
    )

    response = client.get("/dashboard/summary")

    assert response.status_code == 200
    payload = response.json()

    assert "summary" in payload
    assert payload["summary"]["products_count"] == 3
    assert payload["summary"]["sales_count"] == 12
    assert payload["summary"]["inventory_snapshots_count"] == 6
    assert payload["summary"]["open_work_items_count"] == 2
    assert payload["summary"]["last_refresh_at"] == "2026-05-01T10:00:00Z"


def test_dashboard_sales_trend_endpoint_returns_items(monkeypatch):
    monkeypatch.setattr(
        "app.api.dashboard.dashboard_service.get_sales_trend",
        lambda days=14: {
            "items": sample_sales_trend(),
            "days": days,
        },
    )

    response = client.get("/dashboard/sales-trend?days=7")

    assert response.status_code == 200
    payload = response.json()

    assert payload["days"] == 7
    assert isinstance(payload["items"], list)
    assert payload["items"][0]["date"] == "2026-05-01"
    assert payload["items"][0]["units_sold"] == 10
    assert payload["items"][0]["revenue"] == 199.90


def test_dashboard_sales_trend_endpoint_rejects_invalid_days():
    response = client.get("/dashboard/sales-trend?days=0")

    assert response.status_code == 422


def test_dashboard_alerts_endpoint_returns_items(monkeypatch):
    monkeypatch.setattr(
        "app.api.dashboard.dashboard_service.get_open_alerts",
        lambda limit=10: {
            "items": [sample_work_item(source="anomaly")],
            "limit": limit,
        },
    )

    response = client.get("/dashboard/alerts?limit=5")

    assert response.status_code == 200
    payload = response.json()

    assert payload["limit"] == 5
    assert isinstance(payload["items"], list)
    assert payload["items"][0]["source"] == "anomaly"
    assert payload["items"][0]["status"] == "open"


def test_dashboard_alerts_endpoint_rejects_invalid_limit():
    response = client.get("/dashboard/alerts?limit=101")

    assert response.status_code == 422


def test_dashboard_recommendations_endpoint_returns_items(monkeypatch):
    monkeypatch.setattr(
        "app.api.dashboard.dashboard_service.get_top_recommendations",
        lambda limit=10: {
            "items": [sample_work_item(source="recommendation")],
            "limit": limit,
        },
    )

    response = client.get("/dashboard/recommendations?limit=5")

    assert response.status_code == 200
    payload = response.json()

    assert payload["limit"] == 5
    assert isinstance(payload["items"], list)
    assert payload["items"][0]["source"] == "recommendation"


def test_dashboard_open_work_items_endpoint_returns_items(monkeypatch):
    monkeypatch.setattr(
        "app.api.dashboard.dashboard_service.get_open_work_items",
        lambda limit=10: {
            "items": [
                sample_work_item(source="anomaly"),
                sample_work_item(source="recommendation"),
            ],
            "limit": limit,
        },
    )

    response = client.get("/dashboard/open-work-items?limit=2")

    assert response.status_code == 200
    payload = response.json()

    assert payload["limit"] == 2
    assert len(payload["items"]) == 2
    assert payload["items"][0]["source"] in {"anomaly", "recommendation"}


def test_dashboard_stock_risk_summary_endpoint_returns_expected_shape(monkeypatch):
    monkeypatch.setattr(
        "app.api.dashboard.dashboard_service.get_stock_risk_summary",
        lambda: sample_stock_risk_summary(),
    )

    response = client.get("/dashboard/stock-risk-summary")

    assert response.status_code == 200
    payload = response.json()

    assert payload["total_risk_items"] == 4
    assert payload["normal_count"] == 1
    assert payload["stockout_risk_count"] == 2
    assert payload["overstock_risk_count"] == 1
    assert payload["unknown_count"] == 0


def test_dashboard_operational_visibility_endpoint_returns_expected_shape(monkeypatch):
    monkeypatch.setattr(
        "app.api.dashboard.dashboard_service.get_operational_visibility",
        lambda sales_trend_days=14, work_items_limit=10: {
            "generated_at": "2026-05-01T12:00:00+00:00",
            "summary": sample_summary(),
            "stock_risk_summary": sample_stock_risk_summary(),
            "sales_trend": sample_sales_trend(),
            "open_work_items": [
                sample_work_item(source="anomaly"),
                sample_work_item(source="recommendation"),
            ],
            "limits": {
                "sales_trend_days": sales_trend_days,
                "work_items_limit": work_items_limit,
            },
        },
    )

    response = client.get(
        "/dashboard/operational-visibility?"
        "sales_trend_days=7&work_items_limit=2"
    )

    assert response.status_code == 200
    payload = response.json()

    assert "generated_at" in payload
    assert payload["summary"]["products_count"] == 3
    assert payload["stock_risk_summary"]["stockout_risk_count"] == 2
    assert len(payload["sales_trend"]) == 2
    assert len(payload["open_work_items"]) == 2
    assert payload["limits"]["sales_trend_days"] == 7
    assert payload["limits"]["work_items_limit"] == 2


def test_dashboard_operational_visibility_endpoint_rejects_invalid_params():
    response = client.get(
        "/dashboard/operational-visibility?"
        "sales_trend_days=0&work_items_limit=10"
    )

    assert response.status_code == 422
