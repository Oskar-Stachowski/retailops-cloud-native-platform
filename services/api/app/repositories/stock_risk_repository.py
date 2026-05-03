from typing import Any

from psycopg.rows import dict_row

from app.db.connection import fetch_all, fetch_one


class StockRiskRepository:
    """Read repository for product-level inventory/stock risk view."""

    SORT_COLUMNS = {
        "risk_status": "risk_status",
        "sku": "sku",
        "current_stock": "current_stock",
        "forecast_quantity": "forecast_quantity",
        "inventory_updated_at": "inventory_updated_at",
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

    def _build_risk_view_query(self) -> str:
        return """
            WITH latest_inventory AS (
                SELECT DISTINCT ON (product_id)
                    product_id,
                    stock_quantity::float AS current_stock,
                    recorded_at AS inventory_updated_at
                FROM inventory_snapshots
                ORDER BY product_id, recorded_at DESC NULLS LAST
            ),
            latest_forecast AS (
                SELECT DISTINCT ON (product_id)
                    product_id,
                    predicted_quantity::float AS forecast_quantity
                FROM forecasts
                ORDER BY product_id, generated_at DESC NULLS LAST
            )
            SELECT *
            FROM (
                SELECT
                    p.id::text AS product_id,
                    p.sku,
                    p.name,
                    p.category,
                    latest_inventory.current_stock,
                    latest_forecast.forecast_quantity,
                    CASE
                        WHEN latest_forecast.forecast_quantity IS NULL THEN 'unknown'
                        WHEN latest_inventory.current_stock <= latest_forecast.forecast_quantity
                            THEN 'stockout_risk'
                        WHEN latest_forecast.forecast_quantity > 0
                             AND latest_inventory.current_stock >= (latest_forecast.forecast_quantity * 3)
                            THEN 'overstock_risk'
                        ELSE 'normal'
                    END AS risk_status,
                    latest_inventory.inventory_updated_at
                FROM products p
                JOIN latest_inventory ON latest_inventory.product_id = p.id
                LEFT JOIN latest_forecast ON latest_forecast.product_id = p.id
            ) risk_items
        """

    def _build_filters(
        self,
        risk_status: str | None,
        category: str | None,
    ) -> tuple[str, list[Any]]:
        filters = []
        params: list[Any] = []

        if risk_status:
            filters.append("risk_status = %s")
            params.append(risk_status.strip())

        if category:
            filters.append("LOWER(COALESCE(category, '')) = LOWER(%s)")
            params.append(category.strip())

        if not filters:
            return "", params

        return "WHERE " + " AND ".join(filters), params

    def list_inventory_risks(
        self,
        risk_status: str | None = None,
        category: str | None = None,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "risk_status",
        sort_order: str = "asc",
    ) -> list[dict[str, Any]]:
        where_clause, params = self._build_filters(risk_status, category)
        sort_column = self.SORT_COLUMNS.get(sort_by, "risk_status")
        direction = "DESC" if sort_order.lower() == "desc" else "ASC"

        query = f"""
            {self._build_risk_view_query()}
            {where_clause}
            ORDER BY {sort_column} {direction}, sku ASC NULLS LAST
            LIMIT %s OFFSET %s;
        """
        return self._fetch_all(query, tuple(params + [limit, offset]))

    def count_inventory_risks(
        self,
        risk_status: str | None = None,
        category: str | None = None,
    ) -> int:
        where_clause, params = self._build_filters(risk_status, category)
        query = f"""
            SELECT COUNT(*) AS total
            FROM (
                {self._build_risk_view_query()}
                {where_clause}
            ) counted_risk_items;
        """
        row = self._fetch_one(query, tuple(params))
        return int(row["total"]) if row else 0
