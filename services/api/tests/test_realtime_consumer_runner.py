import json
from unittest.mock import Mock

import pytest

from app.core.config import Settings
from app.services.realtime_consumer_runner import (
    RealtimeConsumerRunnerConfig,
    RealtimeKafkaConsumerRunner,
    build_realtime_kafka_consumer_runner,
    build_confluent_kafka_consumer,
    decode_message_value,
)


class FakeMessage:
    def __init__(self, value: bytes | str | None, *, error: object | None = None) -> None:
        self._value = value
        self._error = error

    def value(self) -> bytes | str | None:
        return self._value

    def error(self) -> object | None:
        return self._error

    def topic(self) -> str:
        return "retailops.sales.v1"

    def partition(self) -> int:
        return 0

    def offset(self) -> int:
        return 42

    def key(self):
        return b"key"

    def headers(self):
        return [("test", b"header")]

    def timestamp(self):
        return (1, 1770000000000)


class FakeKafkaConsumer:
    def __init__(self, messages: list[FakeMessage]) -> None:
        self.messages = messages
        self.subscribed_topics: list[str] = []
        self.committed_messages: list[FakeMessage] = []
        self.closed = False

    def subscribe(self, topics: list[str]) -> None:
        self.subscribed_topics = topics

    def poll(self, timeout: float) -> FakeMessage | None:
        assert timeout == 0.01
        if not self.messages:
            return None

        return self.messages.pop(0)

    def commit(self, message: FakeMessage, asynchronous: bool = False) -> object:
        assert asynchronous is False
        self.committed_messages.append(message)
        return None

    def close(self) -> None:
        self.closed = True


class FakeEventConsumer:
    def __init__(self) -> None:
        self.started = False
        self.stopped = False
        self.events: list[dict[str, object]] = []

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True

    def record_quarantined(self, **kwargs):
        self.quarantined = True

    def process_event(
        self, event: dict[str, object], *, transport_topic: str | None = None
    ) -> dict[str, str]:
        assert transport_topic == "retailops.sales.v1"
        self.events.append(event)
        return {"status": "processed"}


def test_decode_message_value_accepts_json_bytes() -> None:
    event = {"event_id": "event-1", "event_type": "sale_completed", "payload": {}}

    assert decode_message_value(json.dumps(event).encode("utf-8")) == event


def test_decode_message_value_rejects_non_object_payload() -> None:
    with pytest.raises(TypeError, match="JSON object"):
        decode_message_value("[1, 2, 3]")


def test_runner_subscribes_processes_commits_and_closes() -> None:
    event = {"event_id": "event-1", "event_type": "sale_completed", "payload": {}}
    message = FakeMessage(json.dumps(event).encode("utf-8"))
    kafka_consumer = FakeKafkaConsumer([message])
    event_consumer = FakeEventConsumer()
    runner = RealtimeKafkaConsumerRunner(
        kafka_consumer=kafka_consumer,
        event_consumer=event_consumer,
        config=RealtimeConsumerRunnerConfig(
            bootstrap_servers="redpanda:9092",
            group_id="retailops-api-consumer",
            client_id="retailops-api",
            topics=("retailops.sales.v1", "retailops.inventory.v1"),
            poll_timeout_seconds=0.01,
        ),
    )

    handled_messages = runner.run(max_messages=1)

    assert handled_messages == 1
    assert kafka_consumer.subscribed_topics == [
        "retailops.sales.v1",
        "retailops.inventory.v1",
    ]
    assert event_consumer.started is True
    assert event_consumer.stopped is True
    assert event_consumer.events == [event]
    assert kafka_consumer.committed_messages == [message]
    assert kafka_consumer.closed is True


def test_runner_commits_invalid_json_only_after_durable_quarantine() -> None:
    message = FakeMessage("not-json")
    kafka_consumer = FakeKafkaConsumer([message])
    event_consumer = FakeEventConsumer()
    quarantine = Mock()
    runner = RealtimeKafkaConsumerRunner(
        quarantine_repository=quarantine,
        kafka_consumer=kafka_consumer,
        event_consumer=event_consumer,
        config=RealtimeConsumerRunnerConfig(
            bootstrap_servers="redpanda:9092",
            group_id="retailops-api-consumer",
            client_id="retailops-api",
            topics=("retailops.sales.v1",),
            poll_timeout_seconds=0.01,
        ),
    )

    handled_messages = runner.run(max_messages=1)

    assert handled_messages == 1
    quarantine.store_message.assert_called_once()
    assert quarantine.store_message.call_args.kwargs["value"] == "not-json"
    assert event_consumer.quarantined is True
    assert event_consumer.events == []
    assert kafka_consumer.committed_messages == [message]
    assert kafka_consumer.closed is True


