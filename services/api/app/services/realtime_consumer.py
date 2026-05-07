from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Protocol

from app.core.config import Settings, settings as default_settings


logger = logging.getLogger(__name__)

SUPPORTED_EVENT_TYPES = frozenset(
    {
        "order_created",
        "sale_completed",
        "return_completed",
        "stock_changed",
        "inventory_snapshot_recorded",
        "replenishment_completed",
        "price_changed",
        "promotion_started",
        "promotion_ended",
        "forecast_generated",
        "anomaly_detected",
        "alert_created",
        "workflow_action_performed",
    }
)

REQUIRED_EVENT_FIELDS = (
    "event_id",
    "event_type",
    "schema_version",
    "source",
    "correlation_id",
    "occurred_at",
    "ingested_at",
    "payload",
)


class EventHandler(Protocol):
    def __call__(self, event: dict[str, Any]) -> None: ...


@dataclass(frozen=True)
class RealtimeEventEnvelope:
    event_id: str
    event_type: str
    schema_version: str
    source: str
    correlation_id: str
    occurred_at: str
    ingested_at: str
    payload: dict[str, Any]

    @classmethod
    def from_dict(cls, event: dict[str, Any]) -> "RealtimeEventEnvelope":
        missing = [
            field_name
            for field_name in REQUIRED_EVENT_FIELDS
            if field_name not in event or event[field_name] in (None, "")
        ]

        if missing:
            raise ValueError(
                f"Missing required event fields: {', '.join(missing)}"
            )

        event_type = str(event["event_type"])
        if event_type not in SUPPORTED_EVENT_TYPES:
            raise ValueError(f"Unsupported event type: {event_type}")

        payload = event["payload"]
        if not isinstance(payload, dict):
            raise ValueError("payload must be a JSON object")

        return cls(
            event_id=str(event["event_id"]),
            event_type=event_type,
            schema_version=str(event["schema_version"]),
            source=str(event["source"]),
            correlation_id=str(event["correlation_id"]),
            occurred_at=str(event["occurred_at"]),
            ingested_at=str(event["ingested_at"]),
            payload=payload,
        )


@dataclass
class RealtimeConsumerState:
    running: bool = False
    received_events: int = 0
    processed_events: int = 0
    failed_events: int = 0
    dead_lettered_events: int = 0
    ignored_events: int = 0
    last_event_id: str | None = None
    last_event_type: str | None = None
    last_error: str | None = None
    last_processed_at: datetime | None = None
    started_at: datetime | None = None
    stopped_at: datetime | None = None

    def snapshot(self) -> dict[str, Any]:
        return {
            "running": self.running,
            "received_events": self.received_events,
            "processed_events": self.processed_events,
            "failed_events": self.failed_events,
            "dead_lettered_events": self.dead_lettered_events,
            "ignored_events": self.ignored_events,
            "last_event_id": self.last_event_id,
            "last_event_type": self.last_event_type,
            "last_error": self.last_error,
            "last_processed_at": (
                self.last_processed_at.isoformat()
                if self.last_processed_at
                else None
            ),
            "started_at": (
                self.started_at.isoformat() if self.started_at else None
            ),
            "stopped_at": (
                self.stopped_at.isoformat() if self.stopped_at else None
            ),
        }


def build_default_event_handlers() -> dict[str, EventHandler]:
    """Return placeholder handlers for the first consumer skeleton."""
    return {event_type: _noop_handler for event_type in SUPPORTED_EVENT_TYPES}


def _noop_handler(event: dict[str, Any]) -> None:
    logger.debug(
        "Skipping event type %s for consumer skeleton", event.get("event_type")
    )


class RealtimeEventConsumer:
    """Minimal consumer skeleton for Sprint 9.

    The class is intentionally broker-agnostic for now. It validates event
    envelopes, dispatches to registered handlers and records processing state.
    The broker adapter will be added in a later commit.
    """

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        handlers: dict[str, EventHandler] | None = None,
    ) -> None:
        self.settings = settings or default_settings
        self.handlers = handlers or build_default_event_handlers()
        self.state = RealtimeConsumerState()

    def start(self) -> None:
        self.state.running = True
        self.state.started_at = datetime.now(timezone.utc)

    def stop(self) -> None:
        self.state.running = False
        self.state.stopped_at = datetime.now(timezone.utc)

    def register_handler(self, event_type: str, handler: EventHandler) -> None:
        self.handlers[event_type] = handler

    def supported_event_types(self) -> tuple[str, ...]:
        return tuple(sorted(self.handlers))

    def process_event(self, event: dict[str, Any]) -> dict[str, Any]:
        self.state.received_events += 1

        try:
            envelope = RealtimeEventEnvelope.from_dict(event)
            handler = self.handlers.get(envelope.event_type)

            if handler is None:
                raise ValueError(f"No handler registered for {envelope.event_type}")

            handler(event)
            self.state.processed_events += 1
            self.state.last_event_id = envelope.event_id
            self.state.last_event_type = envelope.event_type
            self.state.last_processed_at = datetime.now(timezone.utc)
            self.state.last_error = None

            return {
                "status": "processed",
                "event_id": envelope.event_id,
                "event_type": envelope.event_type,
            }

        except Exception as exc:
            self.state.failed_events += 1
            self.state.dead_lettered_events += 1
            self.state.last_error = str(exc)

            logger.exception("Realtime event processing failed")

            return {
                "status": "failed_dead_lettered",
                "error": str(exc),
            }

    def process_events(self, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [self.process_event(event) for event in events]

    def snapshot(self) -> dict[str, Any]:
        snapshot = self.state.snapshot()
        snapshot["bootstrap_servers"] = self.settings.broker_bootstrap_servers
        snapshot["group_id"] = self.settings.broker_group_id
        snapshot["client_id"] = self.settings.broker_client_id
        snapshot["supported_event_types"] = list(self.supported_event_types())
        return snapshot


def build_realtime_event_consumer(
    settings: Settings | None = None,
    handlers: dict[str, EventHandler] | None = None,
) -> RealtimeEventConsumer:
    return RealtimeEventConsumer(settings=settings, handlers=handlers)
