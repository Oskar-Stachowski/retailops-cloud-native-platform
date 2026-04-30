"""create initial retailops schema

Revision ID: 9d505dd3b320
Revises:
Create Date: 2026-04-29 18:53:06.316751

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '9d505dd3b320'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto";')

    op.create_table(
        "products",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("sku", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("brand", sa.String(length=100), nullable=True),
        sa.Column(
            "status",
            sa.String(length=30),
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "status IN ('active', 'discontinued', 'draft')",
            name="ck_products_status",
        ),
        sa.UniqueConstraint("sku", name="uq_products_sku"),
    )

    op.create_index(
        "ix_products_category",
        "products",
        ["category"],
    )

    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("login", sa.String(length=20), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("team", sa.String(length=100), nullable=True),
        sa.Column(
            "status",
            sa.String(length=30),
            nullable=False,
            server_default="inactive",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "length(login) >= 5",
            name="ck_users_login_min_length",
        ),
        sa.CheckConstraint(
            "role IN ('inventory_planner', 'category_manager', 'analyst', 'admin')",
            name="ck_users_role",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'inactive')",
            name="ck_users_status",
        ),
        sa.UniqueConstraint("login", name="uq_users_login"),
    )

    op.create_index(
        "ix_users_role",
        "users",
        ["role"],
    )

    op.create_index(
        "ix_users_status",
        "users",
        ["status"],
    )

    op.create_table(
        "sales",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("sold_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "currency",
            sa.String(length=3),
            nullable=False,
            server_default="PLN",
        ),
        sa.Column("channel", sa.String(length=30), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("quantity > 0", name="ck_sales_quantity_positive"),
        sa.CheckConstraint("unit_price >= 0", name="ck_sales_unit_price_non_negative"),
        sa.CheckConstraint("total_amount >= 0", name="ck_sales_total_amount_non_negative"),
        sa.CheckConstraint(
            "currency IN ('PLN', 'EUR', 'USD')",
            name="ck_sales_currency",
        ),
        sa.CheckConstraint(
            "channel IS NULL OR channel IN ('online', 'store', 'marketplace')",
            name="ck_sales_channel",
        ),
    )

    op.create_index(
        "ix_sales_product_id",
        "sales",
        ["product_id"],
    )

    op.create_index(
        "ix_sales_sold_at",
        "sales",
        ["sold_at"],
    )

    op.create_table(
        "inventory_snapshots",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stock_quantity", sa.Integer(), nullable=False),
        sa.Column("unit_of_measure", sa.String(length=10), nullable=False),
        sa.Column("warehouse_code", sa.String(length=20), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "stock_quantity >= 0",
            name="ck_inventory_snapshots_stock_quantity_non_negative",
        ),
        sa.CheckConstraint(
            "unit_of_measure IN ('pcs', 'kg', 'l', 'm', 'm2')",
            name="ck_inventory_snapshots_unit_of_measure",
        ),
        sa.CheckConstraint(
            "length(warehouse_code) >= 1",
            name="ck_inventory_snapshots_warehouse_code_not_empty",
        ),
        sa.CheckConstraint(
            "recorded_at <= ingested_at",
            name="ck_inventory_snapshots_recorded_before_ingested",
        ),
    )

    op.create_index(
        "ix_inventory_snapshots_product_id",
        "inventory_snapshots",
        ["product_id"],
    )

    op.create_index(
        "ix_inventory_snapshots_recorded_at",
        "inventory_snapshots",
        ["recorded_at"],
    )

    op.create_index(
        "ix_inventory_snapshots_warehouse_code",
        "inventory_snapshots",
        ["warehouse_code"],
    )

    op.create_table(
        "forecasts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("forecast_period_start", sa.Date(), nullable=False),
        sa.Column("forecast_period_end", sa.Date(), nullable=False),
        sa.Column("predicted_quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit_of_measure", sa.String(length=10), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("method", sa.String(length=50), nullable=False),
        sa.Column(
            "status",
            sa.String(length=30),
            nullable=False,
            server_default="generated",
        ),
        sa.Column("confidence_level", sa.Numeric(5, 4), nullable=False),
        sa.CheckConstraint(
            "forecast_period_start <= forecast_period_end",
            name="ck_forecasts_period_order",
        ),
        sa.CheckConstraint(
            "predicted_quantity >= 0",
            name="ck_forecasts_predicted_quantity_non_negative",
        ),
        sa.CheckConstraint(
            "unit_of_measure IN ('pcs', 'kg', 'l', 'm', 'm2')",
            name="ck_forecasts_unit_of_measure",
        ),
        sa.CheckConstraint(
            "method IN ('moving_average', 'naive_baseline', 'seeded_demo')",
            name="ck_forecasts_method",
        ),
        sa.CheckConstraint(
            "status IN ('generated', 'evaluated', 'deprecated')",
            name="ck_forecasts_status",
        ),
        sa.CheckConstraint(
            "confidence_level >= 0 AND confidence_level <= 1",
            name="ck_forecasts_confidence_level_range",
        ),
    )

    op.create_index(
        "ix_forecasts_product_id",
        "forecasts",
        ["product_id"],
    )

    op.create_index(
        "ix_forecasts_forecast_period_start",
        "forecasts",
        ["forecast_period_start"],
    )

    op.create_index(
        "ix_forecasts_generated_at",
        "forecasts",
        ["generated_at"],
    )

    op.create_index(
        "ix_forecasts_status",
        "forecasts",
        ["status"],
    )

    op.create_table(
        "anomalies",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("anomaly_type", sa.String(length=50), nullable=False),
        sa.Column("metric_name", sa.String(length=100), nullable=False),
        sa.Column("actual_value", sa.Numeric(14, 4), nullable=False),
        sa.Column("expected_value", sa.Numeric(14, 4), nullable=False),
        sa.Column("deviation_percent", sa.Numeric(10, 4), nullable=False),
        sa.Column("impact_value", sa.Numeric(14, 4), nullable=False),
        sa.Column("impact_unit", sa.String(length=20), nullable=False),
        sa.Column("severity", sa.String(length=30), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "anomaly_type IN ('sales_drop', 'sales_spike', 'stale_inventory', 'pricing_issue')",
            name="ck_anomalies_anomaly_type",
        ),
        sa.CheckConstraint(
            "length(metric_name) >= 1",
            name="ck_anomalies_metric_name_not_empty",
        ),
        sa.CheckConstraint(
            "impact_unit IN ('PLN', 'pcs', 'kg', 'l', 'm', 'm2', 'percent')",
            name="ck_anomalies_impact_unit",
        ),
        sa.CheckConstraint(
            "severity IN ('low', 'medium', 'high', 'critical')",
            name="ck_anomalies_severity",
        ),
        sa.CheckConstraint(
            "period_start <= period_end",
            name="ck_anomalies_period_order",
        ),
    )

    op.create_index(
        "ix_anomalies_product_id",
        "anomalies",
        ["product_id"],
    )

    op.create_index(
        "ix_anomalies_anomaly_type",
        "anomalies",
        ["anomaly_type"],
    )

    op.create_index(
        "ix_anomalies_severity",
        "anomalies",
        ["severity"],
    )

    op.create_index(
        "ix_anomalies_detected_at",
        "anomalies",
        ["detected_at"],
    )

    op.create_table(
        "alerts",
        sa.Column(
            "id",
            sa.UUID(),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("anomaly_id", sa.UUID(), nullable=True),
        sa.Column("assigned_to_user_id", sa.UUID(), nullable=True),
        sa.Column("alert_type", sa.String(length=50), nullable=False),
        sa.Column("severity", sa.String(length=30), nullable=False),
        sa.Column(
            "status",
            sa.String(length=30),
            nullable=False,
            server_default="open",
        ),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("recommended_action", sa.String(length=300), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["anomaly_id"],
            ["anomalies.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["assigned_to_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "alert_type IN ('stockout_risk', 'overstock_risk', 'sales_drop', 'stale_inventory')",
            name="ck_alerts_alert_type",
        ),
        sa.CheckConstraint(
            "severity IN ('low', 'medium', 'high', 'critical')",
            name="ck_alerts_severity",
        ),
        sa.CheckConstraint(
            "status IN ('open', 'acknowledged', 'in_progress', 'resolved', 'dismissed')",
            name="ck_alerts_status",
        ),
        sa.CheckConstraint(
            "length(title) >= 5",
            name="ck_alerts_title_min_length",
        ),
        sa.CheckConstraint(
            "length(recommended_action) >= 5",
            name="ck_alerts_recommended_action_min_length",
        ),
    )

    op.create_index(
        "ix_alerts_product_id",
        "alerts",
        ["product_id"],
    )
    op.create_index(
        "ix_alerts_anomaly_id",
        "alerts",
        ["anomaly_id"],
    )
    op.create_index(
        "ix_alerts_assigned_to_user_id",
        "alerts",
        ["assigned_to_user_id"],
    )
    op.create_index(
        "ix_alerts_alert_type",
        "alerts",
        ["alert_type"],
    )
    op.create_index(
        "ix_alerts_severity",
        "alerts",
        ["severity"],
    )
    op.create_index(
        "ix_alerts_status",
        "alerts",
        ["status"],
    )
    op.create_index(
        "ix_alerts_created_at",
        "alerts",
        ["created_at"],
    )

    op.create_table(
        "recommendations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("forecast_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("anomaly_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("alert_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("recommendation_type", sa.String(length=50), nullable=False),
        sa.Column("recommended_action", sa.String(length=300), nullable=False),
        sa.Column("rationale", sa.String(length=1000), nullable=False),
        sa.Column(
            "status",
            sa.String(length=30),
            nullable=False,
            server_default="proposed",
        ),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["forecast_id"],
            ["forecasts.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["anomaly_id"],
            ["anomalies.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["alert_id"],
            ["alerts.id"],
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "recommendation_type IN ("
            "'replenish_stock', "
            "'review_stock', "
            "'review_price', "
            "'investigate_sales_drop', "
            "'refresh_inventory_data'"
            ")",
            name="ck_recommendations_recommendation_type",
        ),
        sa.CheckConstraint(
            "status IN ("
            "'proposed', "
            "'accepted', "
            "'rejected', "
            "'expired', "
            "'implemented'"
            ")",
            name="ck_recommendations_status",
        ),
        sa.CheckConstraint(
            "length(recommended_action) >= 5",
            name="ck_recommendations_recommended_action_min_length",
        ),
        sa.CheckConstraint(
            "length(rationale) >= 5",
            name="ck_recommendations_rationale_min_length",
        ),
        sa.CheckConstraint(
            "expires_at IS NULL OR expires_at >= generated_at",
            name="ck_recommendations_expires_after_generated",
        ),
    )

    op.create_index(
        "ix_recommendations_product_id",
        "recommendations",
        ["product_id"],
    )
    op.create_index(
        "ix_recommendations_forecast_id",
        "recommendations",
        ["forecast_id"],
    )
    op.create_index(
        "ix_recommendations_anomaly_id",
        "recommendations",
        ["anomaly_id"],
    )
    op.create_index(
        "ix_recommendations_alert_id",
        "recommendations",
        ["alert_id"],
    )
    op.create_index(
        "ix_recommendations_recommendation_type",
        "recommendations",
        ["recommendation_type"],
    )
    op.create_index(
        "ix_recommendations_status",
        "recommendations",
        ["status"],
    )
    op.create_index(
        "ix_recommendations_generated_at",
        "recommendations",
        ["generated_at"],
    )

    op.create_table(
        "workflow_actions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("alert_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("performed_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action_type", sa.String(length=50), nullable=False),
        sa.Column("comment", sa.String(length=1000), nullable=True),
        sa.Column("previous_status", sa.String(length=30), nullable=True),
        sa.Column("new_status", sa.String(length=30), nullable=True),
        sa.Column("performed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["alert_id"],
            ["alerts.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["performed_by_user_id"],
            ["users.id"],
        ),
        sa.CheckConstraint(
            "action_type IN ("
            "'acknowledge', "
            "'assign', "
            "'escalate', "
            "'dismiss', "
            "'resolve', "
            "'reopen', "
            "'comment', "
            "'reject', "
            "'accept'"
            ")",
            name="ck_workflow_actions_action_type",
        ),
        sa.CheckConstraint(
            "previous_status IS NULL OR previous_status IN ("
            "'open', "
            "'acknowledged', "
            "'in_progress', "
            "'resolved', "
            "'dismissed'"
            ")",
            name="ck_workflow_actions_previous_status",
        ),
        sa.CheckConstraint(
            "new_status IS NULL OR new_status IN ("
            "'open', "
            "'acknowledged', "
            "'in_progress', "
            "'resolved', "
            "'dismissed'"
            ")",
            name="ck_workflow_actions_new_status",
        ),
        sa.CheckConstraint(
            "comment IS NULL OR length(comment) >= 2",
            name="ck_workflow_actions_comment_min_length",
        ),
    )

    op.create_index(
        "ix_workflow_actions_alert_id",
        "workflow_actions",
        ["alert_id"],
    )
    op.create_index(
        "ix_workflow_actions_performed_by_user_id",
        "workflow_actions",
        ["performed_by_user_id"],
    )
    op.create_index(
        "ix_workflow_actions_action_type",
        "workflow_actions",
        ["action_type"],
    )
    op.create_index(
        "ix_workflow_actions_performed_at",
        "workflow_actions",
        ["performed_at"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_workflow_actions_performed_at", table_name="workflow_actions")
    op.drop_index("ix_workflow_actions_action_type", table_name="workflow_actions")
    op.drop_index("ix_workflow_actions_performed_by_user_id", table_name="workflow_actions")
    op.drop_index("ix_workflow_actions_alert_id", table_name="workflow_actions")
    op.drop_table("workflow_actions")

    op.drop_index("ix_recommendations_generated_at", table_name="recommendations")
    op.drop_index("ix_recommendations_status", table_name="recommendations")
    op.drop_index("ix_recommendations_recommendation_type", table_name="recommendations")
    op.drop_index("ix_recommendations_alert_id", table_name="recommendations")
    op.drop_index("ix_recommendations_anomaly_id", table_name="recommendations")
    op.drop_index("ix_recommendations_forecast_id", table_name="recommendations")
    op.drop_index("ix_recommendations_product_id", table_name="recommendations")
    op.drop_table("recommendations")

    op.drop_index("ix_alerts_created_at", table_name="alerts")
    op.drop_index("ix_alerts_status", table_name="alerts")
    op.drop_index("ix_alerts_severity", table_name="alerts")
    op.drop_index("ix_alerts_alert_type", table_name="alerts")
    op.drop_index("ix_alerts_assigned_to_user_id", table_name="alerts")
    op.drop_index("ix_alerts_anomaly_id", table_name="alerts")
    op.drop_index("ix_alerts_product_id", table_name="alerts")
    op.drop_table("alerts")

    op.drop_index("ix_anomalies_detected_at", table_name="anomalies")
    op.drop_index("ix_anomalies_severity", table_name="anomalies")
    op.drop_index("ix_anomalies_anomaly_type", table_name="anomalies")
    op.drop_index("ix_anomalies_product_id", table_name="anomalies")
    op.drop_table("anomalies")

    op.drop_index("ix_forecasts_status", table_name="forecasts")
    op.drop_index("ix_forecasts_generated_at", table_name="forecasts")
    op.drop_index("ix_forecasts_forecast_period_start", table_name="forecasts")
    op.drop_index("ix_forecasts_product_id", table_name="forecasts")
    op.drop_table("forecasts")

    op.drop_index("ix_users_status", table_name="users")
    op.drop_index("ix_users_role", table_name="users")
    op.drop_table("users")

    op.drop_index("ix_inventory_snapshots_warehouse_code", table_name="inventory_snapshots")
    op.drop_index("ix_inventory_snapshots_recorded_at", table_name="inventory_snapshots")
    op.drop_index("ix_inventory_snapshots_product_id", table_name="inventory_snapshots")
    op.drop_table("inventory_snapshots")

    op.drop_index("ix_sales_sold_at", table_name="sales")
    op.drop_index("ix_sales_product_id", table_name="sales")
    op.drop_table("sales")

    op.drop_index("ix_products_category", table_name="products")
    op.drop_table("products")
