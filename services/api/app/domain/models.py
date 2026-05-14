from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum
from typing import Self
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.workflow import (
    WorkflowEntityType,
    WorkflowTransitionError,
    validate_workflow_transition,
)


class RetailOpsBaseModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


# Product
class ProductStatus(str, Enum):
    draft = "draft"
    active = "active"
    discontinued = "discontinued"


class Product(RetailOpsBaseModel):
    id: UUID = Field(default_factory=uuid4)
    sku: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    category: str | None = None
    brand: str | None = None
    status: ProductStatus = ProductStatus.active

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime

    @model_validator(mode="after")
    def validate_dates(self) -> Self:
        if not (self.created_at <= self.updated_at):
            msg = "Invalid time order"
            raise ValueError(msg)
        return self


# Sale
class Currency(str, Enum):
    PLN = "PLN"
    EUR = "EUR"
    USD = "USD"


class Channel(str, Enum):
    online = "online"
    store = "store"
    marketplace = "marketplace"
    wholesale = "wholesale"


class Sale(RetailOpsBaseModel):
    id: UUID = Field(default_factory=uuid4)
    product_id: UUID
    quantity: int = Field(..., gt=0)
    sold_at: datetime = Field(...)
    unit_price: Decimal = Field(..., ge=0)
    total_amount: Decimal = Field(..., ge=0)
    currency: Currency = Currency.PLN
    channel: Channel | None = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def validate_dates(self) -> Self:
        if not (self.sold_at <= self.created_at):
            msg = "Invalid time order"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def validate_total_amount(self) -> Self:
        expected_total = (self.quantity * self.unit_price).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )
        actual_total = self.total_amount.quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

        if actual_total != expected_total:
            msg = (
                f"total_amount must equal quantity * unit_price. "
                f"Expected {expected_total}, got {self.total_amount}."
            )
            raise ValueError(
                msg,
            )

        return self


# InventorySnapshot
class UnitOfMeasure(str, Enum):
    pcs = "pcs"
    kg = "kg"
    liter = "l"
    m = "m"
    m2 = "m2"


class InventorySnapshot(RetailOpsBaseModel):
    id: UUID = Field(default_factory=uuid4)
    product_id: UUID
    stock_quantity: int = Field(..., ge=0)
    unit_of_measure: UnitOfMeasure
    warehouse_code: str = Field(..., min_length=1, max_length=20)

    recorded_at: datetime = Field(...)
    ingested_at: datetime = Field(...)
    created_at: datetime = Field(...)

    @model_validator(mode="after")
    def validate_dates(self) -> Self:
        if not (self.recorded_at <= self.ingested_at <= self.created_at):
            msg = "Invalid time order"
            raise ValueError(msg)
        if self.created_at > datetime.now(UTC):
            msg = "Date cannot be in the future"
            raise ValueError(msg)
        return self


# User
class Role(str, Enum):
    inventory_planner = "inventory_planner"
    category_manager = "category_manager"
    analyst = "analyst"
    admin = "admin"


class UserStatus(str, Enum):
    active = "active"
    inactive = "inactive"


class User(RetailOpsBaseModel):
    id: UUID = Field(default_factory=uuid4)
    login: str = Field(..., min_length=5, max_length=20)
    display_name: str | None = None
    role: Role
    team: str | None = None
    status: UserStatus = UserStatus.inactive

    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def validate_dates(self) -> Self:
        if not (self.created_at <= self.updated_at):
            msg = "Invalid time order"
            raise ValueError(msg)
        return self


# Alert
class AlertType(str, Enum):
    stockout_risk = "stockout_risk"
    overstock_risk = "overstock_risk"
    sales_drop = "sales_drop"
    stale_inventory = "stale_inventory"


class Severity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class AlertStatus(str, Enum):
    open = "open"
    acknowledged = "acknowledged"
    in_progress = "in_progress"
    resolved = "resolved"
    dismissed = "dismissed"


class Alert(RetailOpsBaseModel):
    id: UUID = Field(default_factory=uuid4)
    product_id: UUID
    anomaly_id: UUID | None = None
    assigned_to_user_id: UUID | None = None
    alert_type: AlertType
    severity: Severity
    status: AlertStatus = AlertStatus.open
    title: str = Field(..., min_length=5, max_length=300)
    recommended_action: str = Field(..., min_length=5, max_length=300)

    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def validate_dates(self) -> Self:
        if not (self.created_at <= self.updated_at):
            msg = "Invalid time order"
            raise ValueError(msg)
        return self


# WorkflowAction
class WorkflowActionType(str, Enum):
    ACKNOWLEDGE = "acknowledge"
    ASSIGN = "assign"
    ACCEPT = "accept"
    REJECT = "reject"
    ESCALATE = "escalate"
    DISMISS = "dismiss"
    RESOLVE = "resolve"
    REOPEN = "reopen"
    COMMENT = "comment"


class WorkflowAction(RetailOpsBaseModel):
    id: UUID = Field(default_factory=uuid4)

    alert_id: UUID
    performed_by_user_id: UUID

    action_type: WorkflowActionType

    comment: str | None = Field(
        default=None,
        min_length=5,
        max_length=300,
        description=("Optional decision comment. Required for dismiss and reject actions."),
    )

    previous_status: AlertStatus = Field(...)
    new_status: AlertStatus = Field(...)

    performed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def validate_action_requirements(self) -> "WorkflowAction":
        try:
            validate_workflow_transition(
                entity_type=WorkflowEntityType.alert,
                action=self.action_type,
                previous_status=self.previous_status,
                new_status=self.new_status,
                comment=self.comment,
            )
        except WorkflowTransitionError as exc:
            raise ValueError(str(exc)) from exc

        return self


