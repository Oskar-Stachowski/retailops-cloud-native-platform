from uuid import UUID
from psycopg.rows import dict_row

from app.domain.models import Forecast


class ForecastRepository:
    def __init__(self, connection):
        self.connection = connection

    def _map_row_to_forecast(self, row) -> Forecast:
        return Forecast(
            id=row["id"],
            product_id=row["product_id"],
            forecast_period_start=row["forecast_period_start"],
            forecast_period_end=row["forecast_period_end"],
            predicted_quantity=row["predicted_quantity"],
            unit_of_measure=row["unit_of_measure"],
            generated_at=row["generated_at"],
            method=row["method"],
            status=row["status"],
            confidence_level=row["confidence_level"],
        )

    def list_forecasts_for_product(self, product_id: UUID) -> list[Forecast]:
        with self.connection.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT
                    id,
                    product_id,
                    forecast_period_start,
                    forecast_period_end,
                    predicted_quantity,
                    unit_of_measure,
                    generated_at,
                    method,
                    status,
                    confidence_level
                FROM forecasts
                WHERE product_id = %s
                ORDER BY forecast_period_start, generated_at;
                """,
                (product_id,)
            )
            rows = cur.fetchall()
            return [self._map_row_to_forecast(row) for row in rows]

    def get_latest_forecast_for_product(self, product_id: UUID) -> Forecast | None:
        with self.connection.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT
                    id,
                    product_id,
                    forecast_period_start,
                    forecast_period_end,
                    predicted_quantity,
                    unit_of_measure,
                    generated_at,
                    method,
                    status,
                    confidence_level
                FROM forecasts
                WHERE product_id = %s
                ORDER BY generated_at DESC
                LIMIT 1;
                """,
                (product_id,)
            )
            row = cur.fetchone()
            return self._map_row_to_forecast(row) if row else None
