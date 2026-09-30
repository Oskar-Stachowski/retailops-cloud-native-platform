from __future__ import annotations

import base64
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid5

from psycopg.types.json import Jsonb

from app.db.connection import fetch_all, fetch_one

QUARANTINE_SOURCE = "retailops.consumer.quarantine"
QUARANTINE_NAMESPACE = UUID("e69e3c54-5596-45b0-93d5-7e9289916db9")


class RealtimeQuarantineRepository:
    """Retain rejected bytes in the existing durable event log before ACK."""

    def store_message(
        self,
        *,
        consumer_group: str,
        topic: str,
        partition: int,
        offset: int,
        value: bytes | str | None,
        key: bytes | str | None,
        headers: list[tuple[str, bytes | None]] | None,
        timestamp_ms: int | None,
        error: str,
    ) -> dict[str, Any]:
        transport = {
            "consumer_group": consumer_group,
            "topic": topic,
            "partition": partition,
            "offset": offset,
            "key_base64": _encode(key),
            "headers_base64": [[name, _encode(value)] for name, value in (headers or [])],
            "timestamp_ms": timestamp_ms,
        }
        identity = json.dumps([consumer_group, topic, partition, offset], separators=(",", ":"))
        quarantine_id = str(uuid5(QUARANTINE_NAMESPACE, identity))
        payload = {"transport": transport, "value_base64": _encode(value)}
        now = datetime.now(UTC)
        occurred_at = (
            datetime.fromtimestamp(timestamp_ms / 1000, UTC)
            if timestamp_ms is not None and timestamp_ms >= 0
            else now
        )
        # A synthetic ID uses the transport position, never an untrusted event ID.
        # fetch_one returns only after the insert transaction has committed.
        fetch_one(
            """
            INSERT INTO realtime_event_log
                (event_id, event_type, topic, schema_version, source, correlation_id,
                 occurred_at, ingested_at, status, attempt_count, error_message, payload)
            VALUES (%s, 'transport_rejected', %s, 'transport.v1', %s, %s,
                    %s, %s, 'failed_dead_lettered', 1, %s, %s)
            ON CONFLICT (event_id) DO NOTHING RETURNING event_id;
            """,
            (
                quarantine_id,
                topic,
                QUARANTINE_SOURCE,
                quarantine_id,
                occurred_at,
                now,
                error,
                Jsonb(payload),
            ),
        )
        row = self.get(quarantine_id)
        if any(row["payload"].get(name) != content for name, content in payload.items()):
            msg = "Quarantine did not confirm the immutable transport message."
            raise RuntimeError(msg)
        return row

    def get(self, quarantine_id: str) -> dict[str, Any]:
        row = fetch_one(
            "SELECT * FROM realtime_event_log WHERE event_id = %s AND source = %s;",
            (quarantine_id, QUARANTINE_SOURCE),
        )
        if row is None:
            msg = f"Quarantined message {quarantine_id} does not exist."
            raise ValueError(msg)
        return row

    def pending(self, limit: int = 100) -> list[dict[str, Any]]:
        return fetch_all(
            """
            SELECT event_id, topic, error_message, created_at, payload->'transport' AS transport
            FROM realtime_event_log WHERE source = %s
                AND payload->'replay'->>'delivered_at' IS NULL
            ORDER BY created_at, event_id LIMIT %s;
            """,
            (QUARANTINE_SOURCE, limit),
        )

    def prepare_replay(
        self, quarantine_id: str, event: dict[str, Any], operator: str
    ) -> dict[str, Any]:
        intent = {"event": event, "operator": operator}
        row = fetch_one(
            """
            UPDATE realtime_event_log SET
                payload = CASE WHEN payload ? 'replay' THEN payload
                    ELSE jsonb_set(payload, '{replay}', %s) END,
                updated_at = now()
            WHERE event_id = %s AND source = %s
                AND (NOT payload ? 'replay' OR payload->'replay'->'event' = %s)
            RETURNING *;
            """,
            (Jsonb(intent), quarantine_id, QUARANTINE_SOURCE, Jsonb(event)),
        )
        if row is None:
            msg = "Replay intent is missing or differs from the already pinned event."
            raise ValueError(msg)
        return row

    def confirm_replay(self, quarantine_id: str, *, partition: int, offset: int) -> None:
        receipt = {
            "delivered_at": datetime.now(UTC).isoformat(),
            "partition": partition,
            "offset": offset,
        }
        row = fetch_one(
            """
            UPDATE realtime_event_log SET payload = jsonb_set(
                payload, '{replay}', payload->'replay' || %s), updated_at = now()
            WHERE event_id = %s AND source = %s AND payload ? 'replay'
                AND payload->'replay'->>'delivered_at' IS NULL
            RETURNING event_id;
            """,
            (Jsonb(receipt), quarantine_id, QUARANTINE_SOURCE),
        )
        if row is None and not self.get(quarantine_id)["payload"].get("replay", {}).get(
            "delivered_at"
        ):
            msg = "Could not confirm the replay delivery."
            raise RuntimeError(msg)


def _encode(value: bytes | str | None) -> str | None:
    if isinstance(value, str):
        value = value.encode("utf-8")
    return base64.b64encode(value).decode("ascii") if value is not None else None
