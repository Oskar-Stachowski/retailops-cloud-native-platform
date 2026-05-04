"""Shared API response schemas for RetailOps endpoints.

The goal of this module is to make list/detail and dashboard responses
predictable for frontend, tests, OpenAPI docs and future clients.
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


class DashboardSummary(ApiBaseModel):
    """Top-level operational counters used by the RetailOps dashboard."""

    products_count: int = Field(..., ge=0)
    sales_count: int = Field(..., ge=0)
    inventory_snapshots_count: int = Field(..., ge=0)
    forecasts_count: int = Field(..., ge=0)
    anomalies_count: int = Field(..., ge=0)
    recommendations_count: int = Field(..., ge=0)
    open_anomalies_count: int = Field(..., ge=0)
    open_recommendations_count: int = Field(..., ge=0)
    open_work_items_count: int = Field(..., ge=0)
    last_refresh_at: datetime | None = None


class DashboardSummaryResponse(ApiBaseModel):
    """Response for GET /dashboard/summary."""

    summary: DashboardSummary


class DashboardSalesTrendItem(ApiBaseModel):
    """One point in the dashboard sales trend chart."""

    date: date
    units_sold: float = Field(..., ge=0)
    revenue: float = Field(..., ge=0)


class DashboardSalesTrendResponse(ApiBaseModel):
    """Response for GET /dashboard/sales-trend."""

    items: list[DashboardSalesTrendItem]
    days: int = Field(..., ge=1, le=90)


class DashboardWorkItem(ApiBaseModel):
    """Small operational work item for dashboard widgets."""

    id: str
    source: str
    product_id: str | None = None
    sku: str | None = None
    type: str | None = None
    severity: str | None = None
    priority: str | None = None
    status: str | None = None
    title: str | None = None
    description: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    detected_at: datetime | None = None


class DashboardWorkItemsResponse(ApiBaseModel):
    """Response for open dashboard work item widgets."""

    items: list[DashboardWorkItem]
    limit: int = Field(..., ge=1, le=100)


class DashboardRecommendationResponse(ApiBaseModel):
    """Response for top dashboard recommendations."""

    items: list[DashboardWorkItem]
    limit: int = Field(..., ge=1, le=100)


class DashboardStockRiskSummary(ApiBaseModel):
    """Aggregated stock-risk counters for operational visibility."""

    total_risk_items: int = Field(..., ge=0)
    normal_count: int = Field(..., ge=0)
    stockout_risk_count: int = Field(..., ge=0)
    overstock_risk_count: int = Field(..., ge=0)
    unknown_count: int = Field(..., ge=0)


class DashboardOperationalVisibilityResponse(ApiBaseModel):
    """Composite dashboard response for operations-oriented overview screens."""

    generated_at: datetime
    summary: DashboardSummary
    stock_risk_summary: DashboardStockRiskSummary
    sales_trend: list[DashboardSalesTrendItem]
    open_work_items: list[DashboardWorkItem]
    limits: dict[str, int]


class Product360Metrics(ApiBaseModel):
    """Aggregated product-level counters for Product 360."""

    sales_count: int = Field(..., ge=0)
    total_units_sold: float = Field(..., ge=0)
    total_revenue: float = Field(..., ge=0)
    latest_sale_at: datetime | None = None
    inventory_snapshot_count: int = Field(..., ge=0)
    current_stock: float | None = Field(default=None, ge=0)
    inventory_updated_at: datetime | None = None
    forecast_count: int = Field(..., ge=0)
    latest_forecast_quantity: float | None = Field(default=None, ge=0)
    latest_forecast_period_start: date | None = None
    latest_forecast_period_end: date | None = None
    anomaly_count: int = Field(..., ge=0)
    alert_count: int = Field(..., ge=0)
    open_alert_count: int = Field(..., ge=0)
    recommendation_count: int = Field(..., ge=0)
    open_recommendation_count: int = Field(..., ge=0)
    workflow_action_count: int = Field(..., ge=0)
    risk_status: str


class Product360Anomaly(ApiBaseModel):
    """Anomaly row shown inside a Product 360 view."""

    id: UUID
    product_id: UUID
    anomaly_type: str
    metric_name: str
    actual_value: float
    expected_value: float
    deviation_percent: float
    impact_value: float
    impact_unit: str
    severity: str
    period_start: datetime
    period_end: datetime
    detected_at: datetime


class Product360Alert(ApiBaseModel):
    """Operational alert linked to a product."""

    id: UUID
    product_id: UUID
    anomaly_id: UUID | None = None
    assigned_to_user_id: UUID | None = None
    alert_type: str
    severity: str
    status: str
    title: str
    recommended_action: str
    created_at: datetime
    updated_at: datetime


class Product360Recommendation(ApiBaseModel):
    """Recommended product-level action."""

    id: UUID
    product_id: UUID
    forecast_id: UUID | None = None
    anomaly_id: UUID | None = None
    alert_id: UUID | None = None
    recommendation_type: str
    recommended_action: str
    rationale: str
    status: str
    generated_at: datetime
    expires_at: datetime | None = None
    created_at: datetime


class Product360WorkflowAction(ApiBaseModel):
    """Workflow audit event linked through a product alert."""

    id: UUID
    alert_id: UUID
    performed_by_user_id: UUID
    action_type: str
    comment: str | None = None
    previous_status: str | None = None
    new_status: str | None = None
    performed_at: datetime | None = None
    created_at: datetime
    alert_title: str | None = None
    performed_by_login: str | None = None


class Product360Response(ApiBaseModel):
    """Composite response for GET /products/{product_id}/360."""

    product: ProductResponse
    metrics: Product360Metrics
    stock_risk: StockRiskResponse | None = None
    sales: list[SaleResponse]
    inventory_snapshots: list[InventorySnapshotResponse]
    forecasts: list[ForecastResponse]
    anomalies: list[Product360Anomaly]
    alerts: list[Product360Alert]
    recommendations: list[Product360Recommendation]
    workflow_actions: list[Product360WorkflowAction]
    limits: dict[str, int]
