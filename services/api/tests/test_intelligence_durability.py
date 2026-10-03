"""Real isolated PostgreSQL/Redpanda/read-API tests on explicitly invented forecasts."""

import base64
import copy
import hashlib
import json
import os
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4, uuid5

import psycopg
import pytest
from confluent_kafka import Consumer, KafkaException, Producer, TopicPartition
from confluent_kafka.admin import AdminClient, NewTopic
from fastapi.testclient import TestClient
from test_realtime_durability import docker, runtime as runtime, wait_db

from app.auth.intelligence import access_policy
from app.main import app
from app.repositories.intelligence_repository import IntelligenceRepository
from app.repositories.realtime_quarantine_repository import RealtimeQuarantineRepository
from app.services.intelligence_consumer import IntelligenceEventConsumer
from app.services.intelligence_contract import CONTRACT_DIR, EVENT_NAMESPACE, TOPIC, content_hash
from app.services.realtime_consumer_runner import (
    RealtimeConsumerRunnerConfig,
    RealtimeKafkaConsumerRunner,
    build_confluent_kafka_consumer,
)

pytestmark = pytest.mark.integration_broker
READ_PATH = "/intelligence/v2/forecasts"


def fixture_event(*, origin=None, artifact=None, run_id=None, product_id="fixture-product"):
    event = json.loads((CONTRACT_DIR / "forecast_generated.fixture.json").read_bytes())
    payload = event["payload"]
    artifact = artifact or uuid4().hex*2
    origin = origin or datetime(2026, 10, 1, 23, 59, 59, tzinfo=UTC)
    generated = origin + timedelta(seconds=1)
    payload.update(
        product_id=product_id,
        prediction_dataset_id="v12-forecasts-sha256-" + artifact,
        inference_run_id=run_id or "run-" + uuid4().hex,
        forecast_origin=origin.isoformat().replace("+00:00", "Z"),
        generated_at=generated.isoformat().replace("+00:00", "Z"),
        target_date=(origin.date()+timedelta(days=1)).isoformat(),
    )
    payload["freshness"]["evaluated_at"] = payload["generated_at"]
    key = {name: payload[name] for name in (
        "product_id", "selling_location_id", "channel", "forecast_origin",
        "business_timezone", "cutoff_policy", "target_date", "horizon_days",
    )}
    payload["prediction_id"] = "prediction-sha256-" + content_hash({
        "projection": "forecast-v12-read-v1", "artifact_id": payload["prediction_dataset_id"], "key": key,
    })
    event.update(
        event_id=str(uuid5(EVENT_NAMESPACE, "forecast_generated:" + payload["prediction_id"])),
        correlation_id=payload["inference_run_id"], occurred_at=payload["generated_at"],
        ingested_at=payload["generated_at"],
    )
    return event


@pytest.fixture(scope="module")
def intelligence_runtime(runtime):
    admin = AdminClient({"bootstrap.servers": runtime.bootstrap})
    admin.create_topics([
        NewTopic(TOPIC, num_partitions=2, replication_factor=1)
    ])[TOPIC].result(timeout=15)
    return runtime


