from datetime import datetime, timezone

from app.services.dashboard_service import DashboardService


class EmptyDashboardRepository:
    pass


class FakeRealtimeRepository:
    def get_live_metric_totals(self, window_minutes: int):
        return [
            {
                "metric_name": "live_revenue",
                "metric_value": 499.40,
                "observation_count": 12,
                "latest_observed_at": datetime(2026, 5, 7, 10, tzinfo=timezone.utc),
            },
            {
                "metric_name": "live_stock_delta",
                "metric_value": -7,
                "observation_count": 3,
                "latest_observed_at": datetime(2026, 5, 7, 10, tzinfo=timezone.utc),
            },
        ]

    def get_event_status_counts(self, window_minutes: int):
        return [
            {"status": "processed", "event_count": 15},
            {"status": "failed_dead_lettered", "event_count": 1},
        ]

    def get_event_freshness(self):
        return {
            "latest_event_at": datetime(2026, 5, 7, 10, tzinfo=timezone.utc),
            "freshness_seconds": 42,
        }

    def get_recent_events(self, limit: int):
        return [
            {
                "event_id": "01HXZ7M8E5K9Q3Q76W7J7Y5YV2",
                "event_type": "sale_completed",
                "topic": "retailops.sales.v1",
                "status": "processed",
                "occurred_at": datetime(2026, 5, 7, 9, 59, tzinfo=timezone.utc),
                "ingested_at": datetime(2026, 5, 7, 10, tzinfo=timezone.utc),
                "processed_at": datetime(2026, 5, 7, 10, 0, 1, tzinfo=timezone.utc),
                "error_message": None,
            }
        ]

    def get_recent_operational_alerts(self, limit: int):
        return [
            {
                "event_id": "01HXZ7M8E5K9Q3Q76W7J7Y5YV3",
                "event_type": "alert_created",
                "status": "processed",
                "occurred_at": datetime(2026, 5, 7, 9, 58, tzinfo=timezone.utc),
                "ingested_at": datetime(2026, 5, 7, 9, 58, 1, tzinfo=timezone.utc),
                "payload": {
                    "product_id": "product-1",
                    "severity": "high",
                    "title": "Potential stockout risk",
                },
            }
        ]

    def get_consumer_states(self):
        return [
            {
                "consumer_name": "retailops-realtime-consumer",
                "running": True,
                "received_events": 18,
                "processed_events": 15,
                "failed_events": 1,
                "dead_lettered_events": 1,
                "ignored_events": 2,
                "last_event_id": "01HXZ7M8E5K9Q3Q76W7J7Y5YV2",
                "last_event_type": "sale_completed",
                "last_error": None,
                "last_processed_at": datetime(
                    2026, 5, 7, 10, 0, 1, tzinfo=timezone.utc
                ),
                "started_at": datetime(2026, 5, 7, 9, tzinfo=timezone.utc),
                "stopped_at": None,
                "updated_at": datetime(2026, 5, 7, 10, 0, 1, tzinfo=timezone.utc),
            }
        ]


def test_dashboard_service_builds_live_operations_read_model():
    service = DashboardService(
        repository=EmptyDashboardRepository(),
        realtime_repository=FakeRealtimeRepository(),
    )

    payload = service.get_live_operations(
        window_minutes=15,
        recent_events_limit=5,
        alerts_limit=3,
    )

    assert payload["window_minutes"] == 15
    assert payload["metrics"]["revenue"] == 499.40
    assert payload["metrics"]["stock_delta"] == -7
    assert payload["event_status_counts"]["processed"] == 15
    assert payload["event_status_counts"]["failed_dead_lettered"] == 1
    assert payload["event_status_counts"]["total"] == 16
    assert payload["freshness"]["is_fresh"] is True
    assert payload["recent_events"][0]["event_type"] == "sale_completed"
    assert payload["alerts"][0]["severity"] == "high"
    assert payload["consumer_states"][0]["processed_events"] == 15
