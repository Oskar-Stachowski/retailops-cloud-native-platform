"""Shared API response schemas for RetailOps endpoints.

The goal of this module is to make list/detail and dashboard responses
predictable for frontend, tests, OpenAPI docs and future clients.
"""

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.workflow import (
    WorkflowActionName,
    WorkflowEntityType,
    WorkflowTransitionError,
    validate_workflow_transition,
)

ALERT_WORKFLOW_ACTIONS = frozenset(
    {
        WorkflowActionName.acknowledge,
        WorkflowActionName.assign,
        WorkflowActionName.resolve,
        WorkflowActionName.dismiss,
        WorkflowActionName.comment,
    },
)

RECOMMENDATION_WORKFLOW_ACTIONS = frozenset(
    {
        WorkflowActionName.accept,
        WorkflowActionName.reject,
        WorkflowActionName.assign,
        WorkflowActionName.resolve,
        WorkflowActionName.dismiss,
        WorkflowActionName.comment,
    },
)


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


class ForecastRunRequest(ApiBaseModel):
    """Request body for persisting forecast model run metadata."""

    run_key: str = Field(..., min_length=1, max_length=200)
    model_name: str = Field(..., min_length=1, max_length=120)
    model_version: str = Field(..., min_length=1, max_length=120)
    model_type: str = Field(..., min_length=1, max_length=80)
    status: str
    profile: str = Field(..., min_length=1, max_length=40)
    seed: int
    feature_dataset_name: str = Field(..., min_length=1, max_length=160)
    feature_dataset_id: str = Field(..., min_length=1, max_length=240)
    feature_grain: list[str]
    target: str = Field(..., min_length=1, max_length=80)
    window_days: int = Field(..., gt=0)
    horizon_days: int = Field(..., gt=0)
    holdout_days: int | None = Field(default=None, gt=0)
    feature_row_count: int = Field(..., ge=0)
    forecast_row_count: int = Field(..., ge=0)
    evaluated_rows: int | None = Field(default=None, ge=0)
    skipped_rows: int | None = Field(default=None, ge=0)
    metrics: dict[str, Any] = Field(default_factory=dict)
    artifacts: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime
    completed_at: datetime


class ForecastRunResponse(ForecastRunRequest):
    """Stable public representation of a forecast run."""

    id: UUID
    created_at: datetime
    updated_at: datetime


class ForecastRunListResponse(ApiBaseModel):
    """Stable list response for forecast run endpoints."""

    items: list[ForecastRunResponse]
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


class DashboardLiveMetricValue(ApiBaseModel):
    """Raw live metric value with observation metadata."""

    value: float
    observation_count: int = Field(..., ge=0)
    latest_observed_at: datetime | None = None


class DashboardLiveMetrics(ApiBaseModel):
    """Normalized live operational counters for the selected window."""

    revenue: float = Field(..., ge=0)
    units_sold: float = Field(..., ge=0)
    orders_created: float = Field(..., ge=0)
    sales_events: float = Field(..., ge=0)
    return_amount: float = Field(..., ge=0)
    return_units: float = Field(..., ge=0)
    stock_delta: float
    stock_events: float = Field(..., ge=0)
    replenishment_units: float = Field(..., ge=0)
    anomalies_detected: float = Field(..., ge=0)
    alerts_created: float = Field(..., ge=0)
    workflow_actions: float = Field(..., ge=0)
    raw_metrics: dict[str, DashboardLiveMetricValue]


class DashboardLiveEventStatusCounts(ApiBaseModel):
    """Event processing counters for the selected live window."""

    received: int = Field(..., ge=0)
    processed: int = Field(..., ge=0)
    failed_dead_lettered: int = Field(..., ge=0)
    ignored_duplicate: int = Field(..., ge=0)
    total: int = Field(..., ge=0)


class DashboardLiveFreshness(ApiBaseModel):
    """Freshness metadata for the real-time event stream."""

    latest_event_at: datetime | None = None
    freshness_seconds: float | None = Field(default=None, ge=0)
    is_fresh: bool


class DashboardLiveEvent(ApiBaseModel):
    """Recent processed event shown in live operations views."""

    event_id: str
    event_type: str | None = None
    topic: str | None = None
    status: str | None = None
    occurred_at: datetime | None = None
    ingested_at: datetime | None = None
    processed_at: datetime | None = None
    error_message: str | None = None


class DashboardLiveAlert(ApiBaseModel):
    """Recent alert-like event from the real-time stream."""

    event_id: str
    event_type: str | None = None
    status: str | None = None
    occurred_at: datetime | None = None
    ingested_at: datetime | None = None
    product_id: str | None = None
    severity: str | None = None
    title: str | None = None
    payload: dict[str, Any]


class DashboardLiveConsumerState(ApiBaseModel):
    """Persisted consumer state for live operations monitoring."""

    consumer_name: str
    running: bool
    received_events: int = Field(..., ge=0)
    processed_events: int = Field(..., ge=0)
    failed_events: int = Field(..., ge=0)
    dead_lettered_events: int = Field(..., ge=0)
    ignored_events: int = Field(..., ge=0)
    last_event_id: str | None = None
    last_event_type: str | None = None
    last_error: str | None = None
    last_processed_at: datetime | None = None
    started_at: datetime | None = None
    stopped_at: datetime | None = None
    updated_at: datetime | None = None


