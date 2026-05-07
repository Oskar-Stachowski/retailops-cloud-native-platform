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
    observed: list[str] = []
    consumer = RealtimeEventConsumer(
        settings=Settings(broker_bootstrap_servers="redpanda:9092"),
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


def test_consumer_records_failed_dead_letter_for_validation_error() -> None:
    consumer = build_realtime_event_consumer()
    broken_event = sample_event()
    broken_event.pop("payload")

    result = consumer.process_event(broken_event)

    assert result["status"] == "failed_dead_lettered"
    assert consumer.state.received_events == 1
    assert consumer.state.processed_events == 0
    assert consumer.state.failed_events == 1
    assert consumer.state.dead_lettered_events == 1
    assert consumer.state.last_error


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
    assert "sale_completed" in snapshot["supported_event_types"]
