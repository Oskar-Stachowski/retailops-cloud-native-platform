from datetime import datetime, timezone
from decimal import Decimal

from app.repositories.realtime_metrics_repository import (
    RealtimeMetricsRepository,
)


class FakeCursor:
    def __init__(self, fetchone_result=None) -> None:
        self.fetchone_result = fetchone_result
        self.fetchall_result = []
        self.executed: list[tuple[str, tuple | None]] = []
        self.executemany_calls: list[tuple[str, list[tuple]]] = []

    def execute(self, query, params=None):
        self.executed.append((str(query).strip(), params))

    def executemany(self, query, rows):
        self.executemany_calls.append((str(query).strip(), list(rows)))

    def fetchone(self):
        return self.fetchone_result

    def fetchall(self):
        return self.fetchall_result

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self.cursor_obj = cursor

    def cursor(self, *args, **kwargs):
        return self.cursor_obj


def test_realtime_metrics_repository_persists_event_log_and_state() -> None:
    event_row = {"event_id": "event-1", "status": "processed", "attempt_count": 2}
    cursor = FakeCursor(fetchone_result=event_row)
    repository = RealtimeMetricsRepository(connection=FakeConnection(cursor))

    result = repository.record_event_log(
        event_id="event-1",
        event_type="sale_completed",
        topic="retailops.sales.v1",
        schema_version="1.0",
        source="retailops.synthetic-generator",
        correlation_id="order-1",
        occurred_at=datetime(2026, 5, 7, tzinfo=timezone.utc),
        ingested_at=datetime(2026, 5, 7, 10, tzinfo=timezone.utc),
        payload={"quantity": 3},
        status="processed",
        processed_at=datetime(2026, 5, 7, 10, 1, tzinfo=timezone.utc),
    )

    assert result == event_row
    assert cursor.executed[0][0].startswith("INSERT INTO realtime_event_log")

    rows_written = repository.replace_metric_observations(
        event_id="event-1",
        observations=[
            {
                "metric_name": "live_revenue",
                "metric_value": Decimal("12.50"),
                "dimension_key": "product_id=product-1",
                "source_event_type": "sale_completed",
                "observed_at": datetime(2026, 5, 7, 10, tzinfo=timezone.utc),
            },
            {
                "metric_name": "live_units_sold",
                "metric_value": 3,
                "dimension_key": "",
                "source_event_type": "sale_completed",
                "observed_at": datetime(2026, 5, 7, 10, tzinfo=timezone.utc),
            },
        ],
    )

    assert rows_written == 2
    assert cursor.executed[1][0].startswith("DELETE FROM live_metric_observations")
    assert len(cursor.executemany_calls) == 1
    assert cursor.executemany_calls[0][1][0][3] == "product_id=product-1"
    assert cursor.executemany_calls[0][1][1][3] == ""

    state_row = repository.upsert_consumer_state(
        consumer_name="retailops-realtime-consumer",
        running=True,
        received_events=1,
        processed_events=1,
        failed_events=0,
        dead_lettered_events=0,
        ignored_events=0,
        last_event_id="event-1",
        last_event_type="sale_completed",
        last_error=None,
        last_processed_at=datetime(2026, 5, 7, 10, 1, tzinfo=timezone.utc),
        started_at=datetime(2026, 5, 7, 10, tzinfo=timezone.utc),
        stopped_at=None,
    )

    assert state_row == event_row
    assert cursor.executed[-1][0].startswith("INSERT INTO realtime_consumer_state")


def test_realtime_metrics_repository_reads_live_metric_totals(monkeypatch) -> None:
    cursor = FakeCursor()
    cursor.fetchall_result = [
        {
            "metric_name": "live_revenue",
            "metric_value": 499.4,
            "observation_count": 12,
            "latest_observed_at": datetime(2026, 5, 7, 10, tzinfo=timezone.utc),
        }
    ]
    repository = RealtimeMetricsRepository(connection=FakeConnection(cursor))
    monkeypatch.setattr(
        "app.repositories.realtime_metrics_repository.table_exists",
        lambda table_name: True,
    )

    rows = repository.get_live_metric_totals(window_minutes=15)

    assert rows[0]["metric_name"] == "live_revenue"
    assert cursor.executed[0][1] == (15,)