def test_runner_factory_accepts_injected_kafka_consumer() -> None:
    settings = Settings(
        broker_bootstrap_servers="redpanda:9092",
        broker_group_id="retailops-api-consumer",
        broker_client_id="retailops-api",
        broker_topics=["retailops.sales.v1"],
    )
    kafka_consumer = FakeKafkaConsumer([])
    event_consumer = FakeEventConsumer()

    runner = build_realtime_kafka_consumer_runner(
        settings=settings,
        kafka_consumer=kafka_consumer,
        event_consumer=event_consumer,
    )

    assert runner.config.bootstrap_servers == "redpanda:9092"
    assert runner.config.topics == ("retailops.sales.v1",)


def make_runner(messages, event_consumer=None, quarantine=None):
    kafka = FakeKafkaConsumer(messages)
    runner = RealtimeKafkaConsumerRunner(
        kafka_consumer=kafka,
        event_consumer=event_consumer or FakeEventConsumer(),
        quarantine_repository=quarantine or Mock(),
        config=RealtimeConsumerRunnerConfig(
            bootstrap_servers="broker:9092",
            group_id="test",
            client_id="test",
            topics=("retailops.sales.v1",),
            poll_timeout_seconds=0.01,
        ),
    )
    return runner, kafka


@pytest.mark.parametrize("error", [RuntimeError("DB down"), ValueError("handler failed")])
def test_runner_stops_without_committing_or_polling_past_failure(error):
    first, second = FakeMessage("{}"), FakeMessage("{}")
    handler = FakeEventConsumer()
    handler.process_event = Mock(side_effect=error)
    runner, kafka = make_runner([first, second], handler)
    with pytest.raises(type(error), match=str(error)):
        runner.run(max_messages=2)
    assert kafka.committed_messages == []
    assert kafka.messages == [second]
    assert kafka.closed


def test_quarantine_failure_leaves_offset_uncommitted():
    quarantine = Mock()
    quarantine.store_message.side_effect = RuntimeError("quarantine unavailable")
    runner, kafka = make_runner(
        [FakeMessage(b"not-json"), FakeMessage("{}")], quarantine=quarantine
    )
    with pytest.raises(RuntimeError, match="quarantine unavailable"):
        runner.run(max_messages=2)
    assert kafka.committed_messages == []
    assert len(kafka.messages) == 1
    assert kafka.closed


def test_unknown_processing_receipt_cannot_ack():
    handler = FakeEventConsumer()
    handler.process_event = Mock(return_value={"status": "failed_dead_lettered"})
    runner, kafka = make_runner([FakeMessage("{}")], handler)
    with pytest.raises(RuntimeError, match="durable success receipt"):
        runner.run(max_messages=1)
    assert kafka.committed_messages == []


def test_commit_partition_error_stops_before_next_message():
    runner, kafka = make_runner([FakeMessage("{}"), FakeMessage("{}")])
    kafka.commit = Mock(return_value=[Mock(error="failed")])
    with pytest.raises(RuntimeError, match="offset commit failed"):
        runner.run(max_messages=2)
    assert len(kafka.messages) == 1
    assert kafka.closed


def test_close_is_called_even_if_state_persistence_fails():
    handler = FakeEventConsumer()
    handler.start = Mock(side_effect=RuntimeError("DB down"))
    handler.stop = Mock(side_effect=RuntimeError("DB down"))
    runner, kafka = make_runner([], handler)
    with pytest.raises(RuntimeError, match="DB down"):
        runner.run(max_messages=1)
    assert kafka.closed


def test_factory_disables_both_automatic_offset_paths(monkeypatch):
    import confluent_kafka

    factory = Mock()
    monkeypatch.setattr(confluent_kafka, "Consumer", factory)
    config = RealtimeConsumerRunnerConfig(
        bootstrap_servers="broker:9092",
        group_id="test",
        client_id="test",
        topics=("retailops.sales.v1",),
    )
    build_confluent_kafka_consumer(config)
    passed = factory.call_args.args[0]
    assert passed["enable.auto.commit"] is False
    assert passed["enable.auto.offset.store"] is False


@pytest.mark.parametrize("raw", [None, b"\xff", "[]", "null", "not-json", '{"value":NaN}'])
def test_decode_rejects_poison_messages(raw):
    with pytest.raises((ValueError, TypeError)):
        decode_message_value(raw)
