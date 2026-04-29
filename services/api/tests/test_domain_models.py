from decimal import Decimal
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domain.models import Product, ProductStatus
from app.domain.models import Sale, Currency, Channel
from app.domain.models import InventorySnapshot, UnitOfMeasure
from app.domain.models import WorkflowAction, WorkflowActionType, AlertStatus
from app.domain.models import Forecast, ForecastMethod, ForecastStatus
from app.domain.models import Recommendation, RecommendationType, RecommendationStatus


def test_product_can_be_created_with_valid_data():
    now = datetime.now(timezone.utc)

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


def test_sale_rejects_invalid_total_amount():
    now = datetime.now(timezone.utc)

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


def test_inventory_snapshot_rejects_invalid_time_order():
    now = datetime.now(timezone.utc)

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


def test_workflow_action_requires_comment_for_dismiss():
    with pytest.raises(ValidationError):
        WorkflowAction(
            alert_id=uuid4(),
            performed_by_user_id=uuid4(),
            action_type=WorkflowActionType.DISMISS,
            previous_status=AlertStatus.open,
            new_status=AlertStatus.dismissed,
            comment=None,
        )


def test_forecast_rejects_confidence_level_outside_expected_range():
    today = datetime.now(timezone.utc).date()
    now = datetime.now(timezone.utc)

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


def test_recommendation_rejects_invalid_expiration_date():
    now = datetime.now(timezone.utc)

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
