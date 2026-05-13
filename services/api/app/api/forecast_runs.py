from enum import Enum
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path, Query, status

from app.api.schemas import (
    ForecastRunListResponse,
    ForecastRunRequest,
    ForecastRunResponse,
)
from app.domain.models import ForecastRunStatus
from app.services.forecast_run_service import ForecastRunService

router = APIRouter(prefix="/forecast-runs", tags=["forecast-runs"])
forecast_run_service = ForecastRunService()


class ForecastRunSortBy(str, Enum):
    completed_at = "completed_at"
    started_at = "started_at"
    model_version = "model_version"
    status = "status"
    created_at = "created_at"


class SortOrder(str, Enum):
    asc = "asc"
    desc = "desc"


@router.post(
    "",
    response_model=ForecastRunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Persist forecast run metadata",
    description=(
        "Stores run-level metadata for local MLOps forecasting jobs. "
        "The operation is idempotent by run_key."
    ),
)
def persist_forecast_run(payload: ForecastRunRequest) -> dict:
    return forecast_run_service.persist_forecast_run(payload.model_dump())


@router.get(
    "",
    response_model=ForecastRunListResponse,
    status_code=status.HTTP_200_OK,
    summary="List forecast runs",
)
def list_forecast_runs(
    status_filter: Annotated[
        ForecastRunStatus | None,
        Query(alias="status", description="Filter by forecast run status."),
    ] = None,
    model_version: Annotated[
        str | None,
        Query(description="Filter by model version."),
    ] = None,
    feature_dataset_id: Annotated[
        str | None,
        Query(description="Filter by feature dataset identifier."),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    sort_by: Annotated[ForecastRunSortBy, Query(description="Sort field.")] = (
        ForecastRunSortBy.completed_at
    ),
    sort_order: Annotated[SortOrder, Query(description="Sort direction.")] = SortOrder.desc,
) -> dict:
    return forecast_run_service.list_forecast_runs_response(
        status=status_filter.value if status_filter else None,
        model_version=model_version,
        feature_dataset_id=feature_dataset_id,
        limit=limit,
        offset=offset,
        sort_by=sort_by.value,
        sort_order=sort_order.value,
    )


@router.get(
    "/{forecast_run_id}",
    response_model=ForecastRunResponse,
    status_code=status.HTTP_200_OK,
    summary="Get forecast run details",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Forecast run was not found.",
        },
    },
)
def get_forecast_run(
    forecast_run_id: Annotated[UUID, Path(description="Forecast run identifier.")],
) -> dict:
    forecast_run = forecast_run_service.get_forecast_run_response(forecast_run_id)

    if forecast_run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resource not found",
        )

    return forecast_run
