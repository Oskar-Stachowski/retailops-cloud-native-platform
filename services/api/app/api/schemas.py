"""Shared API response schemas for RetailOps endpoints.

The goal of this module is to make list/detail responses predictable for
frontend, tests, OpenAPI docs and future clients.
"""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ApiBaseModel(BaseModel):
    """Base API schema with a strict response contract."""

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
