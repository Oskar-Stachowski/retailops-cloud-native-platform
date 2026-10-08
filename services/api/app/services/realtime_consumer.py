from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Protocol

from app.core.config import Settings
from app.core.config import settings as default_settings
from app.repositories.realtime_metrics_repository import RealtimeMetricsRepository
from app.repositories.realtime_quarantine_repository import QUARANTINE_SOURCE
from app.services.realtime_contract import (
    SUPPORTED_EVENT_TYPES,
    validate_event,
)

logger = logging.getLogger(__name__)


class InvalidRealtimeEventError(ValueError):
    """An envelope rejected before any handler or projection runs."""


class EventHandler(Protocol):
    def __call__(self, event: dict[str, Any]) -> None: ...


@dataclass(frozen=True)
class RealtimeEventEnvelope:
    event_id: str
    event_type: str
    topic: str
    schema_version: str
    source: str
    correlation_id: str
    occurred_at: str
    ingested_at: str
    payload: dict[str, Any]

    @classmethod
    def from_dict(
        cls, event: dict[str, Any], *, transport_topic: str | None = None
    ) -> RealtimeEventEnvelope:
        validate_event(event, transport_topic=transport_topic)

        return cls(
            event_id=str(event["event_id"]),
            event_type=event["event_type"],
            topic=event["topic"],
            schema_version=str(event["schema_version"]),
            source=str(event["source"]),
            correlation_id=str(event["correlation_id"]),
            occurred_at=str(event["occurred_at"]),
            ingested_at=str(event["ingested_at"]),
            payload=event["payload"],
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
                self.last_processed_at.isoformat() if self.last_processed_at else None
            ),
            "started_at": (self.started_at.isoformat() if self.started_at else None),
            "stopped_at": (self.stopped_at.isoformat() if self.stopped_at else None),
        }


def build_default_event_handlers() -> dict[str, EventHandler]:
    """Return placeholder handlers for the first consumer skeleton."""
    return dict.fromkeys(SUPPORTED_EVENT_TYPES, _noop_handler)


def _noop_handler(event: dict[str, Any]) -> None:
    logger.debug("Skipping event type %s for consumer skeleton", event.get("event_type"))


