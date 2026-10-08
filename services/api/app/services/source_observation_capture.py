"""Source-owned daily observation capture binds a SQL census to the complete real broker prefix."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from jsonschema import Draft202012Validator

from app.services.source_observation_broker import TOPIC, BrokerConfig, BrokerTopology
from app.services.source_observation_outbox import ObservationError, ObservationOutbox, event_for
from app.services.source_observation_wire import ObservationVersion, Stream, canonical

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import date

MAX_FACTS = 10000
MAX_RECEIPTS = 20000
MAX_BYTES = 16 * 1024**2
CONTRACT = (
    Path(__file__).resolve().parents[1] / "contracts/source-observations-v1/capture.schema.json"
)


def check(condition: bool, category: str) -> None:  # noqa: FBT001 - fixed contract guards
    if not condition:
        raise ObservationError(category)


@dataclass(frozen=True, repr=False)
class PrefixRecord:
    partition: int
    offset: int
    raw: bytes
    key: bytes


def seal_capture(
    stream: Stream,
    boundaries: Sequence[int],
    facts: Sequence[dict[str, Any]],
    outbox: Sequence[dict[str, Any]],
    records: Sequence[PrefixRecord],
) -> bytes:
    """Require every real broker position rather than inferring a prefix from SQL delivery receipts."""
    check(1 <= len(boundaries) <= 32, "observation_capture_partition_vector_invalid")
    check(
        all(type(high) is int and high >= 0 for high in boundaries)
        and sum(boundaries) <= MAX_RECEIPTS
        and len(facts) <= MAX_FACTS
        and len(outbox) == len(facts)
        and len(records) == sum(boundaries),
        "observation_capture_census_or_budget_invalid",
    )
    expected: dict[str, tuple[bytes, ObservationVersion, int, int]] = {}
    rows: dict[tuple[str, int], ObservationVersion] = {}
    ids: set[str] = set()
    grains: dict[tuple[date, str, str, str], str] = {}
    for stored in facts:
        raw = bytes(stored["fact_bytes"])
        fact = ObservationVersion.model_validate_json(raw)
        check(
            canonical(fact) == raw
            and hashlib.sha256(raw).hexdigest() == stored["fact_sha256"]
            and str(stored["observation_id"]) == fact.observation_id
            and str(stored["row_id"]) == fact.id
            and stored["version"] == fact.version
            and fact.key not in rows
            and fact.id not in ids
            and grains.get(fact.grain, fact.observation_id) == fact.observation_id,
            "observation_capture_fact_integrity",
        )
        rows[fact.key] = fact
        ids.add(fact.id)
        grains[fact.grain] = fact.observation_id
    previous: dict[str, ObservationVersion] = {}
    for fact in sorted(rows.values(), key=lambda value: value.key):
        old = previous.get(fact.observation_id)
        check(
            fact.version == (1 if old is None else old.version + 1)
            and (
                old is None or (old.grain == fact.grain and old.available_at <= fact.available_at)
            ),
            "observation_capture_history_gap_or_changed_grain",
        )
        previous[fact.observation_id] = fact
    for stored in outbox:
        candidate = rows.get((str(stored["observation_id"]), stored["version"]))
        if candidate is None:
            msg = "observation_capture_outbox_without_fact"
            raise ObservationError(msg)
        fact = candidate
        event = event_for(stream, fact)
        raw = canonical(event)
        partition = UUID(fact.observation_id).int % len(boundaries)
        check(
            bytes(stored["event_bytes"]) == raw
            and stored["event_sha256"] == hashlib.sha256(raw).hexdigest()
            and str(stored["event_id"]) == event.event_id
            and stored["partition"] == partition
            and type(stored["delivered_offset"]) is int
            and stored["delivered_at"] is not None
            and 0 <= stored["delivered_offset"] < boundaries[partition]
            and event.event_id not in expected,
            "observation_capture_pending_or_invalid_outbox",
        )
        expected[event.event_id] = (raw, fact, partition, stored["delivered_offset"])
    by_raw = {value[0]: (identity, value) for identity, value in expected.items()}
    coordinates = {}
    receipts = []
    seen = set()
    for record in records:
        check(record.raw in by_raw, "observation_capture_unknown_broker_record")
        identity, (raw, fact, partition, _offset) = by_raw[record.raw]
        coordinate = (record.partition, record.offset)
        check(
            record.partition == partition
            and record.key == fact.observation_id.encode()
            and type(record.offset) is int
            and 0 <= record.offset < boundaries[partition]
            and coordinate not in coordinates,
            "observation_capture_broker_position_or_key_invalid",
        )
        coordinates[coordinate] = identity
        seen.add(identity)
        receipts.append(
            {
                "partition": partition,
                "offset": record.offset,
                "event_id": identity,
                "event_sha256": hashlib.sha256(raw).hexdigest(),
                "fact_sha256": hashlib.sha256(canonical(fact)).hexdigest(),
            }
        )
    check(
        seen == set(expected)
        and all(
            coordinates.get((partition, offset)) == identity
            for identity, (_raw, _fact, partition, offset) in expected.items()
        )
        and set(coordinates)
        == {
            (partition, offset)
            for partition, high in enumerate(boundaries)
            for offset in range(high)
        },
        "observation_capture_incomplete_prefix_or_delivery_binding",
    )
    body = {
        "version": "source-observation-capture-1.0",
        "table": "daily_demand_versions",
        "stream": stream.model_dump(mode="json"),
        "boundaries": [{"partition": p, "next_offset": high} for p, high in enumerate(boundaries)],
        "rows": [rows[key].model_dump(mode="json") for key in sorted(rows)],
        "receipts": sorted(receipts, key=lambda receipt: (receipt["partition"], receipt["offset"])),
    }
    unsigned = json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    body["capture_id"] = "observation-capture-sha256-" + hashlib.sha256(unsigned).hexdigest()
    Draft202012Validator(json.loads(CONTRACT.read_bytes())).validate(body)
    result = json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    check(len(result) <= MAX_BYTES, "observation_capture_byte_limit")
    return result


class CaptureReader:
    """Dedicated TLS/SCRAM READ principal; manual assignment, no writes/commits/ACKs."""

    def __init__(self, config: BrokerConfig) -> None:
        native = import_module("confluent_kafka")
        admin = import_module("confluent_kafka.admin")
        common = config.backend()
        self.native = native
        self.topology = BrokerTopology(admin.AdminClient(common), config.source_authority_id)
        self.client = native.Consumer(
            {
                **common,
                "group.id": "ai10-observation-capture-" + uuid4().hex,
                "enable.auto.commit": False,
                "enable.auto.offset.store": False,
                "isolation.level": "read_uncommitted",
            }
        )

    def boundaries(self, partitions: int) -> tuple[int, ...]:
        values = []
        for partition in range(partitions):
            low, high = self.client.get_watermark_offsets(
                self.native.TopicPartition(TOPIC, partition), timeout=5, cached=False
            )
            check(low == 0 and type(high) is int and high >= 0, "observation_capture_retention_gap")
            values.append(high)
        check(sum(values) <= MAX_RECEIPTS, "observation_capture_receipt_limit")
        return tuple(values)

    def prefix(self, boundaries: tuple[int, ...]) -> tuple[PrefixRecord, ...]:
        self.client.assign(
            [self.native.TopicPartition(TOPIC, p, 0) for p in range(len(boundaries))]
        )
        next_offsets = dict.fromkeys(range(len(boundaries)), 0)
        records: list[PrefixRecord] = []
        deadline = time.monotonic() + 20
        while len(records) < sum(boundaries):
            check(time.monotonic() < deadline, "observation_capture_broker_read_timeout")
            message = self.client.poll(0.2)
            if message is None:
                continue
            check(message.error() is None, "observation_capture_broker_read_failed")
            partition, offset = message.partition(), message.offset()
            check(
                message.topic() == TOPIC
                and partition in next_offsets
                and offset == next_offsets[partition]
                and offset < boundaries[partition],
                "observation_capture_prefix_gap_or_changed",
            )
            raw, key = message.value(), message.key()
            check(
                isinstance(raw, bytes) and len(raw) <= 16384 and isinstance(key, bytes),
                "observation_capture_broker_record_invalid",
            )
            records.append(PrefixRecord(partition, offset, raw, key))
            next_offsets[partition] += 1
        return tuple(records)

    def close(self) -> None:
        self.client.close()


def capture_source(
    outbox: ObservationOutbox, reader: CaptureReader, output: Path
) -> dict[str, Any]:
    """Hold the same authority lock as append/publish until the complete prefix is verified."""
    try:
        stream, partitions = reader.topology.inspect()
        with outbox.transaction() as conn:
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            outbox.locked(conn, stream, partitions)
            facts = conn.execute(
                "SELECT * FROM source_observation_versions WHERE authority_id=%s "
                "ORDER BY observation_id,version LIMIT %s",
                (stream.source_authority_id, MAX_FACTS + 1),
            ).fetchall()
            publications = conn.execute(
                "SELECT * FROM source_observation_outbox WHERE authority_id=%s "
                "ORDER BY sequence LIMIT %s",
                (stream.source_authority_id, MAX_FACTS + 1),
            ).fetchall()
            boundaries = reader.boundaries(partitions)
            records = reader.prefix(boundaries)
            raw = seal_capture(stream, boundaries, facts, publications, records)
            check(
                reader.topology.inspect() == (stream, partitions)
                and reader.boundaries(partitions) == boundaries,
                "observation_capture_stream_changed_during_barrier",
            )
        # create-only publication; the private output must never replace a prior capture.
        with tempfile.NamedTemporaryFile(
            prefix=".observation-capture-", dir=output.parent, delete=False
        ) as target:
            staging = Path(target.name)
            try:
                target.write(raw)
                target.flush()
                os.fsync(target.fileno())
                os.link(staging, output, follow_symlinks=False)
                descriptor = os.open(output.parent, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
            finally:
                staging.unlink()
        return {
            "status": "passed",
            "capture_id": json.loads(raw)["capture_id"],
            "scope": "daily_demand_versions_only",
            "full_43_table_snapshot": False,
            "rows": len(facts),
            "receipts": len(records),
            "boundaries": list(boundaries),
            "publisher_receipts_used_as_complete_prefix": False,
        }
    except FileExistsError:
        raise
    except Exception:  # noqa: BLE001 - source facts and broker/SQL credentials are private
        msg = "source_observation_capture_unavailable"
        raise ObservationError(msg) from None
