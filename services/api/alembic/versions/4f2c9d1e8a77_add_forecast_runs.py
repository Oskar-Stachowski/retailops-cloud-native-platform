"""add forecast runs

Revision ID: 4f2c9d1e8a77
Revises: 8d6f3b1a4c20
Create Date: 2026-05-13 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "4f2c9d1e8a77"
down_revision: Union[str, Sequence[str], None] = "8d6f3b1a4c20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "forecast_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("run_key", sa.String(length=200), nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=False),
        sa.Column("model_version", sa.String(length=120), nullable=False),
        sa.Column("model_type", sa.String(length=80), nullable=False),
        sa.Column(
            "status",
            sa.String(length=40),
            nullable=False,
            server_default=sa.text("'experimental'"),
        ),
        sa.Column("profile", sa.String(length=40), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.Column("feature_dataset_name", sa.String(length=160), nullable=False),
        sa.Column("feature_dataset_id", sa.String(length=240), nullable=False),
        sa.Column(
            "feature_grain",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("target", sa.String(length=80), nullable=False),
        sa.Column("window_days", sa.Integer(), nullable=False),
        sa.Column("horizon_days", sa.Integer(), nullable=False),
        sa.Column("holdout_days", sa.Integer(), nullable=True),
        sa.Column("feature_row_count", sa.Integer(), nullable=False),
        sa.Column("forecast_row_count", sa.Integer(), nullable=False),
        sa.Column("evaluated_rows", sa.Integer(), nullable=True),
        sa.Column("skipped_rows", sa.Integer(), nullable=True),
        sa.Column(
            "metrics",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "artifacts",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
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
            "status IN ('experimental', 'candidate', 'approved', 'rejected', 'retraining_required', 'failed')",
            name="ck_forecast_runs_status",
        ),
        sa.CheckConstraint(
            "window_days > 0",
            name="ck_forecast_runs_window_days_positive",
        ),
        sa.CheckConstraint(
            "horizon_days > 0",
            name="ck_forecast_runs_horizon_days_positive",
        ),
        sa.CheckConstraint(
            "holdout_days IS NULL OR holdout_days > 0",
            name="ck_forecast_runs_holdout_days_positive",
        ),
        sa.CheckConstraint(
            "feature_row_count >= 0 AND forecast_row_count >= 0",
            name="ck_forecast_runs_row_counts_non_negative",
        ),
        sa.CheckConstraint(
            "evaluated_rows IS NULL OR evaluated_rows >= 0",
            name="ck_forecast_runs_evaluated_rows_non_negative",
        ),
        sa.CheckConstraint(
            "skipped_rows IS NULL OR skipped_rows >= 0",
            name="ck_forecast_runs_skipped_rows_non_negative",
        ),
        sa.CheckConstraint(
            "started_at <= completed_at",
            name="ck_forecast_runs_time_order",
        ),
    )

    op.create_index(
        "uq_forecast_runs_run_key",
        "forecast_runs",
        ["run_key"],
        unique=True,
    )
    op.create_index(
        "ix_forecast_runs_model_version",
        "forecast_runs",
        ["model_version"],
    )
    op.create_index(
        "ix_forecast_runs_status",
        "forecast_runs",
        ["status"],
    )
    op.create_index(
        "ix_forecast_runs_feature_dataset_id",
        "forecast_runs",
        ["feature_dataset_id"],
    )
    op.create_index(
        "ix_forecast_runs_completed_at",
        "forecast_runs",
        ["completed_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_forecast_runs_completed_at", table_name="forecast_runs")
    op.drop_index("ix_forecast_runs_feature_dataset_id", table_name="forecast_runs")
    op.drop_index("ix_forecast_runs_status", table_name="forecast_runs")
    op.drop_index("ix_forecast_runs_model_version", table_name="forecast_runs")
    op.drop_index("uq_forecast_runs_run_key", table_name="forecast_runs")
    op.drop_table("forecast_runs")
