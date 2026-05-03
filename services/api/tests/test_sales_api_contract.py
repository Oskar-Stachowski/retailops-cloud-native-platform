from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


PRODUCT_ID = "85710dbe-1aea-50ac-a155-fb216e12ab97"
SALE_ID = "33333333-3333-4333-8333-333333333333"


class FakeSalesService:
    def list_sales_response(
        self,
        product_id=None,
        channel=None,
        currency=None,
        sold_from=None,
        sold_to=None,
        limit=50,
        offset=0,
        sort_by="sold_at",
        sort_order="desc",
    ):
        assert str(product_id) == PRODUCT_ID
        assert channel == "online"
        assert currency == "PLN"
        assert str(sold_from) == "2026-01-01 00:00:00+00:00"
        assert str(sold_to) == "2026-01-31 23:59:59+00:00"
        assert limit == 5
        assert offset == 0
        assert sort_by == "sold_at"
        assert sort_order == "desc"

        return {
            "items": [
                {
                    "id": SALE_ID,
                    "product_id": PRODUCT_ID,
                    "quantity": 3,
                    "sold_at": "2026-01-15T10:00:00+00:00",
                    "unit_price": 99.99,
                    "total_amount": 299.97,
                    "currency": "PLN",
                    "channel": "online",
                    "created_at": "2026-01-15T10:01:00+00:00",
                }
            ],
            "pagination": {
                "limit": limit,
                "offset": offset,
                "total": 1,
            },
        }

    def get_sale_detail_response(self, sale_id):
        if str(sale_id) != SALE_ID:
            return None

        return {
            "id": SALE_ID,
            "product_id": PRODUCT_ID,
            "quantity": 3,
            "sold_at": "2026-01-15T10:00:00+00:00",
            "unit_price": 99.99,
            "total_amount": 299.97,
            "currency": "PLN",
            "channel": "online",
            "created_at": "2026-01-15T10:01:00+00:00",
        }


def test_sales_list_uses_stable_items_and_pagination_contract(monkeypatch):
    monkeypatch.setattr("app.api.sales.sales_service", FakeSalesService())

    response = client.get(
        "/sales",
        params={
            "product_id": PRODUCT_ID,
            "channel": "online",
            "currency": "PLN",
            "sold_from": "2026-01-01T00:00:00+00:00",
            "sold_to": "2026-01-31T23:59:59+00:00",
            "limit": 5,
            "offset": 0,
            "sort_by": "sold_at",
            "sort_order": "desc",
        },
    )

    assert response.status_code == 200
    body = response.json()

    assert list(body.keys()) == ["items", "pagination"]
    assert body["pagination"] == {"limit": 5, "offset": 0, "total": 1}
    assert body["items"][0]["id"] == SALE_ID
    assert body["items"][0]["total_amount"] == 299.97


def test_sale_detail_returns_one_sale(monkeypatch):
    monkeypatch.setattr("app.api.sales.sales_service", FakeSalesService())

    response = client.get(f"/sales/{SALE_ID}")

    assert response.status_code == 200
    body = response.json()

    assert body["id"] == SALE_ID
    assert body["quantity"] == 3


def test_sale_detail_returns_standard_404_error(monkeypatch):
    monkeypatch.setattr("app.api.sales.sales_service", FakeSalesService())

    response = client.get("/sales/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": "Resource not found",
        }
    }
