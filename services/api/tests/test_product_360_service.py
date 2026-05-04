from datetime import datetime, timezone
from uuid import UUID

from app.services.product_360_service import Product360Service


PRODUCT_ID = UUID("85710dbe-1aea-50ac-a155-fb216e12ab97")
NOW = datetime(2026, 5, 4, 9, 56, 43, tzinfo=timezone.utc)


class FakeProduct:
    def model_dump(self):
        return {
            "id": PRODUCT_ID,
            "sku": "ELEC-HEAD-001",
            "name": "Wireless Headphones",
            "category": "Electronics",
            "brand": "SoundWave",
            "status": "active",
            "created_at": NOW,
            "updated_at": NOW,
        }


class FakeProductRepository:
    def __init__(self, product):
        self.product = product

    def get_product_by_id(self, product_id):
        assert product_id == PRODUCT_ID
        return self.product


class FakeProduct360Repository:
    def get_metrics(self, product_id):
        assert product_id == PRODUCT_ID
        return {
            "sales_count": 3,
            "total_units_sold": 12,
            "total_revenue": 1200.5,
            "latest_sale_at": NOW,
            "inventory_snapshot_count": 2,
            "current_stock": 108,
            "inventory_updated_at": NOW,
            "forecast_count": 1,
            "latest_forecast_quantity": 69,
            "latest_forecast_period_start": "2026-05-01",
            "latest_forecast_period_end": "2026-05-07",
            "anomaly_count": 1,
            "alert_count": 1,
            "open_alert_count": 1,
            "recommendation_count": 1,
            "open_recommendation_count": 1,
            "workflow_action_count": 1,
        }

    def get_stock_risk(self, product_id):
        return {
            "product_id": PRODUCT_ID,
            "sku": "ELEC-HEAD-001",
            "name": "Wireless Headphones",
            "category": "Electronics",
            "current_stock": 108,
            "forecast_quantity": 69,
            "risk_status": "normal",
            "inventory_updated_at": NOW,
        }

    def list_sales(self, product_id, limit):
        return []

    def list_inventory_snapshots(self, product_id, limit):
        return []

    def list_forecasts(self, product_id, limit):
        return []

    def list_anomalies(self, product_id, limit):
        return []

    def list_alerts(self, product_id, limit):
        return []

    def list_recommendations(self, product_id, limit):
        return []

    def list_workflow_actions(self, product_id, limit):
        return []


def test_get_product_360_returns_composite_response():
    service = Product360Service(
        product_repository=FakeProductRepository(FakeProduct()),
        product_360_repository=FakeProduct360Repository(),
    )

    response = service.get_product_360(PRODUCT_ID, limit=5)

    assert response["product"]["sku"] == "ELEC-HEAD-001"
    assert response["metrics"]["sales_count"] == 3
    assert response["metrics"]["risk_status"] == "normal"
    assert response["stock_risk"]["current_stock"] == 108
    assert response["limits"] == {"related_items": 5}


def test_get_product_360_returns_none_when_product_missing():
    service = Product360Service(
        product_repository=FakeProductRepository(None),
        product_360_repository=FakeProduct360Repository(),
    )

    assert service.get_product_360(PRODUCT_ID) is None