# Anomaly
class AnomalyType(str, Enum):
    sales_drop = "sales_drop"
    sales_spike = "sales_spike"
    stale_inventory = "stale_inventory"
    pricing_issue = "pricing_issue"


class ImpactUnit(str, Enum):
    PLN = "PLN"
    pcs = "pcs"
    kg = "kg"
    liter = "l"
    m = "m"
    m2 = "m2"
    percent = "percent"


class Anomaly(RetailOpsBaseModel):
    id: UUID = Field(default_factory=uuid4)
    product_id: UUID
    anomaly_type: AnomalyType
    metric_name: str = Field(..., min_length=1)
    actual_value: float
    expected_value: float
    deviation_percent: float
    impact_value: float
    impact_unit: ImpactUnit
    severity: Severity

    period_start: datetime
    period_end: datetime
    detected_at: datetime

    @model_validator(mode="after")
    def validate_dates(self) -> Self:
        if not (self.period_start <= self.period_end):
            msg = "Invalid time order"
            raise ValueError(msg)
        if self.detected_at > datetime.now(UTC):
            msg = "Date cannot be in the future"
            raise ValueError(msg)
        return self


# Forecast
class ForecastMethod(str, Enum):
    moving_average = "moving_average"
    naive_baseline = "naive_baseline"
    seeded_demo = "seeded_demo"
    retailops_baseline_demand_model = "retailops-baseline-demand-model"
    retailops_realism_baseline_demand_model = "retailops-realism-baseline-demand-model"


class ForecastStatus(str, Enum):
    generated = "generated"
    evaluated = "evaluated"
    deprecated = "deprecated"


class Forecast(RetailOpsBaseModel):
    id: UUID = Field(default_factory=uuid4)
    product_id: UUID

    forecast_period_start: date = Field(...)
    forecast_period_end: date = Field(...)

    predicted_quantity: float = Field(..., ge=0)
    unit_of_measure: UnitOfMeasure

    generated_at: datetime

    method: ForecastMethod
    status: ForecastStatus = ForecastStatus.generated
    confidence_level: float = Field(..., ge=0, le=1)

    @model_validator(mode="after")
    def validate_dates(self) -> Self:
        if not (self.forecast_period_start <= self.forecast_period_end):
            msg = "Invalid time order"
            raise ValueError(msg)
        return self


class ForecastRunStatus(str, Enum):
    experimental = "experimental"
    candidate = "candidate"
    approved = "approved"
    rejected = "rejected"
    retraining_required = "retraining_required"
    failed = "failed"


class ForecastRun(RetailOpsBaseModel):
    id: UUID = Field(default_factory=uuid4)
    run_key: str = Field(..., min_length=1, max_length=200)
    model_name: str = Field(..., min_length=1, max_length=120)
    model_version: str = Field(..., min_length=1, max_length=120)
    model_type: str = Field(..., min_length=1, max_length=80)
    status: ForecastRunStatus = ForecastRunStatus.experimental
    profile: str = Field(..., min_length=1, max_length=40)
    seed: int

    feature_dataset_name: str = Field(..., min_length=1, max_length=160)
    feature_dataset_id: str = Field(..., min_length=1, max_length=240)
    feature_grain: list[str] = Field(default_factory=list)
    target: str = Field(..., min_length=1, max_length=80)

    window_days: int = Field(..., gt=0)
    horizon_days: int = Field(..., gt=0)
    holdout_days: int | None = Field(default=None, gt=0)

    feature_row_count: int = Field(..., ge=0)
    forecast_row_count: int = Field(..., ge=0)
    evaluated_rows: int | None = Field(default=None, ge=0)
    skipped_rows: int | None = Field(default=None, ge=0)

    metrics: dict[str, object] = Field(default_factory=dict)
    artifacts: dict[str, object] = Field(default_factory=dict)

    started_at: datetime
    completed_at: datetime
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def validate_dates(self) -> Self:
        if self.started_at > self.completed_at:
            msg = "Invalid time order"
            raise ValueError(msg)
        if self.created_at > self.updated_at:
            msg = "Invalid time order"
            raise ValueError(msg)
        return self


# Recommendation
class RecommendationType(str, Enum):
    replenish_stock = "replenish_stock"
    review_price = "review_price"
    investigate_sales_drop = "investigate_sales_drop"


class RecommendationStatus(str, Enum):
    proposed = "proposed"
    accepted = "accepted"
    rejected = "rejected"
    expired = "expired"
    implemented = "implemented"
    review_overstock = "review_overstock"
    refresh_inventory_data = "refresh_inventory_data"


class Recommendation(RetailOpsBaseModel):
    id: UUID = Field(default_factory=uuid4)
    product_id: UUID
    forecast_id: UUID | None = None
    anomaly_id: UUID | None = None
    alert_id: UUID | None = None
    recommendation_type: RecommendationType
    recommended_action: str = Field(..., min_length=5, max_length=300)
    rationale: str = Field(..., min_length=5, max_length=300)
    status: RecommendationStatus = RecommendationStatus.proposed

    generated_at: datetime
    expires_at: datetime

    @model_validator(mode="after")
    def validate_dates(self) -> Self:
        if not (self.generated_at <= self.expires_at):
            msg = "Invalid time order"
            raise ValueError(msg)
        return self
