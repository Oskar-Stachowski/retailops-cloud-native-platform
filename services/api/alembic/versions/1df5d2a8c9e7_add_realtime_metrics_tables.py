"""add realtime metrics tables

Revision ID: 1df5d2a8c9e7
Revises: 9d505dd3b320
Create Date: 2026-05-07 09:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "1df5d2a8c9e7"
down_revision: Union[str, Sequence[str], None] = "9d505dd3b320"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "realtime_event_log",
        sa.Column(
            "event_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("topic", sa.String(length=100), nullable=False),
        sa.Column("schema_version", sa.String(length=20), nullable=False),
        sa.Column("source", sa.String(length=120), nullable=False),
        sa.Column("correlation_id", sa.String(length=120), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column(
            "attempt_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
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
            "status IN ('received', 'processed', 'failed_dead_lettered', 'ignored_duplicate')",
            name="ck_realtime_event_log_status",
        ),
        sa.CheckConstraint(
            "attempt_count >= 1",
            name="ck_realtime_event_log_attempt_count_positive",
        ),
    )

    op.create_index(
        "ix_realtime_event_log_event_type",
        "realtime_event_log",
        ["event_type"],
    )
    op.create_index(
        "ix_realtime_event_log_status",
        "realtime_event_log",
        ["status"],
    )
    op.create_index(
        "ix_realtime_event_log_occurred_at",
        "realtime_event_log",
        ["occurred_at"],
    )
    op.create_index(
        "ix_realtime_event_log_processed_at",
        "realtime_event_log",
        ["processed_at"],
    )

    op.create_table(
        "live_metric_observations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("realtime_event_log.event_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("metric_name", sa.String(length=100), nullable=False),
        sa.Column("metric_value", sa.Numeric(18, 4), nullable=False),
        sa.Column(
            "dimension_key",
            sa.String(length=200),
            nullable=False,
            server_default=sa.text("''"),
        ),
        sa.Column("source_event_type", sa.String(length=100), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "length(metric_name) >= 1",
            name="ck_live_metric_observations_metric_name",
        ),
    )

    op.create_index(
        "ix_live_metric_observations_event_id",
        "live_metric_observations",
        ["event_id"],
    )
    op.create_index(
        "ix_live_metric_observations_metric_name",
        "live_metric_observations",
        ["metric_name"],
    )
    op.create_index(
        "ix_live_metric_observations_observed_at",
        "live_metric_observations",
        ["observed_at"],
    )
    op.create_index(
        "uq_live_metric_observations_event_metric_dimension",
        "live_metric_observations",
        ["event_id", "metric_name", "dimension_key"],
        unique=True,
    )

    op.create_table(
        "realtime_consumer_state",
        sa.Column("consumer_name", sa.String(length=120), primary_key=True),
        sa.Column(
            "running",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "received_events",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "processed_events",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "failed_events",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "dead_lettered_events",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "ignored_events",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("last_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("last_event_type", sa.String(length=100), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
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
    )

    op.create_index(
        "ix_realtime_consumer_state_running",
        "realtime_consumer_state",
        ["running"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_realtime_consumer_state_running",
        table_name="realtime_consumer_state",
    )
    op.drop_table("realtime_consumer_state")

    op.drop_index(
        "uq_live_metric_observations_event_metric_dimension",
        table_name="live_metric_observations",
    )
    op.drop_index(
        "ix_live_metric_observations_observed_at",
        table_name="live_metric_observations",
    )
    op.drop_index(
        "ix_live_metric_observations_metric_name",
        table_name="live_metric_observations",
    )
    op.drop_index(
        "ix_live_metric_observations_event_id",
        table_name="live_metric_observations",
    )
    op.drop_table("live_metric_observations")

    op.drop_index(
        "ix_realtime_event_log_processed_at",
        table_name="realtime_event_log",
    )
    op.drop_index(
        "ix_realtime_event_log_occurred_at",
        table_name="realtime_event_log",
    )
    op.drop_index(
        "ix_realtime_event_log_status",
        table_name="realtime_event_log",
    )
    op.drop_index(
        "ix_realtime_event_log_event_type",
        table_name="realtime_event_log",
    )
    op.drop_table("realtime_event_log")
