from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domain.models import (
    AlertStatus,
    Channel,
    Currency,
    Forecast,
    ForecastMethod,
    ForecastRun,
    ForecastRunStatus,
    ForecastStatus,
    InventorySnapshot,
    Product,
    ProductStatus,
    Recommendation,
    RecommendationStatus,
    RecommendationType,
    Sale,
    UnitOfMeasure,
    WorkflowAction,
    WorkflowActionType,
)
from app.domain.workflow import (
    WorkflowActionName,
    WorkflowEntityType,
    WorkflowTransitionError,
    is_workflow_transition_allowed,
    validate_workflow_transition,
)


def test_product_can_be_created_with_valid_data() -> None:
    now = datetime.now(UTC)

    product = Product(
        sku="SKU-001",
        name="Test Product",
        category="Electronics",
        brand="RetailOps",
        status=ProductStatus.active,
        created_at=now,
        updated_at=now,
    )

    assert product.sku == "SKU-001"
    assert product.name == "Test Product"
    assert product.status == ProductStatus.active


def test_sale_rejects_invalid_total_amount() -> None:
    now = datetime.now(UTC)

    with pytest.raises(ValidationError):
        Sale(
            product_id=uuid4(),
            quantity=2,
            sold_at=now,
            unit_price=Decimal("10.00"),
            total_amount=Decimal("30.00"),
            currency=Currency.PLN,
            channel=Channel.online,
            created_at=now,
        )


def test_inventory_snapshot_rejects_invalid_time_order() -> None:
    now = datetime.now(UTC)

    with pytest.raises(ValidationError):
        InventorySnapshot(
            product_id=uuid4(),
            stock_quantity=100,
            unit_of_measure=UnitOfMeasure.pcs,
            warehouse_code="WH-001",
            recorded_at=now,
            ingested_at=now,
            created_at=now.replace(year=now.year - 1),
        )


def test_workflow_action_requires_comment_for_dismiss() -> None:
    with pytest.raises(ValidationError):
        WorkflowAction(
            alert_id=uuid4(),
            performed_by_user_id=uuid4(),
            action_type=WorkflowActionType.DISMISS,
            previous_status=AlertStatus.open,
            new_status=AlertStatus.dismissed,
            comment=None,
        )


def test_workflow_action_accepts_valid_alert_transition() -> None:
    action = WorkflowAction(
        alert_id=uuid4(),
        performed_by_user_id=uuid4(),
        action_type=WorkflowActionType.ACKNOWLEDGE,
        previous_status=AlertStatus.open,
        new_status=AlertStatus.acknowledged,
        comment=None,
    )

    assert action.previous_status == AlertStatus.open
    assert action.new_status == AlertStatus.acknowledged


def test_workflow_action_rejects_invalid_alert_transition() -> None:
    with pytest.raises(ValidationError):
        WorkflowAction(
            alert_id=uuid4(),
            performed_by_user_id=uuid4(),
            action_type=WorkflowActionType.ASSIGN,
            previous_status=AlertStatus.resolved,
            new_status=AlertStatus.in_progress,
            comment=None,
        )


def test_comment_action_cannot_change_alert_status() -> None:
    with pytest.raises(ValidationError):
        WorkflowAction(
            alert_id=uuid4(),
            performed_by_user_id=uuid4(),
            action_type=WorkflowActionType.COMMENT,
            previous_status=AlertStatus.open,
            new_status=AlertStatus.acknowledged,
            comment="Reviewing this alert.",
        )


def test_recommendation_reject_transition_requires_comment() -> None:
    with pytest.raises(WorkflowTransitionError):
        validate_workflow_transition(
            entity_type=WorkflowEntityType.recommendation,
            action=WorkflowActionName.reject,
            previous_status=RecommendationStatus.proposed,
            new_status=RecommendationStatus.rejected,
            comment=None,
        )


def test_recommendation_accept_transition_is_allowed() -> None:
    assert is_workflow_transition_allowed(
        entity_type=WorkflowEntityType.recommendation,
        action=WorkflowActionName.accept,
        previous_status=RecommendationStatus.proposed,
        new_status=RecommendationStatus.accepted,
    )


