"""Read repository for Product 360 views.

Product 360 intentionally aggregates already-existing RetailOps tables. It does
not introduce a new write model or workflow mutation API yet.
"""

from typing import Any
from uuid import UUID

from app.db.connection import fetch_all, fetch_one


OPEN_ALERT_STATUSES = ("open", "acknowledged", "in_progress")
OPEN_RECOMMENDATION_STATUSES = ("proposed", "accepted")


class Product360Repository:
    """Read-only query layer for product drill-down and workflow context."""

    def get_metrics(self, product_id: UUID) -> dict[str, Any]:
        row = fetch_one(
            """
            SELECT
                (
                    SELECT COUNT(*)::int
                    FROM sales
                    WHERE product_id = %s
                ) AS sales_count,
                (
                    SELECT COALESCE(SUM(quantity), 0)::float
                    FROM sales
                    WHERE product_id = %s
                ) AS total_units_sold,
                (
                    SELECT COALESCE(SUM(total_amount), 0)::float
                    FROM sales
                    WHERE product_id = %s
                ) AS total_revenue,
                (
                    SELECT MAX(sold_at)
                    FROM sales
                    WHERE product_id = %s
                ) AS latest_sale_at,
                (
                    SELECT COUNT(*)::int
                    FROM inventory_snapshots
                    WHERE product_id = %s
                ) AS inventory_snapshot_count,
                (
                    SELECT stock_quantity::float
                    FROM inventory_snapshots
                    WHERE product_id = %s
                    ORDER BY recorded_at DESC NULLS LAST
                    LIMIT 1
                ) AS current_stock,
                (
                    SELECT recorded_at
                    FROM inventory_snapshots
                    WHERE product_id = %s
                    ORDER BY recorded_at DESC NULLS LAST
                    LIMIT 1
                ) AS inventory_updated_at,
                (
                    SELECT COUNT(*)::int
                    FROM forecasts
                    WHERE product_id = %s
                ) AS forecast_count,
                (
                    SELECT predicted_quantity::float
                    FROM forecasts
                    WHERE product_id = %s
                    ORDER BY generated_at DESC NULLS LAST
                    LIMIT 1
                ) AS latest_forecast_quantity,
                (
                    SELECT forecast_period_start
                    FROM forecasts
                    WHERE product_id = %s
                    ORDER BY generated_at DESC NULLS LAST
                    LIMIT 1
                ) AS latest_forecast_period_start,
                (
                    SELECT forecast_period_end
                    FROM forecasts
                    WHERE product_id = %s
                    ORDER BY generated_at DESC NULLS LAST
                    LIMIT 1
                ) AS latest_forecast_period_end,
                (
                    SELECT COUNT(*)::int
                    FROM anomalies
                    WHERE product_id = %s
                ) AS anomaly_count,
                (
                    SELECT COUNT(*)::int
                    FROM alerts
                    WHERE product_id = %s
                ) AS alert_count,
                (
                    SELECT COUNT(*)::int
                    FROM alerts
                    WHERE product_id = %s
                      AND status = ANY(%s)
                ) AS open_alert_count,
                (
                    SELECT COUNT(*)::int
                    FROM recommendations
                    WHERE product_id = %s
                ) AS recommendation_count,
                (
                    SELECT COUNT(*)::int
                    FROM recommendations
                    WHERE product_id = %s
                      AND status = ANY(%s)
                ) AS open_recommendation_count,
                (
                    SELECT COUNT(*)::int
                    FROM workflow_actions wa
                    JOIN alerts a ON a.id = wa.alert_id
                    WHERE a.product_id = %s
                ) AS workflow_action_count;
            """,
            (
                product_id,
                product_id,
                product_id,
                product_id,
                product_id,
                product_id,
                product_id,
                product_id,
                product_id,
                product_id,
                product_id,
                product_id,
                product_id,
                product_id,
                list(OPEN_ALERT_STATUSES),
                product_id,
                product_id,
                list(OPEN_RECOMMENDATION_STATUSES),
                product_id,
            ),
        )
        return row or {}

    def get_stock_risk(self, product_id: UUID) -> dict[str, Any] | None:
        return fetch_one(
            """
            WITH latest_inventory AS (
                SELECT DISTINCT ON (product_id)
                    product_id,
                    stock_quantity::float AS current_stock,
                    recorded_at AS inventory_updated_at
                FROM inventory_snapshots
                WHERE product_id = %s
                ORDER BY product_id, recorded_at DESC NULLS LAST
            ),
            latest_forecast AS (
                SELECT DISTINCT ON (product_id)
                    product_id,
                    predicted_quantity::float AS forecast_quantity
                FROM forecasts
                WHERE product_id = %s
                ORDER BY product_id, generated_at DESC NULLS LAST
            )
            SELECT
                p.id AS product_id,
                p.sku,
                p.name,
                p.category,
                latest_inventory.current_stock,
                latest_forecast.forecast_quantity,
                CASE
                    WHEN latest_forecast.forecast_quantity IS NULL THEN 'unknown'
                    WHEN latest_inventory.current_stock
                        <= latest_forecast.forecast_quantity
                        THEN 'stockout_risk'
                    WHEN latest_forecast.forecast_quantity > 0
                         AND latest_inventory.current_stock
                             >= latest_forecast.forecast_quantity * 3
                        THEN 'overstock_risk'
                    ELSE 'normal'
                END AS risk_status,
                latest_inventory.inventory_updated_at
            FROM products p
            JOIN latest_inventory ON latest_inventory.product_id = p.id
            LEFT JOIN latest_forecast ON latest_forecast.product_id = p.id
            WHERE p.id = %s;
            """,
            (product_id, product_id, product_id),
        )

    def list_sales(self, product_id: UUID, limit: int) -> list[dict[str, Any]]:
        return fetch_all(
            """
            SELECT
                id,
                product_id,
                quantity,
                sold_at,
                unit_price::float AS unit_price,
                total_amount::float AS total_amount,
                currency,
                channel,
                created_at
            FROM sales
            WHERE product_id = %s
            ORDER BY sold_at DESC NULLS LAST
            LIMIT %s;
            """,
            (product_id, limit),
        )

    def list_inventory_snapshots(
        self,
        product_id: UUID,
        limit: int,
    ) -> list[dict[str, Any]]:
        return fetch_all(
            """
            SELECT
                id,
                product_id,
                stock_quantity,
                unit_of_measure,
                warehouse_code,
                recorded_at,
                ingested_at,
                created_at
            FROM inventory_snapshots
            WHERE product_id = %s
            ORDER BY recorded_at DESC NULLS LAST
            LIMIT %s;
            """,
            (product_id, limit),
        )

    def list_forecasts(self, product_id: UUID, limit: int) -> list[dict[str, Any]]:
        return fetch_all(
            """
            SELECT
                id,
                product_id,
                forecast_period_start,
                forecast_period_end,
                predicted_quantity::float AS predicted_quantity,
                unit_of_measure,
                generated_at,
                method,
                status,
                confidence_level::float AS confidence_level
            FROM forecasts
            WHERE product_id = %s
            ORDER BY generated_at DESC NULLS LAST
            LIMIT %s;
            """,
            (product_id, limit),
        )

    def list_anomalies(self, product_id: UUID, limit: int) -> list[dict[str, Any]]:
        return fetch_all(
            """
            SELECT
                id,
                product_id,
                anomaly_type,
                metric_name,
                actual_value::float AS actual_value,
                expected_value::float AS expected_value,
                deviation_percent::float AS deviation_percent,
                impact_value::float AS impact_value,
                impact_unit,
                severity,
                period_start,
                period_end,
                detected_at
            FROM anomalies
            WHERE product_id = %s
            ORDER BY detected_at DESC NULLS LAST
            LIMIT %s;
            """,
            (product_id, limit),
        )

    def list_alerts(self, product_id: UUID, limit: int) -> list[dict[str, Any]]:
        return fetch_all(
            """
            SELECT
                id,
                product_id,
                anomaly_id,
                assigned_to_user_id,
                alert_type,
                severity,
                status,
                title,
                recommended_action,
                created_at,
                updated_at
            FROM alerts
            WHERE product_id = %s
            ORDER BY created_at DESC NULLS LAST
            LIMIT %s;
            """,
            (product_id, limit),
        )

    def list_recommendations(
        self,
        product_id: UUID,
        limit: int,
    ) -> list[dict[str, Any]]:
        return fetch_all(
            """
            SELECT
                id,
                product_id,
                forecast_id,
                anomaly_id,
                alert_id,
                recommendation_type,
                recommended_action,
                rationale,
                status,
                generated_at,
                expires_at,
                created_at
            FROM recommendations
            WHERE product_id = %s
            ORDER BY generated_at DESC NULLS LAST
            LIMIT %s;
            """,
            (product_id, limit),
        )

    def list_workflow_actions(
        self,
        product_id: UUID,
        limit: int,
    ) -> list[dict[str, Any]]:
        return fetch_all(
            """
            SELECT
                wa.id,
                wa.alert_id,
                wa.performed_by_user_id,
                wa.action_type,
                wa.comment,
                wa.previous_status,
                wa.new_status,
                wa.performed_at,
                wa.created_at,
                a.title AS alert_title,
                u.login AS performed_by_login
            FROM workflow_actions wa
            JOIN alerts a ON a.id = wa.alert_id
            LEFT JOIN users u ON u.id = wa.performed_by_user_id
            WHERE a.product_id = %s
            ORDER BY COALESCE(wa.performed_at, wa.created_at) DESC NULLS LAST
            LIMIT %s;
            """,
            (product_id, limit),
        )