@pytest.fixture
def context(intelligence_runtime, monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", intelligence_runtime.db)
    group = "ai10-" + uuid4().hex
    client = Consumer({"bootstrap.servers": intelligence_runtime.bootstrap, "group.id": group,
                       "enable.auto.commit": False, "enable.auto.offset.store": False})
    try:
        deadline = time.monotonic()+45
        while True:
            try:
                initial = [TopicPartition(TOPIC, p, client.get_watermark_offsets(
                    TopicPartition(TOPIC, p), timeout=2, cached=False,
                )[1]) for p in range(2)]
                break
            except KafkaException:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.2)
        client.commit(offsets=initial, asynchronous=False)
    finally:
        client.close()
    token = uuid4().hex*2
    policy = tmp_path / "access-policy.json"
    policy.write_text(json.dumps({
        "version": "retailops-intelligence-access-1.0", "principals": [{
            "principal_id": "ai10-fixture-reader",
            "credential_sha256": hashlib.sha256(token.encode()).hexdigest(),
            "capabilities": ["forecast:read"], "product_ids": ["fixture-product"],
            "selling_location_ids": ["fixture-store"], "channels": ["store"],
            "release_ids": ["v12-model-release-sha256-" + "a"*64],
        }],
    }))
    policy.chmod(0o600)
    monkeypatch.setenv("RETAILOPS_INTELLIGENCE_ACCESS_POLICY", str(policy))
    access_policy.cache_clear()
    try:
        yield SimpleNamespace(**vars(intelligence_runtime), group=group, initial=initial,
                              headers={"Authorization": "Bearer " + token}, policy=policy)
    finally:
        access_policy.cache_clear()


def config(context):
    return RealtimeConsumerRunnerConfig(
        bootstrap_servers=context.bootstrap, group_id=context.group, client_id=context.group,
        topics=(TOPIC,), poll_timeout_seconds=0.1,
    )


def produce(context, value, partition=0):
    producer = Producer({"bootstrap.servers": context.bootstrap, "enable.idempotence": True})
    receipts = []
    raw = json.dumps(value).encode() if isinstance(value, dict) else value
    producer.produce(TOPIC, partition=partition, key=b"ai10-fixture", value=raw,
                     on_delivery=lambda error, message: receipts.append((error, message)))
    assert producer.flush(15) == 0
    assert len(receipts) == 1 and receipts[0][0] is None
    return receipts[0][1].offset()


def run(context, *, count=1, repository=None, kafka=None):
    runner = RealtimeKafkaConsumerRunner(
        kafka_consumer=kafka or build_confluent_kafka_consumer(config(context)),
        event_consumer=IntelligenceEventConsumer(repository), config=config(context),
    )
    stop = threading.Event()
    timer = threading.Timer(45, stop.set)
    timer.start()
    try:
        assert runner.run(stop_event=stop, max_messages=count) == count
    finally:
        timer.cancel()


def positions(context):
    client = build_confluent_kafka_consumer(config(context))
    try:
        return {p.partition: p.offset for p in client.committed(
            [TopicPartition(TOPIC, 0), TopicPartition(TOPIC, 1)], timeout=10,
        )}
    finally:
        client.close()


def rows(context, query, params=()):
    with psycopg.connect(context.db) as connection:
        return connection.execute(query, params).fetchall()


def result_count(context, event):
    return rows(context, "SELECT count(*) FROM ai_forecast_results WHERE prediction_id=%s",
                (event["payload"]["prediction_id"],))[0][0]


def test_duplicate_forecast_is_durable_and_readable_with_original_ml_lineage(context):
    event = fixture_event()
    offset = produce(context, event)
    produce(context, event)
    run(context, count=2)
    assert positions(context)[0] == offset+2
    assert result_count(context, event) == 1
    assert rows(context, "SELECT count(*) FROM ai_intelligence_inbox WHERE event_id=%s",
                (event["event_id"],))[0][0] == 1
    with TestClient(app) as client:
        result = client.get(READ_PATH + "/" + event["payload"]["prediction_id"], headers=context.headers)
        assert result.status_code == 200
        assert result.json()["source"] == "retailops-ai"
        assert result.json()["forecast"] == event["payload"]
        assert result.json()["freshness"]["status"] in {"stale", "unknown"}
        assert "received_at" in result.json()
        assert client.get(READ_PATH).status_code == 401
        assert client.get(READ_PATH + "?user_id=admin", headers=context.headers).status_code == 422
        assert client.get(READ_PATH + "?selling_location_id=foreign", headers=context.headers).status_code == 403
        assert client.get(READ_PATH + "?release_id=foreign", headers=context.headers).status_code == 403
        assert client.get(READ_PATH + "?store_id=foreign", headers=context.headers).status_code == 422
        assert client.get(READ_PATH + "?limit=101", headers=context.headers).status_code == 422
        assert client.post(READ_PATH, headers=context.headers).status_code == 405
        # Foreign scope is inaccessible even with its exact result ID.
        foreign = fixture_event(product_id="foreign")
        produce(context, foreign)
        run(context)
        assert client.get(READ_PATH + "/" + foreign["payload"]["prediction_id"], headers=context.headers).status_code == 404