@pytest.mark.parametrize(
    ("entity_type", "action", "previous_status", "new_status"),
    [
        (
            WorkflowEntityType.alert,
            WorkflowActionName.acknowledge,
            AlertStatus.open,
            AlertStatus.acknowledged,
        ),
        (
            WorkflowEntityType.alert,
            WorkflowActionName.resolve,
            AlertStatus.in_progress,
            AlertStatus.resolved,
        ),
        (
            WorkflowEntityType.recommendation,
            WorkflowActionName.accept,
            RecommendationStatus.proposed,
            RecommendationStatus.accepted,
        ),
        (
            WorkflowEntityType.recommendation,
            WorkflowActionName.resolve,
            RecommendationStatus.accepted,
            RecommendationStatus.implemented,
        ),
    ],
)
def test_workflow_transition_matrix_allows_expected_paths(
    entity_type,
    action,
    previous_status,
    new_status,
) -> None:
    assert is_workflow_transition_allowed(
        entity_type=entity_type,
        action=action,
        previous_status=previous_status,
        new_status=new_status,
    )


@pytest.mark.parametrize(
    ("entity_type", "action", "previous_status", "new_status"),
    [
        (
            WorkflowEntityType.alert,
            WorkflowActionName.resolve,
            AlertStatus.open,
            AlertStatus.resolved,
        ),
        (
            WorkflowEntityType.alert,
            WorkflowActionName.assign,
            AlertStatus.resolved,
            AlertStatus.in_progress,
        ),
        (
            WorkflowEntityType.recommendation,
            WorkflowActionName.accept,
            RecommendationStatus.accepted,
            RecommendationStatus.accepted,
        ),
        (
            WorkflowEntityType.recommendation,
            WorkflowActionName.resolve,
            RecommendationStatus.proposed,
            RecommendationStatus.implemented,
        ),
    ],
)
def test_workflow_transition_matrix_rejects_invalid_paths(
    entity_type,
    action,
    previous_status,
    new_status,
) -> None:
    assert not is_workflow_transition_allowed(
        entity_type=entity_type,
        action=action,
        previous_status=previous_status,
        new_status=new_status,
    )


def test_recommendation_cannot_move_from_implemented_to_accepted() -> None:
    assert not is_workflow_transition_allowed(
        entity_type=WorkflowEntityType.recommendation,
        action=WorkflowActionName.accept,
        previous_status=RecommendationStatus.implemented,
        new_status=RecommendationStatus.accepted,
    )


def test_forecast_rejects_confidence_level_outside_expected_range() -> None:
    today = datetime.now(UTC).date()
    now = datetime.now(UTC)

    with pytest.raises(ValidationError):
        Forecast(
            product_id=uuid4(),
            forecast_period_start=today,
            forecast_period_end=today,
            predicted_quantity=100,
            unit_of_measure=UnitOfMeasure.pcs,
            generated_at=now,
            method=ForecastMethod.naive_baseline,
            status=ForecastStatus.generated,
            confidence_level=1.5,
        )


def test_forecast_run_accepts_model_lineage_and_metrics() -> None:
    now = datetime.now(UTC)

    forecast_run = ForecastRun(
        run_key="baseline:v1:dataset-1",
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
        metrics={"mae": "2.0000"},
        artifacts={"model_manifest": "model_manifest.json"},
        started_at=now,
        completed_at=now,
    )

    assert forecast_run.status == ForecastRunStatus.candidate
    assert forecast_run.metrics["mae"] == "2.0000"


def test_forecast_run_rejects_invalid_time_order() -> None:
    now = datetime.now(UTC)

    with pytest.raises(ValidationError):
        ForecastRun(
            run_key="baseline:v1:dataset-1",
            model_name="retailops-demand-baseline-moving-average",
            model_version="baseline-moving-average-v1",
            model_type="moving_average_baseline",
            profile="small",
            seed=42,
            feature_dataset_name="retailops-demand-forecast-features",
            feature_dataset_id="dataset-1",
            feature_grain=["date", "product_id", "store_id", "channel"],
            target="units_sold",
            window_days=28,
            horizon_days=7,
            feature_row_count=100,
            forecast_row_count=70,
            started_at=now,
            completed_at=now.replace(year=now.year - 1),
        )


def test_recommendation_rejects_invalid_expiration_date() -> None:
    now = datetime.now(UTC)

    with pytest.raises(ValidationError):
        Recommendation(
            product_id=uuid4(),
            recommendation_type=RecommendationType.replenish_stock,
            recommended_action="Replenish stock for product",
            rationale="Forecast indicates stockout risk",
            status=RecommendationStatus.proposed,
            generated_at=now,
            expires_at=now.replace(year=now.year - 1),
        )
