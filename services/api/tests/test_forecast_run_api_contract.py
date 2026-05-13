from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

RUN_ID = "11111111-1111-4111-8111-111111111111"


def forecast_run_payload() -> dict:
    return {
        "run_key": "baseline-moving-average-v1:dataset-1",
        "model_name": "retailops-demand-baseline-moving-average",
        "model_version": "baseline-moving-average-v1",
        "model_type": "moving_average_baseline",
        "status": "candidate",
        "profile": "small",
        "seed": 42,
        "feature_dataset_name": "retailops-demand-forecast-features",
        "feature_dataset_id": "dataset-1",
        "feature_grain": ["date", "product_id", "store_id", "channel"],
        "target": "units_sold",
        "window_days": 28,
        "horizon_days": 7,
        "holdout_days": 7,
        "feature_row_count": 100,
        "forecast_row_count": 70,
        "evaluated_rows": 30,
        "skipped_rows": 2,
        "metrics": {"mae": "2.0000"},
        "artifacts": {"model_manifest": "model_manifest.json"},
        "started_at": "2026-05-13T08:00:00+00:00",
        "completed_at": "2026-05-13T08:05:00+00:00",
    }


def forecast_run_response() -> dict:
    payload = forecast_run_payload()
    return {
        "id": RUN_ID,
        **payload,
        "created_at": "2026-05-13T08:05:01+00:00",
        "updated_at": "2026-05-13T08:05:01+00:00",
    }


class FakeForecastRunService:
    def persist_forecast_run(self, payload: dict) -> dict:
        assert payload["run_key"] == "baseline-moving-average-v1:dataset-1"
        return forecast_run_response()

    def list_forecast_runs_response(
        self,
        status=None,
        model_version=None,
        feature_dataset_id=None,
        limit=50,
        offset=0,
        sort_by="completed_at",
        sort_order="desc",
    ) -> dict:
        assert status == "candidate"
        assert model_version == "baseline-moving-average-v1"
        assert feature_dataset_id == "dataset-1"
        assert limit == 5
        assert offset == 0
        assert sort_by == "completed_at"
        assert sort_order == "desc"
        return {
            "items": [forecast_run_response()],
            "pagination": {"limit": limit, "offset": offset, "total": 1},
        }

    def get_forecast_run_response(self, forecast_run_id) -> dict | None:
        if str(forecast_run_id) != RUN_ID:
            return None
        return forecast_run_response()


def test_forecast_run_create_uses_stable_response_contract(monkeypatch) -> None:
    monkeypatch.setattr("app.api.forecast_runs.forecast_run_service", FakeForecastRunService())

    response = client.post("/forecast-runs", json=forecast_run_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["id"] == RUN_ID
    assert body["status"] == "candidate"
    assert body["metrics"] == {"mae": "2.0000"}


def test_forecast_run_list_uses_stable_items_and_pagination_contract(monkeypatch) -> None:
    monkeypatch.setattr("app.api.forecast_runs.forecast_run_service", FakeForecastRunService())

    response = client.get(
        "/forecast-runs",
        params={
            "status": "candidate",
            "model_version": "baseline-moving-average-v1",
            "feature_dataset_id": "dataset-1",
            "limit": 5,
            "offset": 0,
            "sort_by": "completed_at",
            "sort_order": "desc",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert list(body.keys()) == ["items", "pagination"]
    assert body["pagination"] == {"limit": 5, "offset": 0, "total": 1}
    assert body["items"][0]["id"] == RUN_ID


def test_forecast_run_detail_returns_standard_404_error(monkeypatch) -> None:
    monkeypatch.setattr("app.api.forecast_runs.forecast_run_service", FakeForecastRunService())

    response = client.get("/forecast-runs/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": "Resource not found",
        },
    }
