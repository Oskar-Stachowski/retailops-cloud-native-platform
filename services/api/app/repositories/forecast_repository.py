from datetime import date
from typing import Any
from uuid import UUID

from psycopg.rows import dict_row

from app.db.connection import fetch_all, fetch_one
from app.domain.models import Forecast


class ForecastRepository:
    """PostgreSQL-backed read repository for forecast data."""

    SORT_COLUMNS = {
        "forecast_period_start": "forecast_period_start",
        "forecast_period_end": "forecast_period_end",
        "generated_at": "generated_at",
        "predicted_quantity": "predicted_quantity",
        "confidence_level": "confidence_level",
    }

    def __init__(self, connection=None):
        self.connection = connection

    def _fetch_all(self, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        if self.connection is None:
            return fetch_all(query, params)

        with self.connection.cursor(row_factory=dict_row) as cur:
            cur.execute(query, params)
            return cur.fetchall()

    def _fetch_one(self, query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        if self.connection is None:
            return fetch_one(query, params)

        with self.connection.cursor(row_factory=dict_row) as cur:
            cur.execute(query, params)
            return cur.fetchone()

    def _map_row_to_forecast(self, row: dict[str, Any]) -> Forecast:
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

    def _build_filters(
        self,
        product_id: UUID | None,
        status: str | None,
        method: str | None,
        date_from: date | None,
        date_to: date | None,
    ) -> tuple[str, list[Any]]:
        filters = []
        params: list[Any] = []

        if product_id:
            filters.append("product_id = %s")
            params.append(product_id)

        if status:
            filters.append("status = %s")
            params.append(status.strip())

        if method:
            filters.append("method = %s")
            params.append(method.strip())

        if date_from:
            filters.append("forecast_period_start >= %s")
            params.append(date_from)

        if date_to:
            filters.append("forecast_period_end <= %s")
            params.append(date_to)

        if not filters:
            return "", params

        return "WHERE " + " AND ".join(filters), params

    def list_forecasts(
        self,
        product_id: UUID | None = None,
        status: str | None = None,
        method: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "forecast_period_start",
        sort_order: str = "asc",
    ) -> list[Forecast]:
        where_clause, params = self._build_filters(
            product_id=product_id,
            status=status,
            method=method,
            date_from=date_from,
            date_to=date_to,
        )
        sort_column = self.SORT_COLUMNS.get(sort_by, "forecast_period_start")
        direction = "DESC" if sort_order.lower() == "desc" else "ASC"

        query = f"""
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
            {where_clause}
            ORDER BY {sort_column} {direction}, generated_at DESC
            LIMIT %s OFFSET %s;
        """
        rows = self._fetch_all(query, tuple(params + [limit, offset]))
        return [self._map_row_to_forecast(row) for row in rows]

    def count_forecasts(
        self,
        product_id: UUID | None = None,
        status: str | None = None,
        method: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> int:
        where_clause, params = self._build_filters(
            product_id=product_id,
            status=status,
            method=method,
            date_from=date_from,
            date_to=date_to,
        )
        query = f"SELECT COUNT(*) AS total FROM forecasts {where_clause};"
        row = self._fetch_one(query, tuple(params))
        return int(row["total"]) if row else 0

    def get_forecast_by_id(self, forecast_id: UUID) -> Forecast | None:
        row = self._fetch_one(
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
            WHERE id = %s;
            """,
            (forecast_id,),
        )
        return self._map_row_to_forecast(row) if row else None

    def list_forecasts_for_product(self, product_id: UUID) -> list[Forecast]:
        return self.list_forecasts(product_id=product_id, limit=100, offset=0)

    def get_latest_forecast_for_product(self, product_id: UUID) -> Forecast | None:
        row = self._fetch_one(
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
            (product_id,),
        )
        return self._map_row_to_forecast(row) if row else None
