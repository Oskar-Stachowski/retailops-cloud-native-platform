from datetime import datetime, timezone
from uuid import UUID

from fastapi.testclient import TestClient

from app.api import product_360
from app.main import app


PRODUCT_ID = UUID("85710dbe-1aea-50ac-a155-fb216e12ab97")
NOW = datetime(2026, 5, 4, 9, 56, 43, tzinfo=timezone.utc).isoformat()


def _product_360_payload():
    return {
        "product": {
            "id": str(PRODUCT_ID),
            "sku": "ELEC-HEAD-001",
            "name": "Wireless Headphones",
            "category": "Electronics",
            "brand": "SoundWave",
            "status": "active",
            "created_at": NOW,
            "updated_at": NOW,
        },
        "metrics": {
            "sales_count": 0,
            "total_units_sold": 0,
            "total_revenue": 0,
            "latest_sale_at": None,
            "inventory_snapshot_count": 0,
            "current_stock": None,
            "inventory_updated_at": None,
            "forecast_count": 0,
            "latest_forecast_quantity": None,
            "latest_forecast_period_start": None,
            "latest_forecast_period_end": None,
            "anomaly_count": 0,
            "alert_count": 0,
            "open_alert_count": 0,
            "recommendation_count": 0,
            "open_recommendation_count": 0,
            "workflow_action_count": 0,
            "risk_status": "unknown",
        },
        "stock_risk": None,
        "sales": [],
        "inventory_snapshots": [],
        "forecasts": [],
        "anomalies": [],
        "alerts": [],
        "recommendations": [],
        "workflow_actions": [],
        "limits": {"related_items": 10},
    }


def test_product_360_endpoint_returns_payload(monkeypatch):
    def fake_get_product_360(product_id, limit=10):
        assert product_id == PRODUCT_ID
        assert limit == 10
        return _product_360_payload()

    monkeypatch.setattr(
        product_360.product_360_service,
        "get_product_360",
        fake_get_product_360,
    )

    client = TestClient(app)
    response = client.get(f"/products/{PRODUCT_ID}/360")

    assert response.status_code == 200
    assert response.json()["product"]["sku"] == "ELEC-HEAD-001"


def test_product_360_endpoint_returns_404_for_missing_product(monkeypatch):
    monkeypatch.setattr(
        product_360.product_360_service,
        "get_product_360",
        lambda product_id, limit=10: None,
    )

    client = TestClient(app)
    response = client.get(f"/products/{PRODUCT_ID}/360")

    assert response.status_code == 404
