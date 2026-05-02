from datetime import date
from enum import Enum
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path, Query, status

from app.api.schemas import ForecastListResponse, ForecastResponse
from app.domain.models import ForecastMethod, ForecastStatus
from app.services.forecast_service import ForecastService


router = APIRouter(prefix="/forecasts", tags=["forecasts"])
forecast_service = ForecastService()


class ForecastSortBy(str, Enum):
    forecast_period_start = "forecast_period_start"
    forecast_period_end = "forecast_period_end"
    generated_at = "generated_at"
    predicted_quantity = "predicted_quantity"
    confidence_level = "confidence_level"


class SortOrder(str, Enum):
    asc = "asc"
    desc = "desc"


@router.get(
    "",
    response_model=ForecastListResponse,
    status_code=status.HTTP_200_OK,
    summary="List forecasts",
    description=(
        "Returns forecasts using a stable list response contract with "
        "items and pagination metadata. Supports MVP product/status/method/date filters."
    ),
)
def list_forecasts(
    product_id: Annotated[
        UUID | None,
        Query(description="Filter forecasts for one product."),
    ] = None,
    status_filter: Annotated[
        ForecastStatus | None,
        Query(alias="status", description="Filter by forecast status."),
    ] = None,
    method: Annotated[
        ForecastMethod | None,
        Query(description="Filter by forecasting method."),
    ] = None,
    date_from: Annotated[
        date | None,
        Query(description="Filter periods starting on or after this date."),
    ] = None,
    date_to: Annotated[
        date | None,
        Query(description="Filter periods ending on or before this date."),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    sort_by: Annotated[ForecastSortBy, Query(description="Sort field.")] = (
        ForecastSortBy.forecast_period_start
    ),
    sort_order: Annotated[SortOrder, Query(description="Sort direction.")] = SortOrder.asc,
) -> dict:
    return forecast_service.list_forecasts_response(
        product_id=product_id,
        status=status_filter.value if status_filter else None,
        method=method.value if method else None,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
        sort_by=sort_by.value,
        sort_order=sort_order.value,
    )


@router.get(
    "/{forecast_id}",
    response_model=ForecastResponse,
    status_code=status.HTTP_200_OK,
    summary="Get forecast details",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Forecast was not found.",
        }
    },
)
def get_forecast(
    forecast_id: Annotated[UUID, Path(description="Forecast technical identifier.")]
) -> dict:
    forecast = forecast_service.get_forecast_detail_response(forecast_id)

    if forecast is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    return forecast
