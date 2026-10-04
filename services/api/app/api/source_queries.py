"""Versioned query names match legacy reads; scope fields are explicitly required."""

from datetime import date, datetime, timedelta
from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.api.forecasts import ForecastSortBy
from app.api.inventory import InventorySortBy
from app.api.products import ProductSortBy
from app.api.sales import SaleSortBy, SortOrder
from app.api.stock_risks import RiskStatus, StockRiskSortBy
from app.domain.models import (
    Channel,
    Currency,
    ForecastMethod,
    ForecastStatus,
    ProductStatus,
    UnitOfMeasure,
)


class SourceQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product_id: UUID
    limit: Annotated[int, Field(ge=1, le=100)] = 50
    offset: Annotated[int, Field(ge=0, le=10000)] = 0
    sort_order: SortOrder = SortOrder.asc


def check_period(start: date | None, end: date | None) -> None:
    if isinstance(start, datetime) and start.tzinfo is None:
        message = "aware_timestamp_required"
        raise ValueError(message)
    if isinstance(end, datetime) and end.tzinfo is None:
        message = "aware_timestamp_required"
        raise ValueError(message)
    if (start is None) != (end is None):
        message = "both_period_bounds_required"
        raise ValueError(message)
    if start is not None and end is not None and (end < start or end - start > timedelta(days=90)):
        message = "period_outside_90_day_bound"
        raise ValueError(message)


class ProductsQuery(SourceQuery):
    category: str | None = Field(default=None, max_length=120)
    status: ProductStatus | None = None
    search: str | None = Field(default=None, min_length=1, max_length=200)
    sort_by: ProductSortBy = ProductSortBy.sku


class SalesQuery(SourceQuery):
    channel: Channel
    currency: Currency | None = None
    sold_from: datetime
    sold_to: datetime
    sort_by: SaleSortBy = SaleSortBy.sold_at
    sort_order: SortOrder = SortOrder.desc

    @model_validator(mode="after")
    def period(self) -> Self:
        check_period(self.sold_from, self.sold_to)
        return self


class InventoryQuery(SourceQuery):
    warehouse_code: str = Field(min_length=1, max_length=20)
    unit_of_measure: UnitOfMeasure | None = None
    recorded_from: datetime
    recorded_to: datetime
    sort_by: InventorySortBy = InventorySortBy.recorded_at
    sort_order: SortOrder = SortOrder.desc

    @model_validator(mode="after")
    def period(self) -> Self:
        check_period(self.recorded_from, self.recorded_to)
        return self


class ForecastsQuery(SourceQuery):
    status: ForecastStatus | None = None
    method: ForecastMethod | None = None
    date_from: date
    date_to: date
    sort_by: ForecastSortBy = ForecastSortBy.forecast_period_start

    @model_validator(mode="after")
    def period(self) -> Self:
        check_period(self.date_from, self.date_to)
        return self


class RisksQuery(SourceQuery):
    risk_status: RiskStatus | None = None
    category: str | None = Field(default=None, min_length=1, max_length=120)
    sort_by: StockRiskSortBy = StockRiskSortBy.risk_status
