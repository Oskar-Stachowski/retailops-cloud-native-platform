"""Service layer for Product 360 read models."""

from typing import Any
from uuid import UUID

from app.repositories.product_360_repository import Product360Repository
from app.repositories.product_repository import ProductRepository
from app.services.serialization import make_json_safe


class Product360Service:
    """Builds a dashboard-ready Product 360 response.

    The service deliberately stays read-only. It composes existing product,
    sales, inventory, forecast, anomaly, alert, recommendation and workflow
    tables into one stable API contract for the frontend.
    """

    def __init__(
        self,
        product_repository: ProductRepository | None = None,
        product_360_repository: Product360Repository | None = None,
    ) -> None:
        self.product_repository = product_repository or ProductRepository()
        self.product_360_repository = product_360_repository or Product360Repository()

    def get_product_360(
        self,
        product_id: UUID,
        limit: int = 10,
    ) -> dict[str, Any] | None:
        safe_limit = min(max(limit, 1), 50)
        product = self.product_repository.get_product_by_id(product_id)

        if product is None:
            return None

        metrics = self.product_360_repository.get_metrics(product_id)
        stock_risk = self.product_360_repository.get_stock_risk(product_id)

        response = {
            "product": product.model_dump(),
            "metrics": self._normalize_metrics(metrics, stock_risk),
            "stock_risk": stock_risk,
            "sales": self.product_360_repository.list_sales(product_id, safe_limit),
            "inventory_snapshots": self.product_360_repository.list_inventory_snapshots(
                product_id,
                safe_limit,
            ),
            "forecasts": self.product_360_repository.list_forecasts(
                product_id,
                safe_limit,
            ),
            "anomalies": self.product_360_repository.list_anomalies(
                product_id,
                safe_limit,
            ),
            "alerts": self.product_360_repository.list_alerts(product_id, safe_limit),
            "recommendations": self.product_360_repository.list_recommendations(
                product_id,
                safe_limit,
            ),
            "workflow_actions": self.product_360_repository.list_workflow_actions(
                product_id,
                safe_limit,
            ),
            "limits": {"related_items": safe_limit},
        }

        return make_json_safe(response)

    def _normalize_metrics(
        self,
        metrics: dict[str, Any],
        stock_risk: dict[str, Any] | None,
    ) -> dict[str, Any]:
        return {
            "sales_count": int(metrics.get("sales_count") or 0),
            "total_units_sold": float(metrics.get("total_units_sold") or 0),
            "total_revenue": float(metrics.get("total_revenue") or 0),
            "latest_sale_at": metrics.get("latest_sale_at"),
            "inventory_snapshot_count": int(
                metrics.get("inventory_snapshot_count") or 0
            ),
            "current_stock": self._optional_float(metrics.get("current_stock")),
            "inventory_updated_at": metrics.get("inventory_updated_at"),
            "forecast_count": int(metrics.get("forecast_count") or 0),
            "latest_forecast_quantity": self._optional_float(
                metrics.get("latest_forecast_quantity")
            ),
            "latest_forecast_period_start": metrics.get(
                "latest_forecast_period_start"
            ),
            "latest_forecast_period_end": metrics.get("latest_forecast_period_end"),
            "anomaly_count": int(metrics.get("anomaly_count") or 0),
            "alert_count": int(metrics.get("alert_count") or 0),
            "open_alert_count": int(metrics.get("open_alert_count") or 0),
            "recommendation_count": int(metrics.get("recommendation_count") or 0),
            "open_recommendation_count": int(
                metrics.get("open_recommendation_count") or 0
            ),
            "workflow_action_count": int(metrics.get("workflow_action_count") or 0),
            "risk_status": (stock_risk or {}).get("risk_status") or "unknown",
        }

    @staticmethod
    def _optional_float(value: Any) -> float | None:
        if value is None:
            return None
        return float(value)


product_360_service = Product360Service()
