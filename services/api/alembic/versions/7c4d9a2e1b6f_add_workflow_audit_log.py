"""add workflow audit log

Revision ID: 7c4d9a2e1b6f
Revises: 1df5d2a8c9e7
Create Date: 2026-05-08 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "7c4d9a2e1b6f"
down_revision: Union[str, Sequence[str], None] = "1df5d2a8c9e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workflow_audit_log",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("entity_type", sa.String(length=40), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action_type", sa.String(length=50), nullable=False),
        sa.Column(
            "performed_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "assigned_to_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("previous_status", sa.String(length=30), nullable=False),
        sa.Column("new_status", sa.String(length=30), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=120), nullable=True),
        sa.Column(
            "source",
            sa.String(length=60),
            nullable=False,
            server_default=sa.text("'api'"),
        ),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "performed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "entity_type IN ('alert', 'recommendation')",
            name="ck_workflow_audit_log_entity_type",
        ),
        sa.CheckConstraint(
            "action_type IN ('acknowledge', 'assign', 'resolve', 'dismiss', 'comment', 'accept', 'reject')",
            name="ck_workflow_audit_log_action_type",
        ),
        sa.CheckConstraint(
            "comment IS NULL OR length(comment) >= 2",
            name="ck_workflow_audit_log_comment_length",
        ),
    )

    op.create_index(
        "ix_workflow_audit_log_entity",
        "workflow_audit_log",
        ["entity_type", "entity_id"],
    )
    op.create_index(
        "ix_workflow_audit_log_action_type",
        "workflow_audit_log",
        ["action_type"],
    )
    op.create_index(
        "ix_workflow_audit_log_performed_by_user_id",
        "workflow_audit_log",
        ["performed_by_user_id"],
    )
    op.create_index(
        "ix_workflow_audit_log_assigned_to_user_id",
        "workflow_audit_log",
        ["assigned_to_user_id"],
    )
    op.create_index(
        "ix_workflow_audit_log_performed_at",
        "workflow_audit_log",
        ["performed_at"],
    )
    op.create_index(
        "ix_workflow_audit_log_idempotency_key",
        "workflow_audit_log",
        ["idempotency_key"],
    )


def downgrade() -> None:
    op.drop_index("ix_workflow_audit_log_idempotency_key", table_name="workflow_audit_log")
    op.drop_index("ix_workflow_audit_log_performed_at", table_name="workflow_audit_log")
    op.drop_index(
        "ix_workflow_audit_log_assigned_to_user_id",
        table_name="workflow_audit_log",
    )
    op.drop_index(
        "ix_workflow_audit_log_performed_by_user_id",
        table_name="workflow_audit_log",
    )
    op.drop_index("ix_workflow_audit_log_action_type", table_name="workflow_audit_log")
    op.drop_index("ix_workflow_audit_log_entity", table_name="workflow_audit_log")
    op.drop_table("workflow_audit_log")
