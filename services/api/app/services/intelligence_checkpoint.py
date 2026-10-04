"""Atomic transport receipts and fencing for the serial intelligence lane."""

from __future__ import annotations

import base64
import hashlib
import json
import re
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import psycopg
from psycopg.rows import dict_row

from app.db.connection import get_database_url
from app.repositories.intelligence_repository import IntelligenceRepository
from app.repositories.realtime_quarantine_repository import RealtimeQuarantineRepository
from app.services.intelligence_contract import TOPIC, validate_event
from app.services.realtime_consumer import InvalidRealtimeEventError
from app.services.realtime_consumer_runner import decode_message_value

if TYPE_CHECKING:
    from collections.abc import Iterator
    from uuid import UUID


class CheckpointError(RuntimeError):
    """A fixed, safe reason for a fail-stop before broker acknowledgement."""


@dataclass(frozen=True)
class StreamIdentity:
    cluster_id: str
    topic_id: str

    def __post_init__(self) -> None:
        if any(
            not value
            or len(value) > 128
            or not re.fullmatch(pattern, value)
            or value == "AAAAAAAAAAAAAAAAAAAAAA"
            for value, pattern in (
                (self.cluster_id, r"[A-Za-z0-9._:-]+"),
                # confluent_kafka.Uuid uses standard unpadded Base64, including
                # '+' and '/'. Preserve its exact bytes; do not rewrite DB pins.
                (self.topic_id, r"[A-Za-z0-9._:+/-]+"),
            )
        ):
            msg = "broker_stream_identity_unavailable"
            raise CheckpointError(msg)


@dataclass(frozen=True)
class PartitionLease:
    group: str
    partition: int
    owner: UUID
    epoch: int
    start_offset: int
    resume_offset: int
    stream: StreamIdentity

    @property
    def coordinates(self) -> tuple[str, str, int]:
        return self.group, TOPIC, self.partition


@dataclass(frozen=True)
class TransportRecord:
    partition: int
    offset: int
    value: bytes | None
    key: bytes | None = None
    headers: tuple[tuple[str, bytes | None], ...] = ()
    timestamp_ms: int | None = None

    def __post_init__(self) -> None:
        if (
            type(self.partition) is not int
            or self.partition < 0
            or type(self.offset) is not int
            or not 0 <= self.offset < 9223372036854775807
        ):
            msg = "invalid_transport_position"
            raise CheckpointError(msg)

    def fingerprint(self) -> str:
        def encoded(value: bytes | None) -> str | None:
            return base64.b64encode(value).decode("ascii") if value is not None else None

        document = {
            "value": encoded(self.value),
            "key": encoded(self.key),
            "headers": [(key, encoded(value)) for key, value in self.headers],
            "timestamp_ms": self.timestamp_ms,
        }
        return hashlib.sha256(
            json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        ).hexdigest()


@contextmanager
def checkpoint_connection() -> Iterator[psycopg.Connection[dict[str, Any]]]:
    with psycopg.connect(get_database_url(), connect_timeout=3, row_factory=dict_row) as connection:
        connection.execute("SET LOCAL statement_timeout='3s'")
        yield connection


