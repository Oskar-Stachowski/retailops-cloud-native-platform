from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from psycopg.rows import dict_row

from app.db.connection import fetch_one, get_connection


class RealtimeMetricsRepository:
    """Persistence layer for real-time event processing state and metrics."""

    def __init__(self, connection=None) -> None:
        self.connection = connection

    def _fetch_one(
        self,
        query: str,
        params: tuple[Any, ...] = (),
    ) -> dict[str, Any] | None:
        if self.connection is None:
            return fetch_one(query, params)

        with self.connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(query, params)
            row = cursor.fetchone()
            return dict(row) if row is not None else None

    def _execute(
        self,
        query: str,
        params: tuple[Any, ...] = (),
    ) -> None:
        if self.connection is None:
            with get_connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(query, params)
            return

        with self.connection.cursor() as cursor:
            cursor.execute(query, params)

    def _executemany(
        self,
        query: str,
        rows: list[tuple[Any, ...]],
    ) -> None:
        if not rows:
            return

        if self.connection is None:
            with get_connection() as connection:
                with connection.cursor() as cursor:
                    cursor.executemany(query, rows)
            return

        with self.connection.cursor() as cursor:
            cursor.executemany(query, rows)

    def get_event_record(self, event_id: str) -> dict[str, Any] | None:
        return self._fetch_one(
            """
            SELECT
                event_id,
                event_type,
                topic,
                schema_version,
                source,
                correlation_id,
                occurred_at,
                ingested_at,
                processed_at,
                status,
                attempt_count,
                error_message,
                payload,
                created_at,
                updated_at
            FROM realtime_event_log
            WHERE event_id = %s;
            """,
            (event_id,),
        )

    def is_event_processed(self, event_id: str) -> bool:
        row = self.get_event_record(event_id)
        return bool(row and row.get("status") == "processed")

    def record_event_log(
        self,
        *,
        event_id: str,
        event_type: str,
        topic: str,
        schema_version: str,
        source: str,
        correlation_id: str,
        occurred_at: datetime,
        ingested_at: datetime,
        payload: dict[str, Any],
        status: str,
        processed_at: datetime | None = None,
        error_message: str | None = None,
    ) -> dict[str, Any]:
        return self._fetch_one(
            """
            INSERT INTO realtime_event_log (
                event_id,
                event_type,
                topic,
                schema_version,
                source,
                correlation_id,
                occurred_at,
                ingested_at,
                processed_at,
                status,
                attempt_count,
                error_message,
                payload,
                created_at,
                updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1, %s, %s, now(), now()
            )
            ON CONFLICT (event_id) DO UPDATE SET
                event_type = EXCLUDED.event_type,
                topic = EXCLUDED.topic,
                schema_version = EXCLUDED.schema_version,
                source = EXCLUDED.source,
                correlation_id = EXCLUDED.correlation_id,
                occurred_at = EXCLUDED.occurred_at,
                ingested_at = EXCLUDED.ingested_at,
                processed_at = EXCLUDED.processed_at,
                status = EXCLUDED.status,
                attempt_count = realtime_event_log.attempt_count + 1,
                error_message = EXCLUDED.error_message,
                payload = EXCLUDED.payload,
                updated_at = now()
            RETURNING
                event_id,
                event_type,
                topic,
                schema_version,
                source,
                correlation_id,
                occurred_at,
                ingested_at,
                processed_at,
                status,
                attempt_count,
                error_message,
                payload,
                created_at,
                updated_at;
            """,
            (
                event_id,
                event_type,
                topic,
                schema_version,
                source,
                correlation_id,
                occurred_at,
                ingested_at,
                processed_at,
                status,
                error_message,
                payload,
            ),
        )

    def replace_metric_observations(
        self,
        *,
        event_id: str,
        observations: list[dict[str, Any]],
    ) -> int:
        self._execute(
            """
            DELETE FROM live_metric_observations
            WHERE event_id = %s;
            """,
            (event_id,),
        )

        rows: list[tuple[Any, ...]] = []
        for observation in observations:
            rows.append(
                (
                    event_id,
                    observation["metric_name"],
                    self._normalize_metric_value(observation["metric_value"]),
                    observation.get("dimension_key") or "",
                    observation["source_event_type"],
                    observation["observed_at"],
                )
            )

        self._executemany(
            """
            INSERT INTO live_metric_observations (
                event_id,
                metric_name,
                metric_value,
                dimension_key,
                source_event_type,
                observed_at
            ) VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (event_id, metric_name, dimension_key) DO UPDATE SET
                metric_value = EXCLUDED.metric_value,
                source_event_type = EXCLUDED.source_event_type,
                observed_at = EXCLUDED.observed_at;
            """,
            rows,
        )

        return len(rows)

    def upsert_consumer_state(
        self,
        *,
        consumer_name: str,
        running: bool,
        received_events: int,
        processed_events: int,
        failed_events: int,
        dead_lettered_events: int,
        ignored_events: int,
        last_event_id: str | None,
        last_event_type: str | None,
        last_error: str | None,
        last_processed_at: datetime | None,
        started_at: datetime | None,
        stopped_at: datetime | None,
    ) -> dict[str, Any]:
        return self._fetch_one(
            """
            INSERT INTO realtime_consumer_state (
                consumer_name,
                running,
                received_events,
                processed_events,
                failed_events,
                dead_lettered_events,
                ignored_events,
                last_event_id,
                last_event_type,
                last_error,
                last_processed_at,
                started_at,
                stopped_at,
                updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now()
            )
            ON CONFLICT (consumer_name) DO UPDATE SET
                running = EXCLUDED.running,
                received_events = EXCLUDED.received_events,
                processed_events = EXCLUDED.processed_events,
                failed_events = EXCLUDED.failed_events,
                dead_lettered_events = EXCLUDED.dead_lettered_events,
                ignored_events = EXCLUDED.ignored_events,
                last_event_id = EXCLUDED.last_event_id,
                last_event_type = EXCLUDED.last_event_type,
                last_error = EXCLUDED.last_error,
                last_processed_at = EXCLUDED.last_processed_at,
                started_at = EXCLUDED.started_at,
                stopped_at = EXCLUDED.stopped_at,
                updated_at = now()
            RETURNING
                consumer_name,
                running,
                received_events,
                processed_events,
                failed_events,
                dead_lettered_events,
                ignored_events,
                last_event_id,
                last_event_type,
                last_error,
                last_processed_at,
                started_at,
                stopped_at,
                updated_at;
            """,
            (
                consumer_name,
                running,
                received_events,
                processed_events,
                failed_events,
                dead_lettered_events,
                ignored_events,
                last_event_id,
                last_event_type,
                last_error,
                last_processed_at,
                started_at,
                stopped_at,
            ),
        )

    def _normalize_metric_value(self, value: Any) -> Decimal:
        if isinstance(value, Decimal):
            return value

        return Decimal(str(value))
