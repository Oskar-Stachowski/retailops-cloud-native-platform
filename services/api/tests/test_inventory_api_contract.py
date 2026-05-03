from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


PRODUCT_ID = "85710dbe-1aea-50ac-a155-fb216e12ab97"
INVENTORY_SNAPSHOT_ID = "22222222-2222-4222-8222-222222222222"


class FakeInventoryService:
    def list_inventory_snapshots_response(
        self,
        product_id=None,
        warehouse_code=None,
        unit_of_measure=None,
        recorded_from=None,
        recorded_to=None,
        limit=50,
        offset=0,
        sort_by="recorded_at",
        sort_order="desc",
    ):
        assert str(product_id) == PRODUCT_ID
        assert warehouse_code == "WH-001"
        assert unit_of_measure == "pcs"
        assert str(recorded_from) == "2026-01-01 00:00:00+00:00"
        assert str(recorded_to) == "2026-01-31 23:59:59+00:00"
        assert limit == 5
        assert offset == 0
        assert sort_by == "recorded_at"
        assert sort_order == "desc"

        return {
            "items": [
                {
                    "id": INVENTORY_SNAPSHOT_ID,
                    "product_id": PRODUCT_ID,
                    "stock_quantity": 42,
                    "unit_of_measure": "pcs",
                    "warehouse_code": "WH-001",
                    "recorded_at": "2026-01-15T10:00:00+00:00",
                    "ingested_at": "2026-01-15T10:05:00+00:00",
                    "created_at": "2026-01-15T10:06:00+00:00",
                }
            ],
            "pagination": {
                "limit": limit,
                "offset": offset,
                "total": 1,
            },
        }

    def get_inventory_snapshot_detail_response(self, inventory_snapshot_id):
        if str(inventory_snapshot_id) != INVENTORY_SNAPSHOT_ID:
            return None

        return {
            "id": INVENTORY_SNAPSHOT_ID,
            "product_id": PRODUCT_ID,
            "stock_quantity": 42,
            "unit_of_measure": "pcs",
            "warehouse_code": "WH-001",
            "recorded_at": "2026-01-15T10:00:00+00:00",
            "ingested_at": "2026-01-15T10:05:00+00:00",
            "created_at": "2026-01-15T10:06:00+00:00",
        }


def test_inventory_list_uses_stable_items_and_pagination_contract(monkeypatch):
    monkeypatch.setattr("app.api.inventory.inventory_service", FakeInventoryService())

    response = client.get(
        "/inventory-snapshots",
        params={
            "product_id": PRODUCT_ID,
            "warehouse_code": "WH-001",
            "unit_of_measure": "pcs",
            "recorded_from": "2026-01-01T00:00:00+00:00",
            "recorded_to": "2026-01-31T23:59:59+00:00",
            "limit": 5,
            "offset": 0,
            "sort_by": "recorded_at",
            "sort_order": "desc",
        },
    )

    assert response.status_code == 200
    body = response.json()

    assert list(body.keys()) == ["items", "pagination"]
    assert body["pagination"] == {"limit": 5, "offset": 0, "total": 1}
    assert body["items"][0]["id"] == INVENTORY_SNAPSHOT_ID
    assert body["items"][0]["warehouse_code"] == "WH-001"


def test_inventory_detail_returns_one_snapshot(monkeypatch):
    monkeypatch.setattr("app.api.inventory.inventory_service", FakeInventoryService())

    response = client.get(f"/inventory-snapshots/{INVENTORY_SNAPSHOT_ID}")

    assert response.status_code == 200
    body = response.json()

    assert body["id"] == INVENTORY_SNAPSHOT_ID
    assert body["stock_quantity"] == 42


def test_inventory_detail_returns_standard_404_error(monkeypatch):
    monkeypatch.setattr("app.api.inventory.inventory_service", FakeInventoryService())

    response = client.get(
        "/inventory-snapshots/00000000-0000-0000-0000-000000000000"
    )

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": "Resource not found",
        }
    }