class DashboardLiveOperationsResponse(ApiBaseModel):
    """Composite live operations response backed by real-time metrics tables."""

    generated_at: datetime
    window_minutes: int = Field(..., ge=1, le=240)
    metrics: DashboardLiveMetrics
    event_status_counts: DashboardLiveEventStatusCounts
    freshness: DashboardLiveFreshness
    recent_events: list[DashboardLiveEvent]
    alerts: list[DashboardLiveAlert]
    consumer_states: list[DashboardLiveConsumerState]
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


class WorkflowMutationRequest(ApiBaseModel):
    """Base request body for endpoint-specific workflow mutations."""

    comment: str | None = Field(
        default=None,
        min_length=5,
        max_length=1000,
        description="Decision comment. Required for reject and dismiss actions.",
    )
    assigned_to_user_id: UUID | None = Field(
        default=None,
        description="Target user for assign actions.",
    )
    idempotency_key: str | None = Field(
        default=None,
        min_length=8,
        max_length=120,
        description="Optional client-supplied key for safe retries.",
    )


class AlertWorkflowMutationRequest(WorkflowMutationRequest):
    """Request body for alert workflow action endpoints."""

    action: WorkflowActionName = Field(
        ...,
        description="Workflow action requested for an alert.",
    )

    @model_validator(mode="after")
    def validate_alert_action_request(self) -> "AlertWorkflowMutationRequest":
        if self.action not in ALERT_WORKFLOW_ACTIONS:
            msg = f"{self.action.value} is not a supported alert action."
            raise ValueError(msg)

        if self.action == WorkflowActionName.assign and not self.assigned_to_user_id:
            msg = "assigned_to_user_id is required for assign actions."
            raise ValueError(msg)

        if self.action == WorkflowActionName.dismiss and not self.comment:
            msg = "comment is required for dismiss actions."
            raise ValueError(msg)

        return self


class RecommendationWorkflowMutationRequest(WorkflowMutationRequest):
    """Request body for recommendation decision endpoints."""

    action: WorkflowActionName = Field(
        ...,
        description="Workflow action requested for a recommendation.",
    )

    @model_validator(mode="after")
    def validate_recommendation_action_request(
        self,
    ) -> "RecommendationWorkflowMutationRequest":
        if self.action not in RECOMMENDATION_WORKFLOW_ACTIONS:
            msg = f"{self.action.value} is not a supported recommendation action."
            raise ValueError(msg)

        if self.action == WorkflowActionName.assign and not self.assigned_to_user_id:
            msg = "assigned_to_user_id is required for assign actions."
            raise ValueError(msg)

        if (
            self.action
            in {
                WorkflowActionName.reject,
                WorkflowActionName.dismiss,
            }
            and not self.comment
        ):
            msg = f"comment is required for {self.action.value} actions."
            raise ValueError(msg)

        return self


class WorkflowActionCreateRequest(WorkflowMutationRequest):
    """Generic request body for POST /workflow-actions."""

    entity_type: WorkflowEntityType
    entity_id: UUID
    action: WorkflowActionName
    previous_status: str = Field(..., min_length=1, max_length=30)
    new_status: str = Field(..., min_length=1, max_length=30)

    @model_validator(mode="after")
    def validate_transition(self) -> "WorkflowActionCreateRequest":
        if self.action == WorkflowActionName.assign and not self.assigned_to_user_id:
            msg = "assigned_to_user_id is required for assign actions."
            raise ValueError(msg)

        try:
            validate_workflow_transition(
                entity_type=self.entity_type,
                action=self.action,
                previous_status=self.previous_status,
                new_status=self.new_status,
                comment=self.comment,
            )
        except WorkflowTransitionError as exc:
            raise ValueError(str(exc)) from exc

        return self


class WorkflowActionResponse(ApiBaseModel):
    """Public representation of a persisted workflow decision/audit event."""

    id: UUID
    audit_log_id: UUID | None = None
    entity_type: str
    entity_id: UUID
    action: str
    previous_status: str
    new_status: str
    performed_by_user_id: UUID
    assigned_to_user_id: UUID | None = None
    comment: str | None = None
    performed_at: datetime
    idempotency_key: str | None = None


class WorkflowMutationResponse(ApiBaseModel):
    """Response returned by workflow mutation endpoints."""

    workflow_action: WorkflowActionResponse
    status: str
    message: str


class DemoUserResponse(ApiBaseModel):
    """Public mock identity used by Sprint 7 role-aware UI."""

    id: str
    login: str
    display_name: str
    email: str
    role: str
    team: str
    business_area: str
    permissions: list[str]


class DemoUserListResponse(ApiBaseModel):
    """Selectable local users used by the frontend demo switcher."""

    items: list[DemoUserResponse]
    default_user_id: str


class CurrentUserResponse(ApiBaseModel):
    """Response for GET /me."""

    user: DemoUserResponse
    auth_mode: str
    scope_boundary: str


class PermissionListResponse(ApiBaseModel):
    """Response for GET /me/permissions."""

    user_id: str
    role: str
    permissions: list[str]


class NotificationResponse(ApiBaseModel):
    """Local mock notification visible to a demo user."""

    id: str
    title: str
    message: str
    category: str
    severity: str
    status: str
    target_role: str
    action_url: str | None = None
    created_at: datetime
    read_at: datetime | None = None


class NotificationListResponse(ApiBaseModel):
    """Response for GET /notifications."""

    items: list[NotificationResponse]
    pagination: PaginationMetadata
    unread_count: int = Field(..., ge=0)
    total_count: int = Field(..., ge=0)
    user: DemoUserResponse


class NotificationReadResponse(ApiBaseModel):
    """Response for POST /notifications/{notification_id}/read."""

    notification: NotificationResponse
    unread_count: int = Field(..., ge=0)
