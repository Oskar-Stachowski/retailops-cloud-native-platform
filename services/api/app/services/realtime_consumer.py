from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable, Protocol

from app.core.config import Settings, settings as default_settings
from app.repositories.realtime_metrics_repository import RealtimeMetricsRepository


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

EVENT_TOPICS = {
    "order_created": "retailops.sales.v1",
    "sale_completed": "retailops.sales.v1",
    "return_completed": "retailops.sales.v1",
    "stock_changed": "retailops.inventory.v1",
    "inventory_snapshot_recorded": "retailops.inventory.v1",
    "replenishment_completed": "retailops.inventory.v1",
    "price_changed": "retailops.pricing.v1",
    "promotion_started": "retailops.pricing.v1",
    "promotion_ended": "retailops.pricing.v1",
    "forecast_generated": "retailops.intelligence.v1",
    "anomaly_detected": "retailops.intelligence.v1",
    "alert_created": "retailops.operations.v1",
    "workflow_action_performed": "retailops.operations.v1",
}


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
        raw_event_id = self._safe_event_id(event)

        try:
            envelope = RealtimeEventEnvelope.from_dict(event)

            if self.repository.is_event_processed(envelope.event_id):
                self.state.ignored_events += 1
                self.state.last_event_id = envelope.event_id
                self.state.last_event_type = envelope.event_type
                self.state.last_error = None
                self._persist_state()

                return {
                    "status": "ignored_duplicate",
                    "event_id": envelope.event_id,
                    "event_type": envelope.event_type,
                }

            self.repository.record_event_log(
                event_id=envelope.event_id,
                event_type=envelope.event_type,
                topic=self._resolve_topic(envelope.event_type),
                schema_version=envelope.schema_version,
                source=envelope.source,
                correlation_id=envelope.correlation_id,
                occurred_at=self._parse_datetime(envelope.occurred_at),
                ingested_at=self._parse_datetime(envelope.ingested_at),
                payload=envelope.payload,
                status="received",
            )

            handler = self.handlers.get(envelope.event_type)

            if handler is None:
                raise ValueError(f"No handler registered for {envelope.event_type}")

            handler(event)
            observations = self._build_metric_observations(envelope)
            self.repository.replace_metric_observations(
                event_id=envelope.event_id,
                observations=observations,
            )
            processed_at = datetime.now(timezone.utc)
            self.repository.record_event_log(
                event_id=envelope.event_id,
                event_type=envelope.event_type,
                topic=self._resolve_topic(envelope.event_type),
                schema_version=envelope.schema_version,
                source=envelope.source,
                correlation_id=envelope.correlation_id,
                occurred_at=self._parse_datetime(envelope.occurred_at),
                ingested_at=self._parse_datetime(envelope.ingested_at),
                payload=envelope.payload,
                status="processed",
                processed_at=processed_at,
            )
            self.state.processed_events += 1
            self.state.last_event_id = envelope.event_id
            self.state.last_event_type = envelope.event_type
            self.state.last_processed_at = processed_at
            self.state.last_error = None
            self._persist_state()

            return {
                "status": "processed",
                "event_id": envelope.event_id,
                "event_type": envelope.event_type,
            }

        except Exception as exc:
            self.state.failed_events += 1
            self.state.dead_lettered_events += 1
            self.state.last_error = str(exc)
            if raw_event_id is not None:
                try:
                    raw_event_type = (
                        str(event.get("event_type"))
                        if isinstance(event, dict) and event.get("event_type")
                        else "unknown"
                    )
                    raw_schema_version = (
                        str(event.get("schema_version"))
                        if isinstance(event, dict) and event.get("schema_version")
                        else "unknown"
                    )
                    raw_source = (
                        str(event.get("source"))
                        if isinstance(event, dict) and event.get("source")
                        else "unknown"
                    )
                    raw_correlation_id = (
                        str(event.get("correlation_id"))
                        if isinstance(event, dict) and event.get("correlation_id")
                        else raw_event_id
                    )
                    topic = self._resolve_topic(raw_event_type)
                    occurred_at = self._parse_datetime(
                        event.get("occurred_at") if isinstance(event, dict) else None
                    )
                    ingested_at = self._parse_datetime(
                        event.get("ingested_at") if isinstance(event, dict) else None
                    )
                    payload = (
                        event.get("payload")
                        if isinstance(event, dict) and isinstance(event.get("payload"), dict)
                        else {}
                    )
                    self.repository.record_event_log(
                        event_id=raw_event_id,
                        event_type=raw_event_type,
                        topic=topic,
                        schema_version=raw_schema_version,
                        source=raw_source,
                        correlation_id=raw_correlation_id,
                        occurred_at=occurred_at,
                        ingested_at=ingested_at,
                        payload=payload,
                        status="failed_dead_lettered",
                        error_message=str(exc),
                    )
                except Exception:
                    logger.exception("Failed to persist dead-lettered event")

            logger.exception("Realtime event processing failed")
            self._persist_state()

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
            total_amount = self._decimal(
                payload.get("total_amount", quantity * unit_price)
            )
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

    def _parse_datetime(self, value: Any) -> datetime:
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

        if value in (None, ""):
            return datetime.now(timezone.utc)

        normalized = str(value).replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)

    def _decimal(self, value: Any) -> Decimal:
        if isinstance(value, Decimal):
            return value

        if value in (None, ""):
            return Decimal("0")

        return Decimal(str(value))

    def _resolve_topic(self, event_type: str) -> str:
        if event_type not in EVENT_TOPICS:
            return "retailops.unknown.v1"

        return EVENT_TOPICS[event_type]

    def _safe_event_id(self, event: dict[str, Any]) -> str | None:
        if not isinstance(event, dict):
            return None

        event_id = event.get("event_id")
        if event_id in (None, ""):
            return None

        return str(event_id)


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
