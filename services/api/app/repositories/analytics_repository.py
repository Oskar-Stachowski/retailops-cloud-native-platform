"""Repository/query layer for analytics endpoints.

The MVP goal is not a full warehouse. The goal is to expose useful aggregated
reads from PostgreSQL for dashboard and analytical views.
"""

from typing import Any

from app.db.connection import fetch_all
from app.db.introspection import get_columns, pick_column, table_exists


class AnalyticsRepository:
    """Read-only analytical queries for product and inventory views."""

    def get_product_performance(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return product-level sales and stock summary when tables are available."""
        if not table_exists("products"):
            return []

        product_columns = get_columns("products")
        product_id_column = "id" if "id" in product_columns else None
        sku_column = "sku" if "sku" in product_columns else None
        name_column = "name" if "name" in product_columns else None
        category_column = "category" if "category" in product_columns else None
        status_column = "status" if "status" in product_columns else None

        if product_id_column is None:
            return []

        select_parts = ["p.id::text AS product_id"]
        select_parts.append("p.sku" if sku_column else "NULL::text AS sku")
        select_parts.append("p.name" if name_column else "NULL::text AS name")
        select_parts.append("p.category" if category_column else "NULL::text AS category")
        select_parts.append("p.status" if status_column else "NULL::text AS status")

        joins = []

        if table_exists("sales") and "product_id" in get_columns("sales"):
            quantity_column = pick_column("sales", ["quantity", "sales_qty", "qty"])
            value_column = pick_column(
                "sales",
                ["total_amount", "sales_value", "revenue", "amount"],
            )
            units_expression = (
                f"COALESCE(SUM({quantity_column}), 0)::float"
                if quantity_column
                else "COUNT(*)::float"
            )
            revenue_expression = (
                f"COALESCE(SUM({value_column}), 0)::float"
                if value_column
                else "0::float"
            )
            joins.append(
                f"""
                LEFT JOIN (
                    SELECT
                        product_id,
                        {units_expression} AS units_sold,
                        {revenue_expression} AS revenue
                    FROM sales
                    GROUP BY product_id
                ) sales_summary ON sales_summary.product_id = p.id
                """
            )
            select_parts.append("COALESCE(sales_summary.units_sold, 0) AS units_sold")
            select_parts.append("COALESCE(sales_summary.revenue, 0) AS revenue")
        else:
            select_parts.append("0::float AS units_sold")
            select_parts.append("0::float AS revenue")

        if table_exists("inventory_snapshots") and "product_id" in get_columns("inventory_snapshots"):
            stock_column = pick_column(
                "inventory_snapshots",
                ["stock_quantity", "quantity_on_hand", "on_hand_quantity", "stock_qty", "quantity"],
            )
            date_column = pick_column(
                "inventory_snapshots",
                ["recorded_at", "snapshot_date", "updated_at", "created_at"],
            )
            if stock_column and date_column:
                joins.append(
                    f"""
                    LEFT JOIN (
                        SELECT DISTINCT ON (product_id)
                            product_id,
                            {stock_column}::float AS current_stock,
                            {date_column} AS inventory_updated_at
                        FROM inventory_snapshots
                        ORDER BY product_id, {date_column} DESC NULLS LAST
                    ) inventory_latest ON inventory_latest.product_id = p.id
                    """
                )
                select_parts.append(
                    "COALESCE(inventory_latest.current_stock, 0) AS current_stock"
                )
                select_parts.append("inventory_latest.inventory_updated_at")
            else:
                select_parts.append("NULL::float AS current_stock")
                select_parts.append("NULL::timestamp AS inventory_updated_at")
        else:
            select_parts.append("NULL::float AS current_stock")
            select_parts.append("NULL::timestamp AS inventory_updated_at")

        query = f"""
            SELECT {', '.join(select_parts)}
            FROM products p
            {' '.join(joins)}
            ORDER BY units_sold DESC, sku ASC NULLS LAST
            LIMIT %s
        """
        return fetch_all(query, (limit,))

    def get_inventory_risk(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return simple stockout/overstock classification for MVP dashboard use."""
        required_tables = ["products", "inventory_snapshots"]
        if any(not table_exists(table_name) for table_name in required_tables):
            return []

        if "id" not in get_columns("products"):
            return []

        inventory_columns = get_columns("inventory_snapshots")
        if "product_id" not in inventory_columns:
            return []

        stock_column = pick_column(
            "inventory_snapshots",
            ["stock_quantity", "quantity_on_hand", "on_hand_quantity", "stock_qty", "quantity"],
        )
        inventory_date_column = pick_column(
            "inventory_snapshots",
            ["recorded_at", "snapshot_date", "updated_at", "created_at"],
        )

        if stock_column is None or inventory_date_column is None:
            return []

        forecast_join = ""
        forecast_value_expression = "NULL::float"
        forecast_select = "NULL::float AS forecast_quantity"
        forecast_columns = get_columns("forecasts") if table_exists("forecasts") else set()
        if "product_id" in forecast_columns:
            forecast_quantity_column = pick_column(
                "forecasts",
                ["forecast_quantity", "forecast_qty", "predicted_demand", "predicted_quantity", "quantity"],
            )
            forecast_date_column = pick_column(
                "forecasts",
                ["forecast_date", "target_date", "created_at", "updated_at"],
            )
            if forecast_quantity_column and forecast_date_column:
                forecast_value_expression = "forecast_latest.forecast_quantity"
                forecast_select = "forecast_latest.forecast_quantity AS forecast_quantity"
                forecast_join = f"""
                    LEFT JOIN (
                        SELECT DISTINCT ON (product_id)
                            product_id,
                            {forecast_quantity_column}::float AS forecast_quantity,
                            {forecast_date_column} AS forecast_date
                        FROM forecasts
                        ORDER BY product_id, {forecast_date_column} DESC NULLS LAST
                    ) forecast_latest ON forecast_latest.product_id = p.id
                """

        sku_select = "p.sku" if "sku" in get_columns("products") else "NULL::text AS sku"
        name_select = "p.name" if "name" in get_columns("products") else "NULL::text AS name"
        category_select = (
            "p.category" if "category" in get_columns("products") else "NULL::text AS category"
        )

        query = f"""
            WITH latest_inventory AS (
                SELECT DISTINCT ON (product_id)
                    product_id,
                    {stock_column}::float AS current_stock,
                    {inventory_date_column} AS inventory_updated_at
                FROM inventory_snapshots
                ORDER BY product_id, {inventory_date_column} DESC NULLS LAST
            )
            SELECT
                p.id::text AS product_id,
                {sku_select},
                {name_select},
                {category_select},
                latest_inventory.current_stock,
                {forecast_select},
                CASE
                    WHEN {forecast_value_expression} IS NULL THEN 'unknown'
                    WHEN latest_inventory.current_stock <= {forecast_value_expression} THEN 'stockout_risk'
                    WHEN {forecast_value_expression} > 0
                         AND latest_inventory.current_stock >= ({forecast_value_expression} * 3)
                         THEN 'overstock_risk'
                    ELSE 'normal'
                END AS risk_status,
                latest_inventory.inventory_updated_at
            FROM products p
            JOIN latest_inventory ON latest_inventory.product_id = p.id
            {forecast_join}
            ORDER BY
                CASE
                    WHEN {forecast_value_expression} IS NULL THEN 3
                    WHEN latest_inventory.current_stock <= {forecast_value_expression} THEN 1
                    WHEN {forecast_value_expression} > 0
                         AND latest_inventory.current_stock >= ({forecast_value_expression} * 3)
                         THEN 2
                    ELSE 4
                END,
                sku ASC NULLS LAST
            LIMIT %s
        """
        return fetch_all(query, (limit,))
