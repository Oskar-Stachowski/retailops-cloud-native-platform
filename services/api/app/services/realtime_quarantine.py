from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from collections.abc import Callable

from app.repositories.realtime_quarantine_repository import RealtimeQuarantineRepository
from app.services.intelligence_contract import TOPIC, content_hash
from app.services.intelligence_contract import validate_event as validate_intelligence_event
from app.services.intelligence_model_contract import MODEL_TYPES, model_partition_key
from app.services.realtime_contract import validate_event


class ReplayMessage(Protocol):
    def partition(self) -> int: ...

    def offset(self) -> int: ...


class ReplayProducer(Protocol):
    def produce(
        self,
        topic: str,
        *,
        key: bytes,
        value: bytes,
        on_delivery: Callable[[object, ReplayMessage], None],
    ) -> None: ...

    def flush(self, timeout: float) -> int: ...


def replay_quarantined_message(
    quarantine_id: str,
    *,
    event: dict[str, Any],
    operator: str,
    bootstrap_servers: str,
    repository: RealtimeQuarantineRepository | None = None,
    producer: ReplayProducer | None = None,
) -> dict[str, Any]:
    """Pin a reviewed correction before publishing; keep raw bytes and lineage."""
    if not operator.strip() or not bootstrap_servers:
        msg = "Replay requires a named operator and configured broker."
        raise ValueError(msg)
    repository = repository or RealtimeQuarantineRepository()
    original = repository.get(quarantine_id)
    if original["topic"] == TOPIC:
        validate_intelligence_event(event, transport_topic=original["topic"])
        payload = event["payload"]
        partition_key = (
            model_partition_key(event)
            if event["event_type"] in MODEL_TYPES
            else content_hash(
                {
                    name: payload[name]
                    for name in (
                        "product_id",
                        "selling_location_id",
                        "channel",
                    )
                }
            )
        )
    else:
        validate_event(event, transport_topic=original["topic"])
        partition_key = event["event_id"]
    intent = repository.prepare_replay(quarantine_id, event, operator)
    if intent["payload"]["replay"].get("delivered_at"):
        return {"status": "already_replayed", "quarantine_id": quarantine_id}

    if producer is None:
        from confluent_kafka import Producer  # noqa: PLC0415

        producer = Producer(
            {
                "bootstrap.servers": bootstrap_servers,
                "enable.idempotence": True,
                "acks": "all",
                "delivery.timeout.ms": 10000,
            }
        )

    receipts: list[tuple[object, ReplayMessage]] = []

    def on_delivery(error: object, message: ReplayMessage) -> None:
        receipts.append((error, message))

    producer.produce(
        original["topic"],
        key=partition_key.encode("utf-8"),
        value=json.dumps(event, sort_keys=True, allow_nan=False).encode("utf-8"),
        on_delivery=on_delivery,
    )
    remaining = producer.flush(15)
    if remaining or len(receipts) != 1 or receipts[0][0] is not None:
        msg = "Replay has no successful broker delivery receipt; intent remains pending."
        raise RuntimeError(msg)
    delivered = receipts[0][1]
    repository.confirm_replay(
        quarantine_id, partition=delivered.partition(), offset=delivered.offset()
    )
    return {
        "status": "replayed",
        "quarantine_id": quarantine_id,
        "event_id": event["event_id"],
        "partition": delivered.partition(),
        "offset": delivered.offset(),
    }
