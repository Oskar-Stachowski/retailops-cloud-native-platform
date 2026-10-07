"""Real PostgreSQL/Redpanda failure tests in an isolated, disposable runtime."""

import base64
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
from types import SimpleNamespace
from uuid import uuid4

from confluent_kafka import Consumer, KafkaError, KafkaException, Producer, TopicPartition
from confluent_kafka.admin import AdminClient, NewTopic
import psycopg
import pytest

from app.core.config import Settings
from app.repositories.realtime_metrics_repository import RealtimeMetricsRepository
from app.repositories.realtime_quarantine_repository import RealtimeQuarantineRepository
from app.services.realtime_consumer import RealtimeEventConsumer
from app.services.realtime_consumer_runner import (
    RealtimeConsumerRunnerConfig,
    RealtimeKafkaConsumerRunner,
    build_confluent_kafka_consumer,
)
from app.services.realtime_quarantine import replay_quarantined_message

pytestmark = pytest.mark.integration_broker
TOPIC = "retailops.sales.v1"
ROOT = Path(__file__).resolve().parents[3]
POSTGRES = (
    "postgres:16-alpine@sha256:721873c34ceb9f8d8fc265984940dc982404c105f19ad51be9fdc5970a6080ea"
)
REDPANDA = "redpandadata/redpanda:v25.3.6@sha256:ac152ec27adccf9482af2649d293f398eb03c860d7469fc49f86e30d870ea408"


def docker(*args):
    return subprocess.run(
        ["docker", *args], check=True, capture_output=True, text=True, timeout=120
    ).stdout.strip()


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_db(url):
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        try:
            with psycopg.connect(url, connect_timeout=2):
                return
        except psycopg.Error:
            time.sleep(0.2)
    pytest.fail("Isolated PostgreSQL did not become ready")


def wait_broker(bootstrap):
    deadline = time.monotonic() + 45
    admin = AdminClient({"bootstrap.servers": bootstrap})
    while time.monotonic() < deadline:
        try:
            if admin.list_topics(timeout=2).brokers:
                return
        except Exception:
            time.sleep(0.2)
    pytest.fail("Isolated Redpanda did not become ready")


def initial_offsets(client, timeout=45):
    """Wait for real partition reads after startup/restart, before committing offsets."""
    deadline = time.monotonic() + timeout
    last_error = "partition offsets unavailable"
    while time.monotonic() < deadline:
        initial = []
        for partition in range(2):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                offsets = client.get_watermark_offsets(
                    TopicPartition(TOPIC, partition), timeout=min(2, remaining), cached=False
                )
            except KafkaException as error:
                if error.args[0].code() not in (
                    KafkaError.NOT_LEADER_FOR_PARTITION,
                    KafkaError.LEADER_NOT_AVAILABLE,
                    KafkaError._TIMED_OUT,
                ):
                    raise
                last_error = str(error)
                break
            if offsets is None:
                last_error = f"partition {partition} offset query timed out"
                break
            initial.append(TopicPartition(TOPIC, partition, offsets[1]))
        else:
            return initial
        time.sleep(min(0.2, max(0, deadline - time.monotonic())))
    pytest.fail(f"Isolated Redpanda partition reads did not become ready: {last_error}")


@pytest.fixture(scope="module")
def runtime():
    if os.getenv("REQUIRE_BROKER_TESTS") != "1":
        pytest.skip("Set REQUIRE_BROKER_TESTS=1 to run the required real-broker drill")
    prefix = "retailops-ops03-" + uuid4().hex[:10]
    pg, broker = prefix + "-db", prefix + "-broker"
    pg_port, broker_port = free_port(), free_port()
    url = f"postgresql://ops03:ops03@127.0.0.1:{pg_port}/ops03?connect_timeout=3"
    bootstrap = f"127.0.0.1:{broker_port}"
    try:
        docker(
            "run",
            "-d",
            "--name",
            pg,
            "-p",
            f"127.0.0.1:{pg_port}:5432",
            "-e",
            "POSTGRES_USER=ops03",
            "-e",
            "POSTGRES_PASSWORD=ops03",
            "-e",
            "POSTGRES_DB=ops03",
            POSTGRES,
        )
        docker(
            "run",
            "-d",
            "--name",
            broker,
            "-p",
            f"127.0.0.1:{broker_port}:9092",
            REDPANDA,
            "redpanda",
            "start",
            "--mode",
            "dev-container",
            "--smp",
            "1",
            "--memory",
            "512M",
            "--reserve-memory",
            "0M",
            "--kafka-addr",
            "0.0.0.0:9092",
            "--advertise-kafka-addr",
            bootstrap,
        )
        wait_db(url)
        wait_broker(bootstrap)
        environment = {**os.environ, "DATABASE_URL": url, "PYTHONPATH": str(ROOT / "services/api")}
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=ROOT / "services/api",
            env=environment,
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
        admin = AdminClient({"bootstrap.servers": bootstrap})
        admin.create_topics([NewTopic(TOPIC, num_partitions=2, replication_factor=1)])[
            TOPIC
        ].result(timeout=15)
        yield SimpleNamespace(db=url, bootstrap=bootstrap, pg=pg, broker=broker)
    finally:
        # Only containers created by this fixture, including their anonymous data volumes.
        for name in (broker, pg):
            subprocess.run(["docker", "rm", "-fv", name], capture_output=True, timeout=45)


