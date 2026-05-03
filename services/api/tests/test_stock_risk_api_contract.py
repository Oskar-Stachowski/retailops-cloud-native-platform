from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


PRODUCT_ID = "85710dbe-1aea-50ac-a155-fb216e12ab97"


class FakeStockRiskService:
    def list_inventory_risks_response(
        self,
        risk_status=None,
        category=None,
        limit=50,
        offset=0,
        sort_by="risk_status",
        sort_order="asc",
    ):
        assert risk_status == "stockout_risk"
        assert category == "Electronics"
        assert limit == 5
        assert offset == 0
        assert sort_by == "risk_status"
        assert sort_order == "asc"

        return {
            "items": [
                {
                    "product_id": PRODUCT_ID,
                    "sku": "ELEC-HEAD-001",
                    "name": "Wireless Headphones",
                    "category": "Electronics",
                    "current_stock": 10.0,
                    "forecast_quantity": 25.0,
                    "risk_status": "stockout_risk",
                    "inventory_updated_at": "2026-01-15T10:00:00+00:00",
                }
            ],
            "pagination": {
                "limit": limit,
                "offset": offset,
                "total": 1,
            },
        }


def test_inventory_risks_list_uses_stable_items_and_pagination_contract(monkeypatch):
    monkeypatch.setattr(
        "app.api.stock_risks.stock_risk_service",
        FakeStockRiskService(),
    )

    response = client.get(
        "/inventory-risks",
        params={
            "risk_status": "stockout_risk",
            "category": "Electronics",
            "limit": 5,
            "offset": 0,
            "sort_by": "risk_status",
            "sort_order": "asc",
        },
    )

    assert response.status_code == 200
    body = response.json()

    assert list(body.keys()) == ["items", "pagination"]
    assert body["pagination"] == {"limit": 5, "offset": 0, "total": 1}
    assert body["items"][0]["product_id"] == PRODUCT_ID
    assert body["items"][0]["risk_status"] == "stockout_risk"
