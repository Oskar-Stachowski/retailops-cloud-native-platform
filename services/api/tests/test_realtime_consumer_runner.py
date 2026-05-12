import json

import pytest

from app.core.config import Settings
from app.services.realtime_consumer_runner import (
    RealtimeConsumerRunnerConfig,
    RealtimeKafkaConsumerRunner,
    build_realtime_kafka_consumer_runner,
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

    def process_event(self, event: dict[str, object]) -> dict[str, str]:
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


def test_runner_commits_invalid_json_without_processing_event() -> None:
    message = FakeMessage("not-json")
    kafka_consumer = FakeKafkaConsumer([message])
    event_consumer = FakeEventConsumer()
    runner = RealtimeKafkaConsumerRunner(
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
