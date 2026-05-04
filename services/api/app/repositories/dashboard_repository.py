"""Repository/query layer for dashboard endpoints.

This layer is intentionally read-only. It gives the dashboard real PostgreSQL
backing without pushing SQL details into FastAPI route handlers.
"""

from typing import Any

from psycopg import sql

from app.db.connection import fetch_all, fetch_one
from app.db.introspection import count_rows, get_columns, pick_column, table_exists


OPEN_STATUSES = (
    "new",
    "open",
    "acknowledged",
    "in_review",
    "assigned",
    "escalated",
    "proposed",
)


class DashboardRepository:
    """Read-only queries used by dashboard and operations views."""

    CORE_TABLES = (
        "products",
        "sales",
        "inventory_snapshots",
        "forecasts",
        "anomalies",
        "recommendations",
    )

    def get_summary(self) -> dict[str, Any]:
        """Return compact dashboard counters based on current database state."""
        summary = {
            "products_count": count_rows("products"),
            "sales_count": count_rows("sales"),
            "inventory_snapshots_count": count_rows("inventory_snapshots"),
            "forecasts_count": count_rows("forecasts"),
            "anomalies_count": count_rows("anomalies"),
            "recommendations_count": count_rows("recommendations"),
            "open_anomalies_count": self._count_by_status("anomalies", OPEN_STATUSES),
            "open_recommendations_count": self._count_by_status(
                "recommendations",
                OPEN_STATUSES,
            ),
            "last_refresh_at": self._latest_refresh_timestamp(),
        }
        summary["open_work_items_count"] = (
            summary["open_anomalies_count"] + summary["open_recommendations_count"]
        )
        return summary

    def get_sales_trend(self, days: int = 14) -> list[dict[str, Any]]:
        """Return daily sales trend for dashboard chart.

        If the MVP database does not yet contain compatible sales columns,
        return an empty list instead of breaking the dashboard.
        """
        if not table_exists("sales"):
            return []

        date_column = pick_column("sales", ["sold_at", "sale_date", "date", "created_at"])
        quantity_column = pick_column("sales", ["quantity", "sales_qty", "qty"])
        value_column = pick_column(
            "sales",
            ["total_amount", "sales_value", "revenue", "amount"],
        )

        if date_column is None:
            return []

        units_expression = (
            sql.SQL("COALESCE(SUM({}), 0)::float").format(sql.Identifier(quantity_column))
            if quantity_column
            else sql.SQL("COUNT(*)::float")
        )
        revenue_expression = (
            sql.SQL("COALESCE(SUM({}), 0)::float").format(sql.Identifier(value_column))
            if value_column
            else sql.SQL("0::float")
        )

        query = sql.SQL(
            """
            SELECT
                DATE({date_column}) AS date,
                {units_expression} AS units_sold,
                {revenue_expression} AS revenue
            FROM sales
            WHERE {date_column} >= CURRENT_DATE - (%s::int * INTERVAL '1 day')
            GROUP BY DATE({date_column})
            ORDER BY DATE({date_column}) ASC
            """
        ).format(
            date_column=sql.Identifier(date_column),
            units_expression=units_expression,
            revenue_expression=revenue_expression,
        )

        return fetch_all(query, (days,))

    def get_open_alerts(self, limit: int = 10) -> list[dict[str, Any]]:
        """Return current anomaly-like work items for operations dashboard."""
        return self._select_recent_work_items(
            table_name="anomalies",
            limit=limit,
            source="anomaly",
        )

    def get_top_recommendations(self, limit: int = 10) -> list[dict[str, Any]]:
        """Return recent recommendation-like work items for dashboard."""
        return self._select_recent_work_items(
            table_name="recommendations",
            limit=limit,
            source="recommendation",
        )

    def get_open_work_items(self, limit: int = 10) -> list[dict[str, Any]]:
        """Return a combined operational backlog from anomalies and recommendations."""
        per_source_limit = max(limit, 1)
        items = self.get_open_alerts(limit=per_source_limit)
        items.extend(self.get_top_recommendations(limit=per_source_limit))

        def sort_key(item: dict[str, Any]) -> Any:
            return (
                item.get("created_at")
                or item.get("updated_at")
                or item.get("detected_at")
                or ""
            )

        return sorted(items, key=sort_key, reverse=True)[:limit]

    def get_stock_risk_summary(self) -> dict[str, int]:
        """Return product-level stock-risk counters for dashboard summary cards.

        This intentionally mirrors the MVP stock-risk concept without exposing
        a full warehouse model. Missing tables or columns produce safe zeroes.
        """
        empty = {
            "total_risk_items": 0,
            "normal_count": 0,
            "stockout_risk_count": 0,
            "overstock_risk_count": 0,
            "unknown_count": 0,
        }

        if not table_exists("products") or not table_exists("inventory_snapshots"):
            return empty

        inventory_columns = get_columns("inventory_snapshots")
        if "product_id" not in inventory_columns:
            return empty

        stock_column = pick_column(
            "inventory_snapshots",
            ["stock_quantity", "stock_qty", "quantity", "on_hand_quantity"],
        )
        inventory_date_column = pick_column(
            "inventory_snapshots",
            ["recorded_at", "snapshot_at", "created_at", "updated_at"],
        )
        if stock_column is None or inventory_date_column is None:
            return empty

        forecast_cte = sql.SQL("")
        forecast_join = sql.SQL("")
        risk_case = sql.SQL("'unknown'")

        if table_exists("forecasts") and "product_id" in get_columns("forecasts"):
            forecast_quantity_column = pick_column(
                "forecasts",
                [
                    "predicted_quantity",
                    "forecast_quantity",
                    "forecast_qty",
                    "predicted_demand",
                    "quantity",
                ],
            )
            forecast_date_column = pick_column(
                "forecasts",
                ["generated_at", "forecast_date", "target_date", "created_at", "updated_at"],
            )

            if forecast_quantity_column and forecast_date_column:
                forecast_cte = sql.SQL(
                    """
                    , latest_forecast AS (
                        SELECT DISTINCT ON (product_id)
                            product_id,
                            {forecast_quantity_column}::float AS forecast_quantity
                        FROM forecasts
                        ORDER BY product_id, {forecast_date_column} DESC NULLS LAST
                    )
                    """
                ).format(
                    forecast_quantity_column=sql.Identifier(forecast_quantity_column),
                    forecast_date_column=sql.Identifier(forecast_date_column),
                )
                forecast_join = sql.SQL(
                    "LEFT JOIN latest_forecast ON latest_forecast.product_id = p.id"
                )
                risk_case = sql.SQL(
                    """
                    CASE
                        WHEN latest_forecast.forecast_quantity IS NULL THEN 'unknown'
                        WHEN latest_inventory.current_stock <= latest_forecast.forecast_quantity
                            THEN 'stockout_risk'
                        WHEN latest_forecast.forecast_quantity > 0
                             AND latest_inventory.current_stock >= latest_forecast.forecast_quantity * 3
                            THEN 'overstock_risk'
                        ELSE 'normal'
                    END
                    """
                )

        query = sql.SQL(
            """
            WITH latest_inventory AS (
                SELECT DISTINCT ON (product_id)
                    product_id,
                    {stock_column}::float AS current_stock,
                    {inventory_date_column} AS inventory_updated_at
                FROM inventory_snapshots
                ORDER BY product_id, {inventory_date_column} DESC NULLS LAST
            )
            {forecast_cte}
            SELECT risk_status, COUNT(*)::int AS count
            FROM (
                SELECT
                    {risk_case} AS risk_status
                FROM products p
                JOIN latest_inventory ON latest_inventory.product_id = p.id
                {forecast_join}
            ) risk_items
            GROUP BY risk_status
            """
        ).format(
            stock_column=sql.Identifier(stock_column),
            inventory_date_column=sql.Identifier(inventory_date_column),
            forecast_cte=forecast_cte,
            risk_case=risk_case,
            forecast_join=forecast_join,
        )

        rows = fetch_all(query)
        summary = empty.copy()
        for row in rows:
            status = row.get("risk_status") or "unknown"
            count = int(row.get("count", 0))
            if status == "normal":
                summary["normal_count"] = count
            elif status == "stockout_risk":
                summary["stockout_risk_count"] = count
            elif status == "overstock_risk":
                summary["overstock_risk_count"] = count
            else:
                summary["unknown_count"] += count

        summary["total_risk_items"] = (
            summary["normal_count"]
            + summary["stockout_risk_count"]
            + summary["overstock_risk_count"]
            + summary["unknown_count"]
        )
        return summary

    def _count_by_status(self, table_name: str, statuses: tuple[str, ...]) -> int:
        if not table_exists(table_name) or "status" not in get_columns(table_name):
            return 0

        query = sql.SQL(
            "SELECT COUNT(*) AS count FROM {} WHERE status = ANY(%s)"
        ).format(sql.Identifier(table_name))
        row = fetch_one(query, (list(statuses),))
        return int(row["count"]) if row else 0

    def _latest_refresh_timestamp(self) -> Any | None:
        latest_values = []
        candidates = [
            "updated_at",
            "created_at",
            "recorded_at",
            "detected_at",
            "generated_at",
            "forecast_date",
            "sold_at",
        ]

        for table_name in self.CORE_TABLES:
            column = pick_column(table_name, candidates)
            if column is None:
                continue

            query = sql.SQL(
                "SELECT MAX({column}) AS latest FROM {table} WHERE {column} IS NOT NULL"
            ).format(
                column=sql.Identifier(column),
                table=sql.Identifier(table_name),
            )
            row = fetch_one(query)
            if row and row["latest"] is not None:
                latest_values.append(row["latest"])

        return max(latest_values) if latest_values else None

    def _select_recent_work_items(
        self,
        table_name: str,
        limit: int,
        source: str,
    ) -> list[dict[str, Any]]:
        if not table_exists(table_name):
            return []

        columns = get_columns(table_name)
        preferred_columns = [
            "id",
            "product_id",
            "sku",
            "anomaly_type",
            "recommendation_type",
            "type",
            "severity",
            "priority",
            "status",
            "title",
            "description",
            "message",
            "reason",
            "created_at",
            "updated_at",
            "detected_at",
        ]
        selected_columns = [column for column in preferred_columns if column in columns]

        if not selected_columns:
            return []

        status_filter = sql.SQL("")
        params: list[Any] = []
        if "status" in columns:
            status_filter = sql.SQL("WHERE status = ANY(%s)")
            params.append(list(OPEN_STATUSES))

        order_column = pick_column(
            table_name,
            ["created_at", "updated_at", "detected_at", "recorded_at"],
        )
        order_expression = (
            sql.SQL("ORDER BY {} DESC NULLS LAST").format(sql.Identifier(order_column))
            if order_column
            else sql.SQL("")
        )

        params.append(limit)
        query = sql.SQL(
            """
            SELECT {columns}
            FROM {table}
            {status_filter}
            {order_expression}
            LIMIT %s
            """
        ).format(
            columns=sql.SQL(", ").join(sql.Identifier(column) for column in selected_columns),
            table=sql.Identifier(table_name),
            status_filter=status_filter,
            order_expression=order_expression,
        )

        rows = fetch_all(query, tuple(params))
        for row in rows:
            row["source"] = source
        return rows
