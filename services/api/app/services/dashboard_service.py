"""Service layer for dashboard read models.

The service keeps FastAPI handlers thin and gives us one place for response
normalization, small business defaults, and future observability hooks.
"""

from datetime import UTC, datetime
from typing import Any

from app.repositories.dashboard_repository import DashboardRepository
from app.repositories.realtime_metrics_repository import RealtimeMetricsRepository
from app.services.serialization import make_json_safe

LIVE_EVENT_FRESHNESS_SECONDS = 300


class DashboardService:
    def __init__(
        self,
        repository: DashboardRepository | None = None,
        realtime_repository: RealtimeMetricsRepository | None = None,
    ) -> None:
        self.repository = repository or DashboardRepository()
        self.realtime_repository = realtime_repository or RealtimeMetricsRepository()

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
            },
        )

    def get_top_recommendations(self, limit: int = 10) -> dict:
        safe_limit = min(max(limit, 1), 100)
        rows = self.repository.get_top_recommendations(limit=safe_limit)
        return make_json_safe(
            {
                "items": [self._normalize_work_item(row) for row in rows],
                "limit": safe_limit,
            },
        )

    def get_open_work_items(self, limit: int = 10) -> dict:
        safe_limit = min(max(limit, 1), 100)
        rows = self.repository.get_open_work_items(limit=safe_limit)
        return make_json_safe(
            {
                "items": [self._normalize_work_item(row) for row in rows],
                "limit": safe_limit,
            },
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
            self.repository.get_stock_risk_summary(),
        )
        sales_trend = self.repository.get_sales_trend(days=safe_days)
        open_work_items = [
            self._normalize_work_item(row)
            for row in self.repository.get_open_work_items(limit=safe_limit)
        ]

        return make_json_safe(
            {
                "generated_at": datetime.now(UTC),
                "summary": summary,
                "stock_risk_summary": stock_risk_summary,
                "sales_trend": sales_trend,
                "open_work_items": open_work_items,
                "limits": {
                    "sales_trend_days": safe_days,
                    "work_items_limit": safe_limit,
                },
            },
        )

    def get_live_operations(
        self,
        window_minutes: int = 15,
        recent_events_limit: int = 20,
        alerts_limit: int = 10,
    ) -> dict:
        safe_window = min(max(window_minutes, 1), 240)
        safe_recent_events_limit = min(max(recent_events_limit, 1), 100)
        safe_alerts_limit = min(max(alerts_limit, 1), 100)

        metric_rows = self.realtime_repository.get_live_metric_totals(window_minutes=safe_window)
        status_rows = self.realtime_repository.get_event_status_counts(window_minutes=safe_window)
        freshness = self.realtime_repository.get_event_freshness() or {}
        recent_events = self.realtime_repository.get_recent_events(limit=safe_recent_events_limit)
        alerts = self.realtime_repository.get_recent_operational_alerts(limit=safe_alerts_limit)
        consumer_states = self.realtime_repository.get_consumer_states()

        return make_json_safe(
            {
                "generated_at": datetime.now(UTC),
                "window_minutes": safe_window,
                "metrics": self._normalize_live_metrics(metric_rows),
                "event_status_counts": self._normalize_event_status_counts(status_rows),
                "freshness": self._normalize_event_freshness(freshness),
                "recent_events": [self._normalize_live_event(row) for row in recent_events],
                "alerts": [self._normalize_live_alert(row) for row in alerts],
                "consumer_states": [self._normalize_consumer_state(row) for row in consumer_states],
                "limits": {
                    "recent_events": safe_recent_events_limit,
                    "alerts": safe_alerts_limit,
                },
            },
        )

    def _normalize_summary(self, summary: dict[str, Any]) -> dict[str, Any]:
        """Keep the public dashboard summary schema stable."""
        return {
            "products_count": int(summary.get("products_count", 0)),
            "sales_count": int(summary.get("sales_count", 0)),
            "inventory_snapshots_count": int(summary.get("inventory_snapshots_count", 0)),
            "forecasts_count": int(summary.get("forecasts_count", 0)),
            "anomalies_count": int(summary.get("anomalies_count", 0)),
            "recommendations_count": int(summary.get("recommendations_count", 0)),
            "open_anomalies_count": int(summary.get("open_anomalies_count", 0)),
            "open_recommendations_count": int(summary.get("open_recommendations_count", 0)),
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

    def _normalize_live_metrics(
        self,
        rows: list[dict[str, Any]],
    ) -> dict[str, Any]:
        metrics = {
            row["metric_name"]: {
                "value": float(row.get("metric_value") or 0),
                "observation_count": int(row.get("observation_count") or 0),
                "latest_observed_at": row.get("latest_observed_at"),
            }
            for row in rows
        }

        def value(metric_name: str) -> float:
            return float(metrics.get(metric_name, {}).get("value", 0))

        return {
            "revenue": value("live_revenue"),
            "units_sold": value("live_units_sold"),
            "orders_created": value("live_orders_created"),
            "sales_events": value("live_sale_events"),
            "return_amount": value("live_return_amount"),
            "return_units": value("live_return_units"),
            "stock_delta": value("live_stock_delta"),
            "stock_events": value("live_stock_events"),
            "replenishment_units": value("live_replenishment_units"),
            "anomalies_detected": value("live_anomalies_detected"),
            "alerts_created": value("live_alerts_created"),
            "workflow_actions": value("live_workflow_actions"),
            "raw_metrics": metrics,
        }

    def _normalize_event_status_counts(
        self,
        rows: list[dict[str, Any]],
    ) -> dict[str, int]:
        counts = {str(row.get("status")): int(row.get("event_count") or 0) for row in rows}
        return {
            "received": counts.get("received", 0),
            "processed": counts.get("processed", 0),
            "failed_dead_lettered": counts.get("failed_dead_lettered", 0),
            "ignored_duplicate": counts.get("ignored_duplicate", 0),
            "total": sum(counts.values()),
        }

    def _normalize_event_freshness(
        self,
        row: dict[str, Any],
    ) -> dict[str, Any]:
        latest_event_at = row.get("latest_event_at")
        freshness_seconds = row.get("freshness_seconds")
        return {
            "latest_event_at": latest_event_at,
            "freshness_seconds": (
                max(float(freshness_seconds), 0.0) if freshness_seconds is not None else None
            ),
            "is_fresh": (
                freshness_seconds is not None
                and float(freshness_seconds) <= LIVE_EVENT_FRESHNESS_SECONDS
            ),
        }

    def _normalize_live_event(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "event_id": str(row.get("event_id")),
            "event_type": row.get("event_type"),
            "topic": row.get("topic"),
            "status": row.get("status"),
            "occurred_at": row.get("occurred_at"),
            "ingested_at": row.get("ingested_at"),
            "processed_at": row.get("processed_at"),
            "error_message": row.get("error_message"),
        }

    def _normalize_live_alert(self, row: dict[str, Any]) -> dict[str, Any]:
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
        return {
            "event_id": str(row.get("event_id")),
            "event_type": row.get("event_type"),
            "status": row.get("status"),
            "occurred_at": row.get("occurred_at"),
            "ingested_at": row.get("ingested_at"),
            "product_id": payload.get("product_id"),
            "severity": payload.get("severity"),
            "title": payload.get("title") or payload.get("description"),
            "payload": payload,
        }

    def _normalize_consumer_state(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "consumer_name": row.get("consumer_name"),
            "running": bool(row.get("running")),
            "received_events": int(row.get("received_events") or 0),
            "processed_events": int(row.get("processed_events") or 0),
            "failed_events": int(row.get("failed_events") or 0),
            "dead_lettered_events": int(row.get("dead_lettered_events") or 0),
            "ignored_events": int(row.get("ignored_events") or 0),
            "last_event_id": (str(row.get("last_event_id")) if row.get("last_event_id") else None),
            "last_event_type": row.get("last_event_type"),
            "last_error": row.get("last_error"),
            "last_processed_at": row.get("last_processed_at"),
            "started_at": row.get("started_at"),
            "stopped_at": row.get("stopped_at"),
            "updated_at": row.get("updated_at"),
        }

    def _normalize_work_item(self, row: dict[str, Any]) -> dict[str, Any]:
        work_item_type = (
            row.get("anomaly_type") or row.get("recommendation_type") or row.get("type")
        )
        description = row.get("description") or row.get("message") or row.get("reason")

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