def test_history_keeps_newer_origin_first_when_older_result_arrives_late(context):
    run_id = "run-" + uuid4().hex
    newer = fixture_event(origin=datetime(2026, 10, 2, 23, 59, 59, tzinfo=UTC), run_id=run_id)
    older = fixture_event(run_id=run_id)
    produce(context, newer)
    produce(context, older)
    run(context, count=2)
    with TestClient(app) as client:
        result = client.get(READ_PATH, params={"inference_run_id": run_id}, headers=context.headers).json()
    assert result["selection"] == "immutable_history"
    assert [item["forecast"]["prediction_id"] for item in result["items"]] == [
        newer["payload"]["prediction_id"], older["payload"]["prediction_id"],
    ]
    assert result_count(context, newer) == result_count(context, older) == 1


def test_real_db_failure_after_projection_rolls_back_and_does_not_ack_gap(context):
    first, later = fixture_event(), fixture_event()
    offset = produce(context, first)
    produce(context, later)

    class FailingRepository(IntelligenceRepository):
        @staticmethod
        def _insert_result(connection, payload, payload_hash):
            IntelligenceRepository._insert_result(connection, payload, payload_hash)
            connection.execute("SELECT 1/0")

    with pytest.raises(psycopg.errors.DivisionByZero):
        run(context, count=2, repository=FailingRepository())
    assert positions(context)[0] == offset
    assert result_count(context, first) == result_count(context, later) == 0
    assert rows(context, "SELECT count(*) FROM ai_intelligence_inbox WHERE event_id=%s",
                (first["event_id"],))[0][0] == 0
    run(context, count=2)
    assert result_count(context, first) == result_count(context, later) == 1
    assert positions(context)[0] == offset+2


@pytest.mark.parametrize("raw", [b"invalid-json", b"\xff", b"[]", None])
def test_invalid_json_retains_exact_raw_before_ack(context, raw):
    offset = produce(context, raw)
    run(context)
    stored = rows(context, "SELECT payload FROM realtime_event_log WHERE source=%s "
                          "AND payload->'transport'->>'consumer_group'=%s",
                  ("retailops.consumer.quarantine", context.group))
    assert len(stored) == 1
    assert stored[0][0]["value_base64"] == (base64.b64encode(raw).decode() if raw is not None else None)
    assert stored[0][0]["transport"]["offset"] == offset
    assert positions(context)[0] == offset+1


def test_same_result_id_with_changed_functional_is_quarantined_without_overwrite(context):
    original = fixture_event()
    changed = copy.deepcopy(original)
    changed["payload"]["prediction"]["candidate"]["mean"] += 1
    produce(context, original)
    produce(context, changed)
    run(context, count=2)
    assert result_count(context, original) == 1
    stored = rows(context, "SELECT payload FROM ai_forecast_results WHERE prediction_id=%s",
                  (original["payload"]["prediction_id"],))[0][0]
    assert stored == original["payload"]
    quarantined = rows(context, "SELECT error_message FROM realtime_event_log WHERE source=%s "
                               "AND payload->'transport'->>'consumer_group'=%s",
                       ("retailops.consumer.quarantine", context.group))
    assert quarantined == [("intelligence_event_identity_collision",)]


