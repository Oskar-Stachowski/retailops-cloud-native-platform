from app.core.config import Settings
from app.services.realtime_consumer import (
    RealtimeEventConsumer,
    RealtimeEventEnvelope,
    build_realtime_event_consumer,
)


def sample_event(event_type: str = "sale_completed") -> dict[str, object]:
    return {
        "event_id": "01HXZ7M8E5K9Q3Q76W7J7Y5YV2",
        "event_type": event_type,
        "schema_version": "1.0",
        "source": "retailops.synthetic-generator",
        "correlation_id": "order_8f4f7f4b",
        "occurred_at": "2026-05-07T10:15:30+00:00",
        "ingested_at": "2026-05-07T10:15:31+00:00",
        "payload": {
            "sale_id": "sale-1",
            "product_id": "product-1",
        },
    }


def test_event_envelope_validates_required_fields() -> None:
    envelope = RealtimeEventEnvelope.from_dict(sample_event())

    assert envelope.event_id
    assert envelope.event_type == "sale_completed"
    assert envelope.payload["sale_id"] == "sale-1"


def test_event_envelope_rejects_unknown_event_type() -> None:
    event = sample_event(event_type="unknown_event")

    try:
        RealtimeEventEnvelope.from_dict(event)
    except ValueError as exc:
        assert "Unsupported event type" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_consumer_processes_known_event_and_updates_state() -> None:
    class RecordingRepository:
        def __init__(self) -> None:
            self.records: list[tuple[str, dict[str, object]]] = []
            self.processed = False

        def is_event_processed(self, event_id: str) -> bool:
            return self.processed

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
    assert observed == ["01HXZ7M8E5K9Q3Q76W7J7Y5YV2"]
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

        def is_event_processed(self, event_id: str) -> bool:
            return True

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


def test_consumer_records_failed_dead_letter_for_validation_error() -> None:
    class RecordingRepository:
        def __init__(self) -> None:
            self.records: list[tuple[str, dict[str, object]]] = []

        def is_event_processed(self, event_id: str) -> bool:
            return False

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
    consumer = build_realtime_event_consumer(repository=repository)
    broken_event = sample_event()
    broken_event.pop("payload")

    result = consumer.process_event(broken_event)

    assert result["status"] == "failed_dead_lettered"
    assert consumer.state.received_events == 1
    assert consumer.state.processed_events == 0
    assert consumer.state.failed_events == 1
    assert consumer.state.dead_lettered_events == 1
    assert consumer.state.last_error
    assert repository.records[0][0] == "event_log"
    assert repository.records[-1][0] == "state"


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