class RealtimeEventConsumer:
    """Validate and atomically project events; the runner owns transport ACK."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        handlers: dict[str, EventHandler] | None = None,
        repository: RealtimeMetricsRepository | None = None,
        consumer_name: str = "retailops-realtime-consumer",
    ) -> None:
        self.settings = settings or default_settings
        self.handlers = handlers or build_default_event_handlers()
        self.repository = repository or RealtimeMetricsRepository()
        self.consumer_name = consumer_name
        self.state = RealtimeConsumerState()

    def start(self) -> None:
        self.state.running = True
        self.state.started_at = datetime.now(UTC)
        self.state.stopped_at = None
        self._persist_state()

    def stop(self) -> None:
        self.state.running = False
        self.state.stopped_at = datetime.now(UTC)
        self._persist_state()

    def register_handler(self, event_type: str, handler: EventHandler) -> None:
        self.handlers[event_type] = handler

    def supported_event_types(self) -> tuple[str, ...]:
        return tuple(sorted(self.handlers))

    def process_event(
        self, event: dict[str, Any], *, transport_topic: str | None = None
    ) -> dict[str, Any]:
        self.state.received_events += 1
        try:
            envelope = RealtimeEventEnvelope.from_dict(event, transport_topic=transport_topic)
        except (TypeError, ValueError) as exc:
            self._note_failure(exc)
            raise InvalidRealtimeEventError(str(exc)) from exc

        try:
            with self.repository.event_transaction(envelope.event_id) as repository:
                record = repository.get_event_record(envelope.event_id)
                if record and record.get("source") == QUARANTINE_SOURCE:
                    msg = "Event ID is reserved by an immutable quarantine record."
                    raise InvalidRealtimeEventError(msg)
                if record and record.get("status") == "processed":
                    duplicate = True
                else:
                    duplicate = False
                    handler = self.handlers.get(envelope.event_type)
                    if handler is None:
                        msg = f"No handler registered for {envelope.event_type}"
                        raise RuntimeError(msg)
                    repository.record_event_log(**self._event_record(envelope), status="received")
                    handler(event)
                    repository.replace_metric_observations(
                        event_id=envelope.event_id,
                        observations=self._build_metric_observations(envelope),
                    )
                    processed_at = datetime.now(UTC)
                    repository.record_event_log(
                        **self._event_record(envelope),
                        status="processed",
                        processed_at=processed_at,
                    )
        except Exception as exc:
            self._note_failure(exc)
            raise

        self.state.last_event_id = envelope.event_id
        self.state.last_event_type = envelope.event_type
        self.state.last_error = None
        if duplicate:
            self.state.ignored_events += 1
        else:
            self.state.processed_events += 1
            self.state.last_processed_at = processed_at
        # An error here also stops the runner without ACK. The durable marker
        # makes the subsequent delivery a duplicate with no repeated projection.
        self._persist_state()
        return {
            "status": "ignored_duplicate" if duplicate else "processed",
            "event_id": envelope.event_id,
            "event_type": envelope.event_type,
        }

    def record_quarantined(self, *, decoded: bool, error: str) -> None:
        """Count only messages whose raw transport record was committed to DB."""
        if not decoded:
            self.state.received_events += 1
            self.state.failed_events += 1
        self.state.last_error = error
        self.state.dead_lettered_events += 1
        self._persist_state()

    def _note_failure(self, error: Exception) -> None:
        self.state.failed_events += 1
        self.state.last_error = str(error)
        try:
            self._persist_state()
        except Exception:
            logger.exception("Could not persist consumer failure state")

    def _event_record(self, envelope: RealtimeEventEnvelope) -> dict[str, Any]:
        return {
            "event_id": envelope.event_id,
            "event_type": envelope.event_type,
            "topic": envelope.topic,
            "schema_version": envelope.schema_version,
            "source": envelope.source,
            "correlation_id": envelope.correlation_id,
            "occurred_at": self._parse_datetime(envelope.occurred_at),
            "ingested_at": self._parse_datetime(envelope.ingested_at),
            "payload": envelope.payload,
        }

    def process_events(self, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [self.process_event(event) for event in events]

    def snapshot(self) -> dict[str, Any]:
        snapshot = self.state.snapshot()
        snapshot["bootstrap_servers"] = self.settings.broker_bootstrap_servers
        snapshot["group_id"] = self.settings.broker_group_id
        snapshot["client_id"] = self.settings.broker_client_id
        snapshot["consumer_name"] = self.consumer_name
        snapshot["supported_event_types"] = list(self.supported_event_types())
        return snapshot

    def _persist_state(self) -> None:
        self.repository.upsert_consumer_state(
            consumer_name=self.consumer_name,
            running=self.state.running,
            received_events=self.state.received_events,
            processed_events=self.state.processed_events,
            failed_events=self.state.failed_events,
            dead_lettered_events=self.state.dead_lettered_events,
            ignored_events=self.state.ignored_events,
            last_event_id=self.state.last_event_id,
            last_event_type=self.state.last_event_type,
            last_error=self.state.last_error,
            last_processed_at=self.state.last_processed_at,
            started_at=self.state.started_at,
            stopped_at=self.state.stopped_at,
        )

    def _build_metric_observations(
        self,
        envelope: RealtimeEventEnvelope,
    ) -> list[dict[str, Any]]:
        payload = envelope.payload
        observed_at = self._parse_datetime(envelope.ingested_at)
        dimension_key = self._dimension_key(
            payload,
            ("product_id", "store_id", "channel"),
        )
        event_type = envelope.event_type

        if event_type == "sale_completed":
            quantity = self._decimal(payload.get("quantity", 0))
            unit_price = self._decimal(payload.get("unit_price", 0))
            total_amount = self._decimal(payload.get("total_amount", quantity * unit_price))
            return self._metrics(
                event_type,
                observed_at,
                dimension_key,
                [
                    ("live_revenue", total_amount),
                    ("live_units_sold", quantity),
                    ("live_sale_events", 1),
                ],
            )

        if event_type == "return_completed":
            quantity = self._decimal(payload.get("quantity", 0))
            refund_amount = self._decimal(payload.get("refund_amount", 0))
            return self._metrics(
                event_type,
                observed_at,
                dimension_key,
                [
                    ("live_return_amount", refund_amount),
                    ("live_return_units", quantity),
                    ("live_return_events", 1),
                ],
            )

        if event_type == "stock_changed":
            quantity_delta = self._decimal(payload.get("quantity_delta", 0))
            return self._metrics(
                event_type,
                observed_at,
                self._dimension_key(payload, ("product_id", "warehouse_id")),
                [
                    ("live_stock_delta", quantity_delta),
                    ("live_stock_events", 1),
                ],
            )

        if event_type == "inventory_snapshot_recorded":
            stock_quantity = self._decimal(payload.get("stock_quantity", 0))
            return self._metrics(
                event_type,
                observed_at,
                self._dimension_key(payload, ("product_id", "warehouse_id")),
                [
                    ("live_stock_on_hand", stock_quantity),
                    ("live_inventory_snapshots", 1),
                ],
            )

        if event_type == "replenishment_completed":
            quantity = self._decimal(payload.get("quantity", 0))
            return self._metrics(
                event_type,
                observed_at,
                self._dimension_key(payload, ("product_id", "warehouse_id")),
                [
                    ("live_replenishment_units", quantity),
                    ("live_replenishment_events", 1),
                ],
            )

        if event_type == "price_changed":
            new_price = self._decimal(payload.get("new_price", 0))
            return self._metrics(
                event_type,
                observed_at,
                self._dimension_key(payload, ("product_id",)),
                [
                    ("live_new_price", new_price),
                    ("live_price_changes", 1),
                ],
            )

        if event_type in {"promotion_started", "promotion_ended"}:
            return self._metrics(
                event_type,
                observed_at,
                self._dimension_key(payload, ("product_id",)),
                [
                    ("live_promotion_events", 1),
                ],
            )

        if event_type == "forecast_generated":
            predicted_demand = self._decimal(payload.get("predicted_demand", 0))
            return self._metrics(
                event_type,
                observed_at,
                self._dimension_key(payload, ("product_id", "store_id")),
                [
                    ("live_forecast_units", predicted_demand),
                    ("live_forecasts_generated", 1),
                ],
            )

        if event_type == "anomaly_detected":
            return self._metrics(
                event_type,
                observed_at,
                self._dimension_key(payload, ("product_id", "store_id")),
                [
                    ("live_anomalies_detected", 1),
                ],
            )

        if event_type == "alert_created":
            return self._metrics(
                event_type,
                observed_at,
                self._dimension_key(payload, ("product_id",)),
                [
                    ("live_alerts_created", 1),
                ],
            )

        if event_type == "workflow_action_performed":
            return self._metrics(
                event_type,
                observed_at,
                self._dimension_key(payload, ("alert_id",)),
                [
                    ("live_workflow_actions", 1),
                ],
            )

        if event_type == "order_created":
            order_total = self._decimal(payload.get("order_total", 0))
            return self._metrics(
                event_type,
                observed_at,
                self._dimension_key(payload, ("store_id", "channel")),
                [
                    ("live_order_value", order_total),
                    ("live_orders_created", 1),
                ],
            )

        return []

    def _metrics(
        self,
        event_type: str,
        observed_at: datetime,
        dimension_key: str | None,
        values: list[tuple[str, Any]],
    ) -> list[dict[str, Any]]:
        return [
            {
                "metric_name": metric_name,
                "metric_value": metric_value,
                "dimension_key": dimension_key,
                "source_event_type": event_type,
                "observed_at": observed_at,
            }
            for metric_name, metric_value in values
        ]

    def _dimension_key(
        self,
        payload: dict[str, Any],
        fields: tuple[str, ...],
    ) -> str | None:
        parts: list[str] = []
        for field_name in fields:
            value = payload.get(field_name)
            if value in (None, ""):
                continue
            parts.append(f"{field_name}={value}")

        return "|".join(parts) if parts else None

    def _parse_datetime(self, value: object) -> datetime:
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=UTC)

        if value in (None, ""):
            return datetime.now(UTC)

        normalized = str(value).replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)

    def _decimal(self, value: object) -> Decimal:
        if isinstance(value, Decimal):
            return value

        if value in (None, ""):
            return Decimal(0)

        return Decimal(str(value))


def build_realtime_event_consumer(
    settings: Settings | None = None,
    handlers: dict[str, EventHandler] | None = None,
    repository: RealtimeMetricsRepository | None = None,
    consumer_name: str = "retailops-realtime-consumer",
) -> RealtimeEventConsumer:
    return RealtimeEventConsumer(
        settings=settings,
        handlers=handlers,
        repository=repository,
        consumer_name=consumer_name,
    )