def test_sigkill_after_projection_before_ack_replays_with_one_effect(context):
    event = fixture_event()
    offset = produce(context, event)
    code = """
import os, signal
from app.services.intelligence_consumer import IntelligenceEventConsumer
from app.services.intelligence_contract import TOPIC
from app.services.realtime_consumer_runner import RealtimeConsumerRunnerConfig, RealtimeKafkaConsumerRunner, build_confluent_kafka_consumer
config = RealtimeConsumerRunnerConfig(bootstrap_servers=os.environ["AI10_BROKER"], group_id=os.environ["AI10_GROUP"], client_id="ai10-crash", topics=(TOPIC,), poll_timeout_seconds=0.1)
client = build_confluent_kafka_consumer(config)
class KillBeforeAck:
    def __getattr__(self, name): return getattr(client, name)
    def commit(self, **kwargs): os.kill(os.getpid(), signal.SIGKILL)
RealtimeKafkaConsumerRunner(kafka_consumer=KillBeforeAck(), event_consumer=IntelligenceEventConsumer(), config=config).run(max_messages=1)
"""
    process = subprocess.run([sys.executable, "-c", code], capture_output=True, timeout=45,
                             env={**os.environ, "AI10_BROKER": context.bootstrap, "AI10_GROUP": context.group})
    assert process.returncode == -9
    assert positions(context)[0] == offset
    assert result_count(context, event) == 1
    run(context)
    assert positions(context)[0] == offset+1
    assert result_count(context, event) == 1


def test_db_and_quarantine_outage_does_not_ack_or_skip_a_later_record(context):
    offset = produce(context, b"invalid-json")
    later = fixture_event()
    produce(context, later)
    client = build_confluent_kafka_consumer(config(context))

    class Outage:
        def __getattr__(self, name): return getattr(client, name)
        def poll(self, timeout):
            message = client.poll(timeout)
            if message is not None and not message.error():
                docker("stop", "-t", "1", context.pg)
            return message

    try:
        with pytest.raises(psycopg.Error):
            run(context, count=2, kafka=Outage())
        with TestClient(app) as api:
            assert api.get(READ_PATH, headers=context.headers).status_code == 503
    finally:
        docker("start", context.pg)
        wait_db(context.db)
    assert positions(context)[0] == offset
    assert result_count(context, later) == 0
    run(context, count=2)
    assert positions(context)[0] == offset+2
    assert result_count(context, later) == 1


def test_pagination_over_100_is_scoped_bounded_and_detects_a_changed_view(context):
    run_id = "run-" + uuid4().hex
    events = [fixture_event(run_id=run_id) for _ in range(102)]
    for event in events:
        produce(context, event)
    run(context, count=102)
    with TestClient(app) as api:
        query = {"inference_run_id": run_id}
        default = api.get(READ_PATH, params=query, headers=context.headers).json()
        assert len(default["items"]) == 50 and default["pagination"]["total"] == 102
        first = api.get(READ_PATH, params={**query, "limit": 100}, headers=context.headers).json()
        second_query = {**query, "limit": 100, "offset": 100, "view_sha256": first["view_sha256"]}
        second = api.get(READ_PATH, params=second_query, headers=context.headers).json()
        assert len(first["items"]) == 100 and len(second["items"]) == 2
        assert second["pagination"]["next_offset"] is None
        ids = [item["forecast"]["prediction_id"] for item in first["items"]+second["items"]]
        assert len(set(ids)) == 102
        assert api.get(READ_PATH, params={**query, "offset": 100}, headers=context.headers).status_code == 409
        empty = api.get(READ_PATH, params={"inference_run_id": "run-" + "0"*32},
                        headers=context.headers).json()
        assert empty["items"] == [] and empty["data_status"] == "no_data"
        produce(context, fixture_event(run_id=run_id))
        run(context)
        assert api.get(READ_PATH, params=second_query, headers=context.headers).status_code == 409
        context.policy.chmod(0o644)
        access_policy.cache_clear()
        assert api.get(READ_PATH, headers=context.headers).status_code == 503
