from __future__ import annotations

import json
import logging
import os
import signal
import threading
from dataclasses import dataclass
from typing import Any, Protocol

from app.core.config import Settings
from app.core.config import settings as default_settings
from app.services.realtime_consumer import (
    RealtimeEventConsumer,
    build_realtime_event_consumer,
)

logger = logging.getLogger(__name__)


class KafkaMessage(Protocol):
    def value(self) -> bytes | str | None: ...

    def error(self) -> object | None: ...

    def topic(self) -> str: ...

    def partition(self) -> int: ...

    def offset(self) -> int: ...


class KafkaConsumerClient(Protocol):
    def subscribe(self, topics: list[str]) -> None: ...

    def poll(self, timeout: float) -> KafkaMessage | None: ...

    def commit(self, message: KafkaMessage, *, asynchronous: bool = False) -> object: ...

    def close(self) -> None: ...


@dataclass(frozen=True)
class RealtimeConsumerRunnerConfig:
    bootstrap_servers: str
    group_id: str
    client_id: str
    topics: tuple[str, ...]
    poll_timeout_seconds: float = 1.0
    auto_offset_reset: str = "earliest"
    commit_offsets: bool = True

    @classmethod
    def from_settings(
        cls,
        settings: Settings = default_settings,
        *,
        poll_timeout_seconds: float | None = None,
        commit_offsets: bool = True,
    ) -> RealtimeConsumerRunnerConfig:
        if not settings.broker_bootstrap_servers:
            msg = "RETAILOPS_BROKER_BOOTSTRAP_SERVERS is not configured."
            raise RuntimeError(msg)

        return cls(
            bootstrap_servers=settings.broker_bootstrap_servers,
            group_id=settings.broker_group_id,
            client_id=settings.broker_client_id,
            topics=tuple(settings.broker_topics),
            poll_timeout_seconds=(
                poll_timeout_seconds
                if poll_timeout_seconds is not None
                else _float_env("RETAILOPS_CONSUMER_POLL_TIMEOUT_SECONDS", 1.0)
            ),
            auto_offset_reset=os.getenv("RETAILOPS_CONSUMER_AUTO_OFFSET_RESET", "earliest"),
            commit_offsets=commit_offsets,
        )


class RealtimeKafkaConsumerRunner:
    def __init__(
        self,
        *,
        kafka_consumer: KafkaConsumerClient,
        event_consumer: RealtimeEventConsumer,
        config: RealtimeConsumerRunnerConfig,
    ) -> None:
        self.kafka_consumer = kafka_consumer
        self.event_consumer = event_consumer
        self.config = config

    def run(
        self,
        *,
        stop_event: threading.Event | None = None,
        max_messages: int | None = None,
    ) -> int:
        stop_event = stop_event or threading.Event()
        handled_messages = 0
        topics = list(self.config.topics)

        self.kafka_consumer.subscribe(topics)
        logger.info(
            "Realtime consumer subscribed to topics=%s bootstrap_servers=%s group_id=%s",
            ",".join(topics),
            self.config.bootstrap_servers,
            self.config.group_id,
        )

        self.event_consumer.start()
        try:
            while not stop_event.is_set():
                message = self.kafka_consumer.poll(self.config.poll_timeout_seconds)
                if message is None:
                    continue

                if message.error():
                    logger.warning("Kafka consumer message error: %s", message.error())
                    continue

                handled_messages += 1
                self._handle_message(message)

                if max_messages is not None and handled_messages >= max_messages:
                    break
        finally:
            self.event_consumer.stop()
            self.kafka_consumer.close()

        return handled_messages

    def _handle_message(self, message: KafkaMessage) -> None:
        try:
            event = decode_message_value(message.value())
            result = self.event_consumer.process_event(event)
            logger.info(
                "Processed realtime event status=%s topic=%s partition=%s offset=%s",
                result.get("status"),
                message.topic(),
                message.partition(),
                message.offset(),
            )
        except Exception:
            logger.exception(
                "Failed to process Kafka message topic=%s partition=%s offset=%s",
                message.topic(),
                message.partition(),
                message.offset(),
            )
        finally:
            if self.config.commit_offsets:
                self.kafka_consumer.commit(message=message, asynchronous=False)


def decode_message_value(value: bytes | str | None) -> dict[str, Any]:
    if value is None:
        msg = "Kafka message value is empty."
        raise ValueError(msg)

    raw_value = value.decode("utf-8") if isinstance(value, bytes) else value
    decoded = json.loads(raw_value)
    if not isinstance(decoded, dict):
        msg = "Kafka message value must decode to a JSON object."
        raise TypeError(msg)

    return decoded


def build_confluent_kafka_consumer(
    config: RealtimeConsumerRunnerConfig,
) -> KafkaConsumerClient:
    try:
        from confluent_kafka import Consumer
    except ImportError as exc:
        msg = (
            "confluent-kafka is required for the long-running realtime consumer. "
            "Install services/api/requirements.txt before running this command."
        )
        raise RuntimeError(msg) from exc

    return Consumer(
        {
            "bootstrap.servers": config.bootstrap_servers,
            "group.id": config.group_id,
            "client.id": config.client_id,
            "enable.auto.commit": False,
            "auto.offset.reset": config.auto_offset_reset,
            "enable.partition.eof": False,
        },
    )


def build_realtime_kafka_consumer_runner(
    *,
    settings: Settings = default_settings,
    config: RealtimeConsumerRunnerConfig | None = None,
    kafka_consumer: KafkaConsumerClient | None = None,
    event_consumer: RealtimeEventConsumer | None = None,
) -> RealtimeKafkaConsumerRunner:
    runner_config = config or RealtimeConsumerRunnerConfig.from_settings(settings)
    return RealtimeKafkaConsumerRunner(
        kafka_consumer=kafka_consumer or build_confluent_kafka_consumer(runner_config),
        event_consumer=event_consumer or build_realtime_event_consumer(settings=settings),
        config=runner_config,
    )


def run_realtime_consumer(
    *,
    settings: Settings = default_settings,
    stop_event: threading.Event | None = None,
    max_messages: int | None = None,
) -> int:
    runner = build_realtime_kafka_consumer_runner(settings=settings)
    return runner.run(stop_event=stop_event, max_messages=max_messages)


def build_signal_stop_event() -> threading.Event:
    stop_event = threading.Event()

    def _handle_signal(signum: int, _frame: object) -> None:
        logger.info("Received signal %s; stopping realtime consumer", signum)
        stop_event.set()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    return stop_event


def _float_env(name: str, default: float) -> float:
    raw_value = os.getenv(name)
    if raw_value in (None, ""):
        return default

    return float(raw_value)
