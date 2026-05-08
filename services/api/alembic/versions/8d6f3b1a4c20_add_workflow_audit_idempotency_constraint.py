"""add workflow audit idempotency constraint

Revision ID: 8d6f3b1a4c20
Revises: 7c4d9a2e1b6f
Create Date: 2026-05-08 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8d6f3b1a4c20"
down_revision: Union[str, Sequence[str], None] = "7c4d9a2e1b6f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "uq_workflow_audit_log_entity_idempotency_key",
        "workflow_audit_log",
        ["entity_type", "entity_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_workflow_audit_log_entity_idempotency_key",
        table_name="workflow_audit_log",
    )
