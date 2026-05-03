"""Shared API response schemas for RetailOps endpoints.

The goal of this module is to make list/detail responses predictable for
frontend, tests, OpenAPI docs and future clients.
"""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ApiBaseModel(BaseModel):
    """Base API schema with a strict public response contract."""

    model_config = ConfigDict(extra="forbid")


class PaginationMetadata(ApiBaseModel):
    """Pagination metadata returned with every list response."""

    limit: int = Field(..., ge=1, json_schema_extra={"example": 50})
    offset: int = Field(..., ge=0, json_schema_extra={"example": 0})
    total: int = Field(..., ge=0, json_schema_extra={"example": 125})


class ProductResponse(ApiBaseModel):
    """Stable public representation of a Product."""

    id: UUID
    sku: str
    name: str
    category: str | None = None
    brand: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime


class ProductListResponse(ApiBaseModel):
    """Stable list response for Product endpoints."""

    items: list[ProductResponse]
    pagination: PaginationMetadata


class ForecastResponse(ApiBaseModel):
    """Stable public representation of a Forecast."""

    id: UUID
    product_id: UUID
    forecast_period_start: date
    forecast_period_end: date
    predicted_quantity: float = Field(..., ge=0)
    unit_of_measure: str
    generated_at: datetime
    method: str
    status: str
    confidence_level: float = Field(..., ge=0, le=1)


class ForecastListResponse(ApiBaseModel):
    """Stable list response for Forecast endpoints."""

    items: list[ForecastResponse]
    pagination: PaginationMetadata


class InventorySnapshotResponse(ApiBaseModel):
    """Stable public representation of an inventory snapshot."""

    id: UUID
    product_id: UUID
    stock_quantity: int = Field(..., ge=0)
    unit_of_measure: str
    warehouse_code: str
    recorded_at: datetime
    ingested_at: datetime
    created_at: datetime


class InventorySnapshotListResponse(ApiBaseModel):
    """Stable list response for inventory snapshot endpoints."""

    items: list[InventorySnapshotResponse]
    pagination: PaginationMetadata


class SaleResponse(ApiBaseModel):
    """Stable public representation of a sales record."""

    id: UUID
    product_id: UUID
    quantity: int = Field(..., gt=0)
    sold_at: datetime
    unit_price: float = Field(..., ge=0)
    total_amount: float = Field(..., ge=0)
    currency: str
    channel: str | None = None
    created_at: datetime


class SaleListResponse(ApiBaseModel):
    """Stable list response for sales endpoints."""

    items: list[SaleResponse]
    pagination: PaginationMetadata


class StockRiskResponse(ApiBaseModel):
    """Stable public representation of product-level stock risk."""

    product_id: UUID
    sku: str | None = None
    name: str | None = None
    category: str | None = None
    current_stock: float | None = None
    forecast_quantity: float | None = None
    risk_status: str
    inventory_updated_at: datetime | None = None


class StockRiskListResponse(ApiBaseModel):
    """Stable list response for stock-risk endpoints."""

    items: list[StockRiskResponse]
    pagination: PaginationMetadata
