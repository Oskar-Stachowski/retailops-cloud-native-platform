from contextlib import contextmanager
from unittest.mock import Mock

import pytest

from app.core.config import Settings
from app.repositories.realtime_metrics_repository import RealtimeMetricsRepository
from app.services.realtime_consumer import (
    InvalidRealtimeEventError,
    RealtimeEventConsumer,
    RealtimeEventEnvelope,
    build_realtime_event_consumer,
)


def sample_event(event_type: str = "sale_completed") -> dict[str, object]:
    return {
        "event_id": "10c72395-4d9c-4f07-a940-c220c7f3aaf3",
        "event_type": event_type,
        "topic": "retailops.sales.v1",
        "schema_version": "1.0",
        "source": "retailops.synthetic-generator",
        "correlation_id": "order_8f4f7f4b",
        "occurred_at": "2026-05-07T10:15:30+00:00",
        "ingested_at": "2026-05-07T10:15:31+00:00",
        "payload": {
            "sale_id": "sale-1",
            "product_id": "product-1",
            "store_id": "store-1",
            "channel": "online",
            "quantity": "2",
            "total_amount": "14",
        },
    }


def test_event_envelope_validates_required_fields() -> None:
    envelope = RealtimeEventEnvelope.from_dict(sample_event())

    assert envelope.event_id
    assert envelope.event_type == "sale_completed"
    assert envelope.payload["sale_id"] == "sale-1"


def test_event_envelope_rejects_unknown_event_type() -> None:
    event = sample_event(event_type="unknown_event")

    with pytest.raises(ValueError, match="Unsupported event type"):
        RealtimeEventEnvelope.from_dict(event)


def test_consumer_processes_known_event_and_updates_state() -> None:
    class RecordingRepository:
        def __init__(self) -> None:
            self.records: list[tuple[str, dict[str, object]]] = []
            self.processed = False

        @contextmanager
        def event_transaction(self, event_id):
            yield self

        def get_event_record(self, event_id):
            return {"status": "processed"} if self.processed else None

        def record_event_log(self, **kwargs):
            self.records.append(("event_log", kwargs))
            return kwargs

        def replace_metric_observations(self, **kwargs):
            self.records.append(("metrics", kwargs))
            return len(kwargs["observations"])

        def upsert_consumer_state(self, **kwargs):
            self.records.append(("state", kwargs))
            return kwargs

    observed: list[str] = []
    repository = RecordingRepository()
    consumer = RealtimeEventConsumer(
        settings=Settings(broker_bootstrap_servers="redpanda:9092"),
        repository=repository,
        handlers={
            "sale_completed": lambda event: observed.append(str(event["event_id"])),
        },
    )

    result = consumer.process_event(sample_event())

    assert result["status"] == "processed"
    assert observed == ["10c72395-4d9c-4f07-a940-c220c7f3aaf3"]
    assert consumer.state.received_events == 1
    assert consumer.state.processed_events == 1
    assert consumer.state.failed_events == 0
    assert consumer.state.dead_lettered_events == 0
    assert consumer.state.last_event_type == "sale_completed"
    assert [kind for kind, _ in repository.records] == [
        "event_log",
        "metrics",
        "event_log",
        "state",
    ]


def test_consumer_ignores_duplicate_processed_events() -> None:
    class RecordingRepository:
        def __init__(self) -> None:
            self.records: list[tuple[str, dict[str, object]]] = []

        @contextmanager
        def event_transaction(self, event_id):
            yield self

        def get_event_record(self, event_id):
            return {"status": "processed"}

        def record_event_log(self, **kwargs):
            self.records.append(("event_log", kwargs))
            return kwargs

        def replace_metric_observations(self, **kwargs):
            self.records.append(("metrics", kwargs))
            return len(kwargs["observations"])

        def upsert_consumer_state(self, **kwargs):
            self.records.append(("state", kwargs))
            return kwargs

    repository = RecordingRepository()
    consumer = RealtimeEventConsumer(repository=repository)

    result = consumer.process_event(sample_event())

    assert result["status"] == "ignored_duplicate"
    assert consumer.state.received_events == 1
    assert consumer.state.ignored_events == 1
    assert consumer.state.processed_events == 0
    assert len(repository.records) == 1
    assert repository.records[0][0] == "state"


def test_consumer_validation_error_is_not_a_durable_dead_letter() -> None:
    repository = Mock(spec=RealtimeMetricsRepository)
    consumer = build_realtime_event_consumer(repository=repository)
    broken_event = sample_event()
    broken_event.pop("payload")

    with pytest.raises(InvalidRealtimeEventError, match="Missing required"):
        consumer.process_event(broken_event)

    assert consumer.state.received_events == 1
    assert consumer.state.processed_events == 0
    assert consumer.state.failed_events == 1
    assert consumer.state.dead_lettered_events == 0
    repository.record_event_log.assert_not_called()
    repository.replace_metric_observations.assert_not_called()


def test_consumer_snapshot_includes_broker_settings() -> None:
    consumer = RealtimeEventConsumer(
        settings=Settings(
            broker_bootstrap_servers="redpanda:9092",
            broker_group_id="retailops-consumer",
            broker_client_id="retailops-api",
        ),
    )

    snapshot = consumer.snapshot()

    assert snapshot["bootstrap_servers"] == "redpanda:9092"
    assert snapshot["group_id"] == "retailops-consumer"
    assert snapshot["client_id"] == "retailops-api"
    assert snapshot["consumer_name"] == "retailops-realtime-consumer"
    assert "sale_completed" in snapshot["supported_event_types"]


def test_consumer_rejects_mismatched_transport_topic_before_metrics() -> None:
    repository = Mock(spec=RealtimeMetricsRepository)
    consumer = RealtimeEventConsumer(repository=repository)

    with pytest.raises(InvalidRealtimeEventError, match="Transport topic mismatch"):
        consumer.process_event(sample_event(), transport_topic="retailops.inventory.v1")
    repository.replace_metric_observations.assert_not_called()


@pytest.mark.parametrize("field", ["payload", "event_type", "schema_version"])
def test_validation_diagnostics_do_not_copy_untrusted_content(field) -> None:
    repository = Mock(spec=RealtimeMetricsRepository)
    consumer = RealtimeEventConsumer(repository=repository)
    invalid = sample_event()
    content = "untrusted-payload-must-stay-in-raw-quarantine"
    invalid[field] = {"private_context": content} if field == "payload" else content
    with pytest.raises(InvalidRealtimeEventError) as captured:
        consumer.process_event(invalid)
    assert content not in str(captured.value)
    assert content not in repository.upsert_consumer_state.call_args.kwargs["last_error"]
