from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from app.domain.models import ForecastRun, ForecastRunStatus
from app.services.forecast_run_service import ForecastRunService


RUN_ID = UUID("11111111-1111-4111-8111-111111111111")


def make_forecast_run() -> ForecastRun:
    now = datetime.now(UTC)
    return ForecastRun(
        id=RUN_ID,
        run_key="baseline-moving-average-v1:dataset-1",
        model_name="retailops-demand-baseline-moving-average",
        model_version="baseline-moving-average-v1",
        model_type="moving_average_baseline",
        status=ForecastRunStatus.candidate,
        profile="small",
        seed=42,
        feature_dataset_name="retailops-demand-forecast-features",
        feature_dataset_id="dataset-1",
        feature_grain=["date", "product_id", "store_id", "channel"],
        target="units_sold",
        window_days=28,
        horizon_days=7,
        holdout_days=7,
        feature_row_count=100,
        forecast_row_count=70,
        evaluated_rows=30,
        skipped_rows=2,
        metrics={"mae": "2.0000"},
        artifacts={"model_manifest": "model_manifest.json"},
        started_at=now,
        completed_at=now,
        created_at=now,
        updated_at=now,
    )


class FakeForecastRunRepository:
    def __init__(self) -> None:
        self.forecast_run = make_forecast_run()
        self.persisted_payload = None

    def upsert_forecast_run(self, forecast_run: ForecastRun) -> ForecastRun:
        self.persisted_payload = forecast_run
        return self.forecast_run

    def get_forecast_run_by_id(self, forecast_run_id: UUID) -> ForecastRun | None:
        if forecast_run_id == RUN_ID:
            return self.forecast_run
        return None

    def list_forecast_runs(self, **kwargs) -> list[ForecastRun]:
        self.list_kwargs = kwargs
        return [self.forecast_run]

    def count_forecast_runs(self, **kwargs) -> int:
        self.count_kwargs = kwargs
        return 1


def test_forecast_run_service_persists_payload() -> None:
    repository = FakeForecastRunRepository()
    service = ForecastRunService(repository)

    response = service.persist_forecast_run(make_forecast_run().model_dump())

    assert repository.persisted_payload is not None
    assert response["id"] == str(RUN_ID)
    assert response["status"] == "candidate"


def test_forecast_run_service_lists_runs_with_pagination() -> None:
    repository = FakeForecastRunRepository()
    service = ForecastRunService(repository)

    response = service.list_forecast_runs_response(
        status="candidate",
        model_version="baseline-moving-average-v1",
        feature_dataset_id="dataset-1",
        limit=10,
        offset=5,
    )

    assert response["pagination"] == {"limit": 10, "offset": 5, "total": 1}
    assert response["items"][0]["run_key"] == "baseline-moving-average-v1:dataset-1"
    assert repository.list_kwargs["status"] == "candidate"
    assert repository.count_kwargs["feature_dataset_id"] == "dataset-1"
