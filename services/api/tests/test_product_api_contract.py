from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


PRODUCT_ID = "85710dbe-1aea-50ac-a155-fb216e12ab97"


class FakeProductService:
    def list_products_response(
        self,
        category=None,
        status=None,
        search=None,
        limit=50,
        offset=0,
        sort_by="sku",
        sort_order="asc",
    ):
        assert category == "Electronics"
        assert status == "active"
        assert search == "head"
        assert limit == 2
        assert offset == 0
        assert sort_by == "sku"
        assert sort_order == "asc"

        return {
            "items": [
                {
                    "id": PRODUCT_ID,
                    "sku": "ELEC-HEAD-001",
                    "name": "Wireless Headphones",
                    "category": "Electronics",
                    "brand": "SoundMax",
                    "status": "active",
                    "created_at": "2026-01-01T10:00:00+00:00",
                    "updated_at": "2026-01-01T10:00:00+00:00",
                }
            ],
            "pagination": {
                "limit": limit,
                "offset": offset,
                "total": 1,
            },
        }

    def get_product_detail_response(self, product_id):
        if str(product_id) != PRODUCT_ID:
            return None

        return {
            "id": PRODUCT_ID,
            "sku": "ELEC-HEAD-001",
            "name": "Wireless Headphones",
            "category": "Electronics",
            "brand": "SoundMax",
            "status": "active",
            "created_at": "2026-01-01T10:00:00+00:00",
            "updated_at": "2026-01-01T10:00:00+00:00",
        }


def test_products_list_uses_stable_items_and_pagination_contract(monkeypatch):
    monkeypatch.setattr("app.api.products.product_service", FakeProductService())

    response = client.get(
        "/products",
        params={
            "category": "Electronics",
            "status": "active",
            "search": "head",
            "limit": 2,
            "offset": 0,
            "sort_by": "sku",
            "sort_order": "asc",
        },
    )

    assert response.status_code == 200
    body = response.json()

    assert list(body.keys()) == ["items", "pagination"]
    assert body["pagination"] == {"limit": 2, "offset": 0, "total": 1}
    assert body["items"][0]["sku"] == "ELEC-HEAD-001"
    assert body["items"][0]["category"] == "Electronics"


def test_product_detail_returns_one_product(monkeypatch):
    monkeypatch.setattr("app.api.products.product_service", FakeProductService())

    response = client.get(f"/products/{PRODUCT_ID}")

    assert response.status_code == 200
    body = response.json()

    assert body["id"] == PRODUCT_ID
    assert body["sku"] == "ELEC-HEAD-001"


def test_product_detail_returns_standard_404_error(monkeypatch):
    monkeypatch.setattr("app.api.products.product_service", FakeProductService())

    response = client.get("/products/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": "Resource not found",
        }
    }
