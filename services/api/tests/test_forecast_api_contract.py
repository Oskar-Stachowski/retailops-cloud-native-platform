from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


PRODUCT_ID = "85710dbe-1aea-50ac-a155-fb216e12ab97"
FORECAST_ID = "11111111-1111-4111-8111-111111111111"


class FakeForecastService:
    def list_forecasts_response(
        self,
        product_id=None,
        status=None,
        method=None,
        date_from=None,
        date_to=None,
        limit=50,
        offset=0,
        sort_by="forecast_period_start",
        sort_order="asc",
    ):
        assert str(product_id) == PRODUCT_ID
        assert status == "generated"
        assert method == "seeded_demo"
        assert str(date_from) == "2026-01-01"
        assert str(date_to) == "2026-01-31"
        assert limit == 5
        assert offset == 0
        assert sort_by == "forecast_period_start"
        assert sort_order == "asc"

        return {
            "items": [
                {
                    "id": FORECAST_ID,
                    "product_id": PRODUCT_ID,
                    "forecast_period_start": "2026-01-01",
                    "forecast_period_end": "2026-01-31",
                    "predicted_quantity": 120.5,
                    "unit_of_measure": "pcs",
                    "generated_at": "2026-01-01T08:00:00+00:00",
                    "method": "seeded_demo",
                    "status": "generated",
                    "confidence_level": 0.8,
                }
            ],
            "pagination": {
                "limit": limit,
                "offset": offset,
                "total": 1,
            },
        }

    def get_forecast_detail_response(self, forecast_id):
        if str(forecast_id) != FORECAST_ID:
            return None

        return {
            "id": FORECAST_ID,
            "product_id": PRODUCT_ID,
            "forecast_period_start": "2026-01-01",
            "forecast_period_end": "2026-01-31",
            "predicted_quantity": 120.5,
            "unit_of_measure": "pcs",
            "generated_at": "2026-01-01T08:00:00+00:00",
            "method": "seeded_demo",
            "status": "generated",
            "confidence_level": 0.8,
        }


def test_forecasts_list_uses_stable_items_and_pagination_contract(monkeypatch):
    monkeypatch.setattr("app.api.forecasts.forecast_service", FakeForecastService())

    response = client.get(
        "/forecasts",
        params={
            "product_id": PRODUCT_ID,
            "status": "generated",
            "method": "seeded_demo",
            "date_from": "2026-01-01",
            "date_to": "2026-01-31",
            "limit": 5,
            "offset": 0,
            "sort_by": "forecast_period_start",
            "sort_order": "asc",
        },
    )

    assert response.status_code == 200
    body = response.json()

    assert list(body.keys()) == ["items", "pagination"]
    assert body["pagination"] == {"limit": 5, "offset": 0, "total": 1}
    assert body["items"][0]["id"] == FORECAST_ID
    assert body["items"][0]["product_id"] == PRODUCT_ID


def test_forecast_detail_returns_one_forecast(monkeypatch):
    monkeypatch.setattr("app.api.forecasts.forecast_service", FakeForecastService())

    response = client.get(f"/forecasts/{FORECAST_ID}")

    assert response.status_code == 200
    body = response.json()

    assert body["id"] == FORECAST_ID
    assert body["method"] == "seeded_demo"


def test_forecast_detail_returns_standard_404_error(monkeypatch):
    monkeypatch.setattr("app.api.forecasts.forecast_service", FakeForecastService())

    response = client.get("/forecasts/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": "Resource not found",
        }
    }
