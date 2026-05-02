from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_dashboard_summary_endpoint_returns_expected_shape(monkeypatch):
    monkeypatch.setattr(
        "app.api.dashboard.dashboard_service.get_summary",
        lambda: {
            "summary": {
                "products_count": 3,
                "forecasts_count": 2,
                "anomalies_count": 1,
                "recommendations_count": 1,
                "open_work_items_count": 2,
                "last_refresh_at": "2026-05-01T10:00:00+00:00",
            }
        },
    )

    response = client.get("/dashboard/summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["products_count"] == 3
    assert "open_work_items_count" in payload["summary"]


def test_dashboard_sales_trend_endpoint_returns_items(monkeypatch):
    monkeypatch.setattr(
        "app.api.dashboard.dashboard_service.get_sales_trend",
        lambda days=14: {
            "items": [
                {"date": "2026-05-01", "units_sold": 10, "revenue": 199.90}
            ],
            "days": days,
        },
    )

    response = client.get("/dashboard/sales-trend?days=7")

    assert response.status_code == 200
    payload = response.json()
    assert payload["days"] == 7
    assert isinstance(payload["items"], list)


def test_analytics_inventory_risk_endpoint_returns_items(monkeypatch):
    monkeypatch.setattr(
        "app.api.analytics.analytics_service.get_inventory_risk",
        lambda limit=50: {
            "items": [
                {
                    "sku": "ELEC-HEAD-001",
                    "current_stock": 5,
                    "forecast_quantity": 20,
                    "risk_status": "stockout_risk",
                }
            ],
            "limit": limit,
        },
    )

    response = client.get("/analytics/inventory-risk?limit=5")

    assert response.status_code == 200
    payload = response.json()
    assert payload["limit"] == 5
    assert payload["items"][0]["risk_status"] == "stockout_risk"
