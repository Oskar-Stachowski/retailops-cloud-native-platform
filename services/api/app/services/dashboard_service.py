"""Service layer for dashboard read models.

The service keeps FastAPI handlers thin and gives us one place for response
normalization, small business defaults, and future observability hooks.
"""

from datetime import datetime, timezone
from typing import Any

from app.repositories.dashboard_repository import DashboardRepository
from app.services.serialization import make_json_safe


class DashboardService:
    def __init__(self, repository: DashboardRepository | None = None) -> None:
        self.repository = repository or DashboardRepository()

    def get_summary(self) -> dict:
        summary = self.repository.get_summary()
        return make_json_safe({"summary": self._normalize_summary(summary)})

    def get_sales_trend(self, days: int = 14) -> dict:
        safe_days = min(max(days, 1), 90)
        items = self.repository.get_sales_trend(days=safe_days)
        return make_json_safe({"items": items, "days": safe_days})

    def get_open_alerts(self, limit: int = 10) -> dict:
        safe_limit = min(max(limit, 1), 100)
        rows = self.repository.get_open_alerts(limit=safe_limit)
        return make_json_safe(
            {
                "items": [self._normalize_work_item(row) for row in rows],
                "limit": safe_limit,
            }
        )

    def get_top_recommendations(self, limit: int = 10) -> dict:
        safe_limit = min(max(limit, 1), 100)
        rows = self.repository.get_top_recommendations(limit=safe_limit)
        return make_json_safe(
            {
                "items": [self._normalize_work_item(row) for row in rows],
                "limit": safe_limit,
            }
        )

    def get_open_work_items(self, limit: int = 10) -> dict:
        safe_limit = min(max(limit, 1), 100)
        rows = self.repository.get_open_work_items(limit=safe_limit)
        return make_json_safe(
            {
                "items": [self._normalize_work_item(row) for row in rows],
                "limit": safe_limit,
            }
        )

    def get_stock_risk_summary(self) -> dict:
        summary = self.repository.get_stock_risk_summary()
        return make_json_safe(self._normalize_stock_risk_summary(summary))

    def get_operational_visibility(
        self,
        sales_trend_days: int = 14,
        work_items_limit: int = 10,
    ) -> dict:
        safe_days = min(max(sales_trend_days, 1), 90)
        safe_limit = min(max(work_items_limit, 1), 100)

        summary = self._normalize_summary(self.repository.get_summary())
        stock_risk_summary = self._normalize_stock_risk_summary(
            self.repository.get_stock_risk_summary()
        )
        sales_trend = self.repository.get_sales_trend(days=safe_days)
        open_work_items = [
            self._normalize_work_item(row)
            for row in self.repository.get_open_work_items(limit=safe_limit)
        ]

        return make_json_safe(
            {
                "generated_at": datetime.now(timezone.utc),
                "summary": summary,
                "stock_risk_summary": stock_risk_summary,
                "sales_trend": sales_trend,
                "open_work_items": open_work_items,
                "limits": {
                    "sales_trend_days": safe_days,
                    "work_items_limit": safe_limit,
                },
            }
        )

    def _normalize_summary(self, summary: dict[str, Any]) -> dict[str, Any]:
        """Keep the public dashboard summary schema stable."""
        return {
            "products_count": int(summary.get("products_count", 0)),
            "sales_count": int(summary.get("sales_count", 0)),
            "inventory_snapshots_count": int(
                summary.get("inventory_snapshots_count", 0)
            ),
            "forecasts_count": int(summary.get("forecasts_count", 0)),
            "anomalies_count": int(summary.get("anomalies_count", 0)),
            "recommendations_count": int(summary.get("recommendations_count", 0)),
            "open_anomalies_count": int(summary.get("open_anomalies_count", 0)),
            "open_recommendations_count": int(
                summary.get("open_recommendations_count", 0)
            ),
            "open_work_items_count": int(summary.get("open_work_items_count", 0)),
            "last_refresh_at": summary.get("last_refresh_at"),
        }

    def _normalize_stock_risk_summary(self, summary: dict[str, Any]) -> dict[str, int]:
        return {
            "total_risk_items": int(summary.get("total_risk_items", 0)),
            "normal_count": int(summary.get("normal_count", 0)),
            "stockout_risk_count": int(summary.get("stockout_risk_count", 0)),
            "overstock_risk_count": int(summary.get("overstock_risk_count", 0)),
            "unknown_count": int(summary.get("unknown_count", 0)),
        }

    def _normalize_work_item(self, row: dict[str, Any]) -> dict[str, Any]:
        work_item_type = (
            row.get("anomaly_type")
            or row.get("recommendation_type")
            or row.get("type")
        )
        description = (
            row.get("description")
            or row.get("message")
            or row.get("reason")
        )

        return {
            "id": str(row.get("id")),
            "source": str(row.get("source") or "unknown"),
            "product_id": str(row["product_id"]) if row.get("product_id") else None,
            "sku": row.get("sku"),
            "type": work_item_type,
            "severity": row.get("severity"),
            "priority": row.get("priority"),
            "status": row.get("status"),
            "title": row.get("title"),
            "description": description,
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
            "detected_at": row.get("detected_at"),
        }


dashboard_service = DashboardService()