class IntelligenceCheckpointStore:
    def __init__(
        self,
        projection: IntelligenceRepository | None = None,
        quarantine: RealtimeQuarantineRepository | None = None,
    ) -> None:
        self.projection = projection or IntelligenceRepository()
        self.quarantine = quarantine or RealtimeQuarantineRepository()

    def claim(
        self,
        *,
        group: str,
        partition: int,
        owner: UUID,
        stream: StreamIdentity,
        low: int,
        high: int,
        committed: int | None,
        bootstrap: bool = False,
    ) -> PartitionLease:
        if (
            not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", group)
            or type(partition) is not int
            or partition < 0
            or type(low) is not int
            or type(high) is not int
            or not 0 <= low <= high
            or (committed is not None and (type(committed) is not int or committed < 0))
        ):
            msg = "invalid_partition_claim"
            raise CheckpointError(msg)
        coordinates = group, TOPIC, partition
        initial = max(low, committed if committed is not None else low)
        with checkpoint_connection() as connection:
            if bootstrap:
                connection.execute(
                    """INSERT INTO ai_intelligence_partitions
                    (consumer_group,topic,partition,cluster_id,topic_id,
                     coverage_start,next_offset,initial_policy)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                    (
                        *coordinates,
                        stream.cluster_id,
                        stream.topic_id,
                        initial,
                        initial,
                        "broker_commit" if committed is not None else "log_low",
                    ),
                )
            state = connection.execute(
                """SELECT * FROM ai_intelligence_partitions
                   WHERE consumer_group=%s AND topic=%s AND partition=%s FOR UPDATE""",
                coordinates,
            ).fetchone()
            if state is None:
                msg = "partition_bootstrap_required"
                raise CheckpointError(msg)
            if (state["cluster_id"], state["topic_id"]) != (stream.cluster_id, stream.topic_id):
                msg = "broker_stream_changed"
                raise CheckpointError(msg)
            next_offset = state["next_offset"]
            if low > next_offset:
                msg = "retention_gap"
                raise CheckpointError(msg)
            if high < next_offset:
                msg = "broker_log_rewound"
                raise CheckpointError(msg)
            if committed is not None and committed > next_offset:
                msg = "broker_checkpoint_ahead"
                raise CheckpointError(msg)
            # An absent Kafka commit resumes at the proven DB cursor. A retained
            # earlier commit deliberately replays immutable transport receipts.
            resume = next_offset if committed is None else max(low, committed)
            updated = connection.execute(
                """UPDATE ai_intelligence_partitions SET epoch=epoch+1,
                   owner_id=%s, claimed_at=clock_timestamp()
                   WHERE consumer_group=%s AND topic=%s AND partition=%s RETURNING epoch""",
                (owner, *coordinates),
            ).fetchone()
            assert updated is not None  # noqa: S101 - locked existing row
            return PartitionLease(
                group, partition, owner, updated["epoch"], state["coverage_start"], resume, stream
            )

    def release(self, lease: PartitionLease) -> None:
        with checkpoint_connection() as connection:
            connection.execute(
                """UPDATE ai_intelligence_partitions SET epoch=epoch+1,owner_id=NULL
                   WHERE consumer_group=%s AND topic=%s AND partition=%s
                     AND owner_id=%s AND epoch=%s""",
                (*lease.coordinates, lease.owner, lease.epoch),
            )

    def process(self, lease: PartitionLease, record: TransportRecord) -> dict[str, Any]:
        if record.partition != lease.partition:
            msg = "partition_not_owned"
            raise CheckpointError(msg)
        raw_hash = record.fingerprint()
        with checkpoint_connection() as connection:
            state = connection.execute(
                """SELECT * FROM ai_intelligence_partitions
                   WHERE consumer_group=%s AND topic=%s AND partition=%s FOR UPDATE""",
                lease.coordinates,
            ).fetchone()
            if state is None or state["owner_id"] != lease.owner or state["epoch"] != lease.epoch:
                msg = "partition_fenced"
                raise CheckpointError(msg)
            if (state["cluster_id"], state["topic_id"]) != (
                lease.stream.cluster_id,
                lease.stream.topic_id,
            ):
                msg = "broker_stream_changed"
                raise CheckpointError(msg)
            if record.offset > state["next_offset"]:
                msg = "partition_offset_gap"
                raise CheckpointError(msg)
            if record.offset < state["next_offset"]:
                old = connection.execute(
                    """SELECT raw_sha256,outcome FROM ai_intelligence_transport
                       WHERE consumer_group=%s AND topic=%s AND partition=%s AND offset_number=%s""",
                    (*lease.coordinates, record.offset),
                ).fetchone()
                if old is None or old["raw_sha256"] != raw_hash:
                    msg = "transport_identity_collision"
                    raise CheckpointError(msg)
                return {
                    "status": "quarantined"
                    if old["outcome"] == "quarantined"
                    else "ignored_duplicate",
                    "transport_replayed": True,
                    "checkpoint_next_offset": state["next_offset"],
                }
            prediction_id = quarantine_id = None
            try:
                try:
                    event = decode_message_value(record.value)
                except (ValueError, TypeError, RecursionError) as exc:
                    msg = "intelligence_message_invalid_json"
                    raise InvalidRealtimeEventError(msg) from exc
                validate_event(event, transport_topic=TOPIC)
                # Identity/schema poison cannot commit any partially staged result.
                with connection.transaction():
                    result = self.projection.project_on_connection(connection, event)
                if result["status"] not in ("processed", "ignored_duplicate"):
                    msg = "projection_receipt_missing"
                    raise CheckpointError(msg)
                prediction_id = result["prediction_id"]
                outcome = "projected" if result["status"] == "processed" else "duplicate"
            except InvalidRealtimeEventError as exc:
                row = self.quarantine.store_message(
                    consumer_group=lease.group,
                    topic=TOPIC,
                    partition=record.partition,
                    offset=record.offset,
                    value=record.value,
                    key=record.key,
                    headers=list(record.headers),
                    timestamp_ms=record.timestamp_ms,
                    error=str(exc),
                    connection=connection,
                )
                quarantine_id = row["event_id"]
                outcome = "quarantined"
                result = {"status": "quarantined"}
            connection.execute(
                """INSERT INTO ai_intelligence_transport
                   (consumer_group,topic,partition,offset_number,raw_sha256,outcome,
                    prediction_id,quarantine_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    *lease.coordinates,
                    record.offset,
                    raw_hash,
                    outcome,
                    prediction_id,
                    quarantine_id,
                ),
            )
            self.advance(connection, lease, record.offset + 1)
        return {**result, "checkpoint_next_offset": record.offset + 1, "transport_replayed": False}

    @staticmethod
    def advance(
        connection: psycopg.Connection[dict[str, Any]], lease: PartitionLease, next_offset: int
    ) -> None:
        updated = connection.execute(
            """UPDATE ai_intelligence_partitions SET next_offset=%s,
               checkpoint_at=clock_timestamp() WHERE consumer_group=%s AND topic=%s
               AND partition=%s AND epoch=%s AND owner_id=%s RETURNING next_offset""",
            (next_offset, *lease.coordinates, lease.epoch, lease.owner),
        ).fetchone()
        if updated is None:
            msg = "partition_fenced"
            raise CheckpointError(msg)

    def states(self, group: str) -> list[dict[str, Any]]:
        if not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", group):
            msg = "invalid_consumer_group"
            raise CheckpointError(msg)
        with checkpoint_connection() as connection:
            return connection.execute(
                """SELECT * FROM ai_intelligence_partitions WHERE consumer_group=%s
                   AND topic=%s ORDER BY partition LIMIT 33""",
                (group, TOPIC),
            ).fetchall()
