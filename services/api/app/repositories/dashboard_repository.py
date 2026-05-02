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
            summary["open_anomalies_count"]
            + summary["open_recommendations_count"]
        )
        return summary

    def get_sales_trend(self, days: int = 14) -> list[dict[str, Any]]:
        """Return daily sales trend for dashboard chart.

        If the current MVP database does not yet contain compatible sales
        columns, return an empty list instead of breaking the dashboard.
        """
        if not table_exists("sales"):
            return []

        date_column = pick_column("sales", ["sold_at", "sale_date", "date", "created_at"])
        quantity_column = pick_column("sales", ["quantity", "sales_qty", "qty"])
        value_column = pick_column("sales", ["total_amount", "sales_value", "revenue", "amount"])

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
        return self._select_recent_work_items("anomalies", limit)

    def get_top_recommendations(self, limit: int = 10) -> list[dict[str, Any]]:
        """Return recent recommendation-like work items for dashboard."""
        return self._select_recent_work_items("recommendations", limit)

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

        return fetch_all(query, tuple(params))
