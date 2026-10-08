"""One SQL transaction owns observation versions/outbox; publication is at least once."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import threading
import time
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Protocol
from uuid import UUID, uuid5

import psycopg
from psycopg.rows import dict_row

from app.services.source_observation_wire import Envelope, ObservationVersion, Stream, canonical

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from pathlib import Path

    from psycopg import Connection


class ObservationError(ValueError):
    """Fixed category only; source facts and credentials are private."""


def private_bytes(path: Path, *, limit: int) -> bytes:
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError
            result[key] = value
        return result

    def nonfinite(_value: str) -> None:
        raise ValueError

    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            info = os.fstat(fd)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) != 0o600
                or info.st_size > limit
            ):
                raise ValueError
            raw = os.read(fd, limit + 1)
            if len(raw) > limit:
                raise ValueError
            json.loads(raw, object_pairs_hook=unique, parse_constant=nonfinite)
            return raw
        finally:
            os.close(fd)
    except (OSError, ValueError, RecursionError):
        msg = "observation_private_input_invalid"
        raise ObservationError(msg) from None


def event_for(stream: Stream, fact: ObservationVersion) -> Envelope:
    identity = (
        "daily_demand_versions:" + fact.id + ":" + hashlib.sha256(canonical(fact)).hexdigest()
    )
    return Envelope(
        source_authority_id=stream.source_authority_id,
        event_id=str(uuid5(UUID(stream.source_authority_id), identity)),
        fact=fact,
    )


class ObservationOutbox:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    @contextmanager
    def transaction(self) -> Iterator[Connection[dict[str, Any]]]:
        try:
            with psycopg.connect(
                self._database_url,
                row_factory=dict_row,
                connect_timeout=3,
                application_name="source-observation-outbox",
            ) as conn:
                conn.execute("SET LOCAL lock_timeout='2s'")
                conn.execute("SET LOCAL statement_timeout='3s'")
                yield conn
        except ObservationError:
            raise
        except Exception:  # noqa: BLE001 - private database/broker boundary emits a fixed category
            msg = "observation_database_unavailable"
            raise ObservationError(msg) from None

    @staticmethod
    def locked(conn: Connection[dict[str, Any]], stream: Stream, partitions: int) -> None:
        if type(partitions) is not int or not 1 <= partitions <= 32:
            msg = "observation_partition_count_invalid"
            raise ObservationError(msg)
        row = conn.execute(
            "SELECT cluster_id,topic_id,partitions FROM source_observation_streams "
            "WHERE authority_id=%s FOR UPDATE",
            (stream.source_authority_id,),
        ).fetchone()
        if row is None or (row["cluster_id"], row["topic_id"], row["partitions"]) != (
            stream.cluster_id,
            stream.topic_id,
            partitions,
        ):
            msg = "observation_stream_identity_changed"
            raise ObservationError(msg)

    def bind(self, stream: Stream, partitions: int) -> None:
        if type(partitions) is not int or not 1 <= partitions <= 32:
            msg = "observation_partition_count_invalid"
            raise ObservationError(msg)
        with self.transaction() as conn:
            conn.execute(
                "INSERT INTO source_observation_streams(authority_id,cluster_id,topic_id,partitions) "
                "VALUES (%s,%s,%s,%s) ON CONFLICT(authority_id) DO NOTHING",
                (stream.source_authority_id, stream.cluster_id, stream.topic_id, partitions),
            )
            self.locked(conn, stream, partitions)

    def append(self, stream: Stream, partitions: int, fact: ObservationVersion) -> str:
        with self.transaction() as conn:
            return self.append_on_connection(conn, stream, partitions, fact)

    def append_on_connection(
        self,
        conn: Connection[dict[str, Any]],
        stream: Stream,
        partitions: int,
        fact: ObservationVersion,
    ) -> str:
        """Join the caller's transaction; never commit a partial business fact."""
        if conn.autocommit and conn.info.transaction_status != psycopg.pq.TransactionStatus.INTRANS:
            msg = "observation_caller_transaction_required"
            raise ObservationError(msg)
        conn.execute("SET LOCAL lock_timeout='2s'")
        conn.execute("SET LOCAL statement_timeout='3s'")
        self.locked(conn, stream, partitions)
        fact = ObservationVersion.model_validate_json(canonical(fact))
        raw = canonical(fact)
        fact_hash = hashlib.sha256(raw).hexdigest()
        old = conn.execute(
            "SELECT fact_bytes,fact_sha256 FROM source_observation_versions "
            "WHERE authority_id=%s AND observation_id=%s AND version=%s",
            (stream.source_authority_id, fact.observation_id, fact.version),
        ).fetchone()
        if old is not None:
            if bytes(old["fact_bytes"]) != raw or old["fact_sha256"] != fact_hash:
                msg = "observation_version_collision"
                raise ObservationError(msg)
            return "duplicate"
        current = conn.execute(
            "SELECT * FROM source_observation_keys WHERE authority_id=%s AND observation_id=%s",
            (stream.source_authority_id, fact.observation_id),
        ).fetchone()
        grain = (
            fact.business_date,
            UUID(fact.product_id),
            UUID(fact.selling_location_id),
            fact.channel,
        )
        if current is None:
            if fact.version != 1:
                msg = "observation_version_gap"
                raise ObservationError(msg)
            conn.execute(
                "INSERT INTO source_observation_keys(authority_id,observation_id,business_date,product_id,"
                "selling_location_id,channel,latest_version,latest_available_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    stream.source_authority_id,
                    fact.observation_id,
                    *grain,
                    fact.version,
                    fact.available_at,
                ),
            )
        else:
            if grain != (
                current["business_date"],
                current["product_id"],
                current["selling_location_id"],
                current["channel"],
            ):
                msg = "observation_grain_changed"
                raise ObservationError(msg)
            if (
                fact.version != current["latest_version"] + 1
                or fact.available_at < current["latest_available_at"]
            ):
                msg = "observation_version_or_availability_gap"
                raise ObservationError(msg)
            conn.execute(
                "UPDATE source_observation_keys SET latest_version=%s,latest_available_at=%s "
                "WHERE authority_id=%s AND observation_id=%s",
                (fact.version, fact.available_at, stream.source_authority_id, fact.observation_id),
            )
        conn.execute(
            "INSERT INTO source_observation_versions(authority_id,observation_id,version,row_id,fact_bytes,fact_sha256) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            (
                stream.source_authority_id,
                fact.observation_id,
                fact.version,
                fact.id,
                raw,
                fact_hash,
            ),
        )
        envelope = event_for(stream, fact)
        event_bytes = canonical(envelope)
        partition = UUID(fact.observation_id).int % partitions
        conn.execute(
            "INSERT INTO source_observation_outbox(authority_id,observation_id,version,event_id,partition,event_bytes,event_sha256) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (
                stream.source_authority_id,
                fact.observation_id,
                fact.version,
                envelope.event_id,
                partition,
                event_bytes,
                hashlib.sha256(event_bytes).hexdigest(),
            ),
        )
        return "inserted"


