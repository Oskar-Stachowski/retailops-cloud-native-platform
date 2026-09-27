"""Allow forecasts produced by the assessed Random Forest batch."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "3a2b1c4d5e6f"
down_revision: Union[str, Sequence[str], None] = "6b0f1c2d3e4a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PREVIOUS_FORECAST_METHOD_CHECK = (
    "method IN ("
    "'moving_average', "
    "'naive_baseline', "
    "'seeded_demo', "
    "'retailops-baseline-demand-model', "
    "'retailops-realism-baseline-demand-model'"
    ")"
)

FORECAST_METHOD_CHECK = (
    "method IN ("
    "'moving_average', "
    "'naive_baseline', "
    "'seeded_demo', "
    "'retailops-baseline-demand-model', "
    "'retailops-realism-baseline-demand-model', "
    "'retailops-random-forest-demand-model'"
    ")"
)


def upgrade() -> None:
    op.drop_constraint("ck_forecasts_method", "forecasts", type_="check")
    op.create_check_constraint("ck_forecasts_method", "forecasts", sa.text(FORECAST_METHOD_CHECK))


def downgrade() -> None:
    op.drop_constraint("ck_forecasts_method", "forecasts", type_="check")
    op.create_check_constraint(
        "ck_forecasts_method", "forecasts", sa.text(PREVIOUS_FORECAST_METHOD_CHECK)
    )
