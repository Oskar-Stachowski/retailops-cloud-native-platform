"""allow realism forecast method

Revision ID: 6b0f1c2d3e4a
Revises: 4f2c9d1e8a77
Create Date: 2026-05-14 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "6b0f1c2d3e4a"
down_revision: Union[str, Sequence[str], None] = "4f2c9d1e8a77"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


FORECAST_METHOD_CHECK = (
    "method IN ("
    "'moving_average', "
    "'naive_baseline', "
    "'seeded_demo', "
    "'retailops-baseline-demand-model', "
    "'retailops-realism-baseline-demand-model'"
    ")"
)

PREVIOUS_FORECAST_METHOD_CHECK = (
    "method IN ("
    "'moving_average', "
    "'naive_baseline', "
    "'seeded_demo', "
    "'retailops-baseline-demand-model'"
    ")"
)


def upgrade() -> None:
    op.drop_constraint("ck_forecasts_method", "forecasts", type_="check")
    op.create_check_constraint(
        "ck_forecasts_method",
        "forecasts",
        sa.text(FORECAST_METHOD_CHECK),
    )


def downgrade() -> None:
    op.drop_constraint("ck_forecasts_method", "forecasts", type_="check")
    op.create_check_constraint(
        "ck_forecasts_method",
        "forecasts",
        sa.text(PREVIOUS_FORECAST_METHOD_CHECK),
    )