@pytest.fixture
def context(runtime, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", runtime.db)
    group = "ops03-" + uuid4().hex
    client = Consumer(
        {
            "bootstrap.servers": runtime.bootstrap,
            "group.id": group,
            "enable.auto.commit": False,
            "enable.auto.offset.store": False,
        }
    )
    try:
        initial = initial_offsets(client)
        client.commit(offsets=initial, asynchronous=False)
    finally:
        client.close()
    return SimpleNamespace(**vars(runtime), group=group, initial=initial)


def config(context):
    return RealtimeConsumerRunnerConfig(
        bootstrap_servers=context.bootstrap,
        group_id=context.group,
        client_id=context.group,
        topics=(TOPIC,),
        poll_timeout_seconds=0.1,
    )


def event():
    return {
        "event_id": str(uuid4()),
        "event_type": "sale_completed",
        "topic": TOPIC,
        "schema_version": "1.0",
        "source": "retailops.ops03.test",
        "correlation_id": "ops03",
        "occurred_at": "2026-09-30T10:00:00+00:00",
        "ingested_at": "2026-09-30T10:00:01+00:00",
        "payload": {
            "sale_id": str(uuid4()),
            "product_id": "product-1",
            "store_id": "store-1",
            "channel": "online",
            "quantity": "2",
            "total_amount": "14",
        },
    }


def produce(context, value, partition=0):
    producer = Producer({"bootstrap.servers": context.bootstrap, "enable.idempotence": True})
    receipts = []
    raw = json.dumps(value).encode() if isinstance(value, dict) else value
    producer.produce(
        TOPIC,
        partition=partition,
        key=b"\x00original-key",
        value=raw,
        headers=[("test", b"\xff"), ("test", None)],
        on_delivery=lambda error, message: receipts.append((error, message)),
    )
    assert producer.flush(15) == 0
    assert len(receipts) == 1 and receipts[0][0] is None
    return receipts[0][1].offset()


def run(context, *, count=1, handlers=None, kafka=None, quarantine=None):
    client = kafka or build_confluent_kafka_consumer(config(context))
    consumer = RealtimeEventConsumer(
        settings=Settings(broker_bootstrap_servers=context.bootstrap),
        consumer_name=context.group,
        handlers=handlers,
    )
    runner = RealtimeKafkaConsumerRunner(
        kafka_consumer=client,
        event_consumer=consumer,
        config=config(context),
        quarantine_repository=quarantine,
    )
    stop = threading.Event()
    timer = threading.Timer(60, stop.set)
    timer.start()
    try:
        assert runner.run(stop_event=stop, max_messages=count) == count
    finally:
        timer.cancel()


def positions(context):
    client = build_confluent_kafka_consumer(config(context))
    deadline = time.monotonic() + 45
    try:
        while time.monotonic() < deadline:
            try:
                committed = client.committed(
                    [TopicPartition(TOPIC, 0), TopicPartition(TOPIC, 1)],
                    timeout=min(10, max(0.1, deadline - time.monotonic())),
                )
                for partition in committed:
                    if partition.error is not None:
                        raise KafkaException(partition.error)
                return {p.partition: p.offset for p in committed}
            except KafkaException as error:
                # Broker readiness does not imply group-coordinator readiness
                # after restart. Retry only these transient reads, never writes
                # or missing/wrong durable offsets.
                if not error.args or not isinstance(error.args[0], KafkaError) or error.args[0].code() not in {
                    KafkaError.NOT_COORDINATOR, KafkaError.COORDINATOR_NOT_AVAILABLE,
                }:
                    raise
                time.sleep(0.2)
        pytest.fail("Isolated Kafka group coordinator did not provide committed offsets")
    finally:
        client.close()


def rows(context, query, params=()):
    with psycopg.connect(context.db) as connection:
        return connection.execute(query, params).fetchall()


def quarantined(context):
    return rows(
        context,
        """
        SELECT event_id::text, payload FROM realtime_event_log
        WHERE source = 'retailops.consumer.quarantine'
            AND payload->'transport'->>'consumer_group' = %s;
    """,
        (context.group,),
    )


def metric_count(context, event_id):
    return rows(
        context, "SELECT count(*) FROM live_metric_observations WHERE event_id=%s", (event_id,)
    )[0][0]


@pytest.mark.parametrize("raw", [b"not-json", b"\xff", b"[]", None, {"event_id": "not-a-uuid"}])
def test_poison_is_durable_before_ack_with_exact_bytes(context, raw):
    offset = produce(context, raw)
    run(context)
    stored = quarantined(context)
    assert len(stored) == 1
    payload = stored[0][1]
    expected = json.dumps(raw).encode() if isinstance(raw, dict) else raw
    assert payload["value_base64"] == (
        base64.b64encode(expected).decode() if expected is not None else None
    )
    assert payload["transport"]["offset"] == offset
    assert payload["transport"]["key_base64"] == base64.b64encode(b"\x00original-key").decode()
    assert payload["transport"]["headers_base64"] == [["test", "/w=="], ["test", None]]
    assert positions(context)[0] == offset + 1
    # PostgreSQL and broker restart retain both raw recovery bytes and offset.
    docker("restart", context.pg, context.broker)
    wait_db(context.db)
    wait_broker(context.bootstrap)
    assert quarantined(context) == stored
    assert positions(context)[0] == offset + 1


def test_handler_failure_stops_before_later_offset_and_retries(context):
    first, later = event(), event()
    offset = produce(context, first)
    produce(context, later)

    def fail(_event):
        raise ValueError("handler failure")

    with pytest.raises(ValueError, match="handler failure"):
        run(context, count=2, handlers={"sale_completed": fail})
    assert positions(context)[0] == offset
    assert metric_count(context, first["event_id"]) == 0
    assert metric_count(context, later["event_id"]) == 0
    assert quarantined(context) == []
    run(context, count=2)
    assert positions(context)[0] == offset + 2
    assert metric_count(context, first["event_id"]) == 3
    assert metric_count(context, later["event_id"]) == 3


@pytest.mark.parametrize(
    "field,value",
    [
        ("event_id", "not-a-uuid"),
        ("payload", {}),
        ("schema_version", "2.0"),
        ("schema_version", "1.1"),
        ("source", "retailops.consumer.quarantine"),
    ],
)
def test_invalid_envelope_is_quarantined_before_ack(context, field, value):
    invalid = event()
    invalid[field] = value
    offset = produce(context, invalid)
    run(context)
    assert positions(context)[0] == offset + 1
    assert len(quarantined(context)) == 1
    if field != "event_id":
        assert metric_count(context, invalid["event_id"]) == 0


def test_partial_projection_rolls_back_before_retry(context, monkeypatch):
    sale = event()
    offset = produce(context, sale)
    original = RealtimeMetricsRepository.record_event_log

    def fail_processed(self, **kwargs):
        if kwargs["status"] == "processed":
            self._execute("SELECT 1 / 0;")
        return original(self, **kwargs)

    monkeypatch.setattr(RealtimeMetricsRepository, "record_event_log", fail_processed)
    with pytest.raises(psycopg.errors.DivisionByZero):
        run(context)
    assert metric_count(context, sale["event_id"]) == 0
    assert (
        rows(
            context,
            "SELECT event_id FROM realtime_event_log WHERE event_id=%s",
            (sale["event_id"],),
        )
        == []
    )
    assert positions(context)[0] == offset
    monkeypatch.setattr(RealtimeMetricsRepository, "record_event_log", original)
    run(context)
    assert metric_count(context, sale["event_id"]) == 3
    assert positions(context)[0] == offset + 1


@pytest.mark.parametrize("poison", [False, True])
def test_db_or_quarantine_outage_leaves_broker_message_for_restart(context, poison):
    sale = event()
    offset = produce(context, b"invalid-json" if poison else sale)
    client = build_confluent_kafka_consumer(config(context))

    class Outage:
        def __getattr__(self, name):
            return getattr(client, name)

        def poll(self, timeout):
            message = client.poll(timeout)
            if message is not None and not message.error():
                docker("stop", "-t", "1", context.pg)
            return message

    try:
        with pytest.raises(psycopg.Error):
            run(context, kafka=Outage())
    finally:
        docker("start", context.pg)
        wait_db(context.db)
    assert positions(context)[0] == offset
    assert quarantined(context) == []
    run(context)
    assert positions(context)[0] == offset + 1
    assert len(quarantined(context)) == (1 if poison else 0)
    assert metric_count(context, sale["event_id"]) == (0 if poison else 3)


@pytest.mark.parametrize("poison", [False, True])
def test_sigkill_after_durable_write_before_ack_is_replayed_once(context, poison):
    sale = event()
    offset = produce(context, b"invalid-json" if poison else sale)
    code = """
import os, signal
from app.services.realtime_consumer import RealtimeEventConsumer
from app.services.realtime_consumer_runner import RealtimeConsumerRunnerConfig, RealtimeKafkaConsumerRunner, build_confluent_kafka_consumer
config = RealtimeConsumerRunnerConfig(bootstrap_servers=os.environ["OPS03_BROKER"], group_id=os.environ["OPS03_GROUP"], client_id="crash-test", topics=("retailops.sales.v1",), poll_timeout_seconds=0.1)
client = build_confluent_kafka_consumer(config)
class KillBeforeAck:
    def __getattr__(self, name):
        return getattr(client, name)
    def commit(self, **kwargs):
        os.kill(os.getpid(), signal.SIGKILL)
RealtimeKafkaConsumerRunner(kafka_consumer=KillBeforeAck(), event_consumer=RealtimeEventConsumer(consumer_name=config.group_id), config=config).run(max_messages=1)
"""
    environment = {
        **os.environ,
        "OPS03_BROKER": context.bootstrap,
        "OPS03_GROUP": context.group,
        "PYTHONPATH": str(ROOT / "services/api"),
    }
    result = subprocess.run(
        [sys.executable, "-c", code], env=environment, capture_output=True, timeout=60
    )
    assert result.returncode == -9, result.stderr.decode()
    before = quarantined(context)
    assert len(before) == (1 if poison else 0)
    assert metric_count(context, sale["event_id"]) == (0 if poison else 3)
    assert positions(context)[0] == offset
    run(context)
    assert positions(context)[0] == offset + 1
    assert quarantined(context) == before
    assert metric_count(context, sale["event_id"]) == (0 if poison else 3)


def test_reviewed_replay_retries_delivery_without_duplicate_metrics(context):
    produce(context, b"invalid-json")
    run(context)
    quarantine_id, raw = quarantined(context)[0]
    corrected = event()

    class MissingReceipt(RealtimeQuarantineRepository):
        def confirm_replay(self, *args, **kwargs):
            raise RuntimeError("DB failed after broker delivery")

    with pytest.raises(RuntimeError, match="DB failed after broker delivery"):
        replay_quarantined_message(
            quarantine_id,
            event=corrected,
            operator="test",
            bootstrap_servers=context.bootstrap,
            repository=MissingReceipt(),
        )
    run(context)
    assert metric_count(context, corrected["event_id"]) == 3
    receipt = replay_quarantined_message(
        quarantine_id, event=corrected, operator="test", bootstrap_servers=context.bootstrap
    )
    assert receipt["status"] == "replayed"
    run(context)
    assert metric_count(context, corrected["event_id"]) == 3
    assert quarantined(context)[0][1]["value_base64"] == raw["value_base64"]
    assert (
        replay_quarantined_message(
            quarantine_id, event=corrected, operator="test", bootstrap_servers=context.bootstrap
        )["status"]
        == "already_replayed"
    )
    changed = {**corrected, "event_id": str(uuid4())}
    with pytest.raises(ValueError, match="already pinned"):
        replay_quarantined_message(
            quarantine_id, event=changed, operator="test", bootstrap_servers=context.bootstrap
        )
