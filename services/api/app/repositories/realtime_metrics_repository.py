from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datetime import datetime

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.db.connection import fetch_all, fetch_one, get_connection
from app.db.introspection import table_exists


class RealtimeMetricsRepository:
    """Persistence layer for real-time event processing state and metrics."""

    def __init__(self, connection: object | None = None) -> None:
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
            with get_connection() as connection, connection.cursor() as cursor:
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
            with get_connection() as connection, connection.cursor() as cursor:
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

    def get_live_metric_totals(self, window_minutes: int) -> list[dict[str, Any]]:
        if not table_exists("live_metric_observations"):
            return []

        return self._fetch_all(
            """
            SELECT
                metric_name,
                COALESCE(SUM(metric_value), 0)::float AS metric_value,
                COUNT(*)::int AS observation_count,
                MAX(observed_at) AS latest_observed_at
            FROM live_metric_observations
            WHERE observed_at >= now() - (%s::int * INTERVAL '1 minute')
            GROUP BY metric_name
            ORDER BY metric_name ASC;
            """,
            (window_minutes,),
        )

    def get_event_status_counts(self, window_minutes: int) -> list[dict[str, Any]]:
        if not table_exists("realtime_event_log"):
            return []

        return self._fetch_all(
            """
            SELECT
                status,
                COUNT(*)::int AS event_count
            FROM realtime_event_log
            WHERE ingested_at >= now() - (%s::int * INTERVAL '1 minute')
            GROUP BY status
            ORDER BY status ASC;
            """,
            (window_minutes,),
        )

    def get_event_freshness(self) -> dict[str, Any] | None:
        if not table_exists("realtime_event_log"):
            return None

        return self._fetch_one(
            """
            SELECT
                MAX(ingested_at) AS latest_event_at,
                EXTRACT(EPOCH FROM (now() - MAX(ingested_at)))::float
                    AS freshness_seconds
            FROM realtime_event_log;
            """,
        )

    def get_recent_events(self, limit: int) -> list[dict[str, Any]]:
        if not table_exists("realtime_event_log"):
            return []

        return self._fetch_all(
            """
            SELECT
                event_id,
                event_type,
                topic,
                status,
                occurred_at,
                ingested_at,
                processed_at,
                error_message
            FROM realtime_event_log
            ORDER BY ingested_at DESC, occurred_at DESC
            LIMIT %s;
            """,
            (limit,),
        )

    def get_recent_operational_alerts(self, limit: int) -> list[dict[str, Any]]:
        if not table_exists("realtime_event_log"):
            return []

        return self._fetch_all(
            """
            SELECT
                event_id,
                event_type,
                status,
                occurred_at,
                ingested_at,
                payload
            FROM realtime_event_log
            WHERE event_type IN ('alert_created', 'anomaly_detected')
            ORDER BY ingested_at DESC, occurred_at DESC
            LIMIT %s;
            """,
            (limit,),
        )

    def get_consumer_states(self) -> list[dict[str, Any]]:
        if not table_exists("realtime_consumer_state"):
            return []

        return self._fetch_all(
            """
            SELECT
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
            FROM realtime_consumer_state
            ORDER BY updated_at DESC, consumer_name ASC;
            """,
        )

    def get_stream_processing_metrics(self) -> dict[str, Any]:
        return {
            "event_status_counts": self.get_all_event_status_counts(),
            "event_type_counts": self.get_all_event_type_counts(),
            "freshness": self.get_event_freshness() or {},
            "processing_latency": self.get_processing_latency_summary() or {},
            "consumer_states": self.get_consumer_states(),
        }

    def get_all_event_status_counts(self) -> list[dict[str, Any]]:
        if not table_exists("realtime_event_log"):
            return []

        return self._fetch_all(
            """
            SELECT
                status,
                COUNT(*)::int AS event_count
            FROM realtime_event_log
            GROUP BY status
            ORDER BY status ASC;
            """,
        )

    def get_all_event_type_counts(self) -> list[dict[str, Any]]:
        if not table_exists("realtime_event_log"):
            return []

        return self._fetch_all(
            """
            SELECT
                event_type,
                COUNT(*)::int AS event_count
            FROM realtime_event_log
            GROUP BY event_type
            ORDER BY event_type ASC;
            """,
        )

    def get_processing_latency_summary(self) -> dict[str, Any] | None:
        if not table_exists("realtime_event_log"):
            return None

        return self._fetch_one(
            """
            SELECT
                COUNT(*)::int AS processed_event_count,
                AVG(EXTRACT(EPOCH FROM (processed_at - ingested_at)))::float
                    AS avg_latency_seconds,
                MAX(EXTRACT(EPOCH FROM (processed_at - ingested_at)))::float
                    AS max_latency_seconds
            FROM realtime_event_log
            WHERE processed_at IS NOT NULL
              AND ingested_at IS NOT NULL;
            """,
        )

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
                Jsonb(payload),
            ),
        )

    def _fetch_all(
        self,
        query: str,
        params: tuple[Any, ...] = (),
    ) -> list[dict[str, Any]]:
        if self.connection is None:
            return fetch_all(query, params)

        with self.connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

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

        rows: list[tuple[Any, ...]] = [
            (
                event_id,
                observation["metric_name"],
                self._normalize_metric_value(observation["metric_value"]),
                observation.get("dimension_key") or "",
                observation["source_event_type"],
                observation["observed_at"],
            )
            for observation in observations
        ]

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

    def _normalize_metric_value(self, value: object) -> Decimal:
        if isinstance(value, Decimal):
            return value

        return Decimal(str(value))
