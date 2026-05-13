from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from app.domain.models import ForecastRun, ForecastRunStatus
from app.repositories.forecast_run_repository import ForecastRunRepository


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
        metrics={"mae": "2.0000", "rmse": "3.0000"},
        artifacts={"model_manifest": "model_manifest.json"},
        started_at=now,
        completed_at=now,
        created_at=now,
        updated_at=now,
    )


class RecordingForecastRunRepository(ForecastRunRepository):
    def __init__(self, returned_run: ForecastRun) -> None:
        super().__init__(connection=None)
        self.returned_run = returned_run
        self.executed_query = ""
        self.executed_params = ()
        self.fetch_all_query = ""
        self.fetch_all_params = ()

    def _execute_one(self, query: str, params: tuple) -> dict:
        self.executed_query = query
        self.executed_params = params
        return self.returned_run.model_dump()

    def _fetch_one(self, query: str, params: tuple = ()) -> dict | None:
        self.executed_query = query
        self.executed_params = params
        return self.returned_run.model_dump()

    def _fetch_all(self, query: str, params: tuple = ()) -> list[dict]:
        self.fetch_all_query = query
        self.fetch_all_params = params
        return [self.returned_run.model_dump()]


def test_forecast_run_repository_upserts_run_by_key() -> None:
    forecast_run = make_forecast_run()
    repository = RecordingForecastRunRepository(forecast_run)

    persisted = repository.upsert_forecast_run(forecast_run)

    assert persisted == forecast_run
    assert "ON CONFLICT (run_key)" in repository.executed_query
    assert forecast_run.run_key in repository.executed_params
    assert forecast_run.window_days in repository.executed_params


def test_forecast_run_repository_gets_run_by_key() -> None:
    forecast_run = make_forecast_run()
    repository = RecordingForecastRunRepository(forecast_run)

    result = repository.get_forecast_run_by_key(forecast_run.run_key)

    assert result == forecast_run
    assert "WHERE run_key = %s" in repository.executed_query
    assert repository.executed_params == (forecast_run.run_key,)


def test_forecast_run_repository_lists_runs_with_filters() -> None:
    forecast_run = make_forecast_run()
    repository = RecordingForecastRunRepository(forecast_run)

    results = repository.list_forecast_runs(
        status="candidate",
        model_version="baseline-moving-average-v1",
        feature_dataset_id="dataset-1",
        limit=10,
        offset=5,
    )

    assert results == [forecast_run]
    assert "status = %s" in repository.fetch_all_query
    assert "model_version = %s" in repository.fetch_all_query
    assert "feature_dataset_id = %s" in repository.fetch_all_query
    assert repository.fetch_all_params == (
        "candidate",
        "baseline-moving-average-v1",
        "dataset-1",
        10,
        5,
    )
