from __future__ import annotations

from typing import TYPE_CHECKING

from app.domain.models import ForecastRun
from app.repositories.forecast_run_repository import ForecastRunRepository
from app.services.serialization import make_json_safe

if TYPE_CHECKING:
    from uuid import UUID


class ForecastRunService:
    """Application service for forecast run persistence."""

    def __init__(
        self,
        forecast_run_repository: ForecastRunRepository | None = None,
    ) -> None:
        self.forecast_run_repository = forecast_run_repository or ForecastRunRepository()

    def persist_forecast_run(self, payload: dict) -> dict:
        forecast_run = ForecastRun(**payload)
        persisted = self.forecast_run_repository.upsert_forecast_run(forecast_run)
        return make_json_safe(persisted.model_dump())

    def get_forecast_run_response(self, forecast_run_id: UUID) -> dict | None:
        forecast_run = self.forecast_run_repository.get_forecast_run_by_id(forecast_run_id)
        if forecast_run is None:
            return None
        return make_json_safe(forecast_run.model_dump())

    def list_forecast_runs_response(
        self,
        *,
        status: str | None = None,
        model_version: str | None = None,
        feature_dataset_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "completed_at",
        sort_order: str = "desc",
    ) -> dict:
        forecast_runs = self.forecast_run_repository.list_forecast_runs(
            status=status,
            model_version=model_version,
            feature_dataset_id=feature_dataset_id,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        total = self.forecast_run_repository.count_forecast_runs(
            status=status,
            model_version=model_version,
            feature_dataset_id=feature_dataset_id,
        )
        return {
            "items": [make_json_safe(forecast_run.model_dump()) for forecast_run in forecast_runs],
            "pagination": {
                "limit": limit,
                "offset": offset,
                "total": total,
            },
        }