class Producer(Protocol):
    def produce(self, topic: str, **kwargs: Any) -> None: ...  # noqa: ANN401 - native delivery callback parameters
    def flush(self, timeout: float) -> int: ...


class Topology(Protocol):
    def inspect(self) -> tuple[Stream, int]: ...


class ObservationPublisher:
    """Serialize one authority under its SQL row lock, including bounded delivery.

    Broker acceptance and SQL completion are separate commits. A crash between
    them resends the identical event; the AI receiver deduplicates its fact.
    Delivery receipts are not a complete snapshot/replay watermark.
    """

    def __init__(
        self,
        outbox: ObservationOutbox,
        producer: Producer,
        topology: Topology,
        *,
        after_delivery: Callable[[], None] | None = None,
    ) -> None:
        self.outbox, self.producer, self.topology = outbox, producer, topology
        self.after_delivery = after_delivery
        self.failed = False

    def once(self) -> bool:
        if self.failed:
            msg = "observation_publisher_stopped"
            raise ObservationError(msg)
        try:
            stream, partitions = self.topology.inspect()
            with self.outbox.transaction() as conn:
                self.outbox.locked(conn, stream, partitions)
                row = conn.execute(
                    "SELECT * FROM source_observation_outbox WHERE authority_id=%s "
                    "AND delivered_offset IS NULL ORDER BY sequence LIMIT 1 FOR UPDATE",
                    (stream.source_authority_id,),
                ).fetchone()
                if row is None:
                    return False
                raw = bytes(row["event_bytes"])
                envelope = Envelope.model_validate_json(raw)
                expected = event_for(stream, envelope.fact)
                if (
                    envelope != expected
                    or canonical(envelope) != raw
                    or row["event_sha256"] != hashlib.sha256(raw).hexdigest()
                    or str(row["event_id"]) != envelope.event_id
                    or str(row["observation_id"]) != envelope.fact.observation_id
                    or row["version"] != envelope.fact.version
                    or row["partition"] != UUID(envelope.fact.observation_id).int % partitions
                ):
                    msg = "observation_outbox_integrity_failed"
                    raise ObservationError(msg)
                fact = conn.execute(
                    "SELECT fact_bytes,fact_sha256 FROM source_observation_versions "
                    "WHERE authority_id=%s AND observation_id=%s AND version=%s",
                    (stream.source_authority_id, row["observation_id"], row["version"]),
                ).fetchone()
                if (
                    fact is None
                    or bytes(fact["fact_bytes"]) != canonical(envelope.fact)
                    or fact["fact_sha256"] != hashlib.sha256(canonical(envelope.fact)).hexdigest()
                ):
                    msg = "observation_fact_integrity_failed"
                    raise ObservationError(msg)
                if self.topology.inspect() != (stream, partitions):
                    msg = "observation_stream_identity_changed"
                    raise ObservationError(msg)
                receipts = []
                self.producer.produce(
                    stream.topic,
                    value=raw,
                    key=envelope.fact.observation_id.encode(),
                    partition=row["partition"],
                    timestamp=int(envelope.fact.available_at.timestamp() * 1000),
                    headers=[("source-observation-version", b"1.0")],
                    on_delivery=lambda error, message: receipts.append((error, message)),
                )
                pending = self.producer.flush(12)
                if pending != 0 or len(receipts) != 1 or receipts[0][0] is not None:
                    msg = "observation_delivery_unconfirmed"
                    raise ObservationError(msg)
                message = receipts[0][1]
                if (
                    message.topic() != stream.topic
                    or message.partition() != row["partition"]
                    or type(message.offset()) is not int
                    or not 0 <= message.offset() < 2**63 - 1
                ):
                    msg = "observation_delivery_receipt_invalid"
                    raise ObservationError(msg)
                if self.after_delivery:
                    self.after_delivery()
                if self.topology.inspect() != (stream, partitions):
                    msg = "observation_stream_identity_changed"
                    raise ObservationError(msg)
                conn.execute(
                    "UPDATE source_observation_outbox SET delivered_offset=%s,delivered_at=now() WHERE sequence=%s",
                    (message.offset(), row["sequence"]),
                )
            return True
        except Exception:  # noqa: BLE001 - private database/broker boundary emits a fixed category
            self.failed = True
            msg = "observation_publication_unavailable"
            raise ObservationError(msg) from None

    def run(
        self,
        *,
        max_messages: int = 100,
        max_seconds: int = 60,
        stop_event: threading.Event | None = None,
    ) -> int:
        if (
            type(max_messages) is not int
            or not 1 <= max_messages <= 20000
            or type(max_seconds) is not int
            or not 1 <= max_seconds <= 3600
        ):
            msg = "observation_publisher_bounds_invalid"
            raise ObservationError(msg)
        stop = stop_event or threading.Event()
        deadline = time.monotonic() + max_seconds
        count = 0
        while count < max_messages and not stop.is_set() and time.monotonic() < deadline:
            if not self.once():
                break
            count += 1
        return count
