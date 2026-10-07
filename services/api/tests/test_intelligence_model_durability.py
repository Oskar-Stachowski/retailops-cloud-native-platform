"""Real SQL/broker/API failure proof; native-shaped data are contract fixtures only."""

import copy
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4, uuid5

import psycopg
import pytest
from confluent_kafka import Producer
from fastapi.testclient import TestClient
from test_intelligence_checkpoint_durability import checkpoint, receipts, run
from test_intelligence_durability import (
    context as context,
    intelligence_runtime as intelligence_runtime,
    positions,
    rows,
    runtime as runtime,
)
from test_intelligence_model_access import TOKEN, model_policy

from app.main import app
from app.services.intelligence_checkpoint import IntelligenceCheckpointStore
from app.services.intelligence_contract import (
    CONTRACT_DIR,
    EVENT_NAMESPACE,
    TOPIC,
    content_hash,
    validate_event,
)
from app.services.intelligence_model_contract import decision_fields, model_partition_key, utc

pytestmark = pytest.mark.integration_broker
KINDS = ("anomaly_detected", "stockout_risk_scored")
RESOURCES = {"anomaly_detected": "anomalies", "stockout_risk_scored": "stockout-risks"}


def fixture_event(kind, *, run_id=None):
    event = json.loads((CONTRACT_DIR / (kind + ".fixture.json")).read_bytes())
    item = event["payload"]
    if kind == "anomaly_detected":
        item["batch_id"] = run_id or "anomaly-batch-sha256-" + hashlib.sha256(uuid4().bytes).hexdigest()
        item["inference_run_id"] = item["batch_id"]
    else:
        item["inference_run_id"] = run_id or "run-" + uuid4().hex
    return bind(event)


def bind(event):
    kind, item = event["event_type"], event["payload"]
    if kind == "anomaly_detected":
        decision = {name: item[name] for name in decision_fields()}
        decision["scoring_origin"] = utc(decision["scoring_origin"])
        key = {"batch_id": item["batch_id"], "decision": decision}
        field, prefix = "anomaly_id", "anomaly-sha256-"
    else:
        key = {"product_id": item["product_id"], "stock_location_id": item["stock_location_id"],
               "as_of": utc(item["as_of"]), "run_id": item["inference_run_id"],
               "release_id": item["release_id"], "source": item["lineage"]}
        field, prefix = "risk_id", "risk-sha256-"
    item[field] = prefix + content_hash(key)
    event.update(event_id=str(uuid5(EVENT_NAMESPACE, kind + ":" + item[field])),
                 correlation_id=item["inference_run_id"], occurred_at=item["generated_at"],
                 ingested_at=item["generated_at"])
    validate_event(event, transport_topic=TOPIC)
    return event


def identity(event):
    return event["payload"]["anomaly_id" if event["event_type"] == KINDS[0] else "risk_id"]


def result_count(context, event):
    return rows(context, "SELECT count(*) FROM ai_model_results WHERE result_id=%s", (identity(event),))[0][0]


def produce_model(context, event, *, partition=0):
    producer = Producer({"bootstrap.servers": context.bootstrap, "enable.idempotence": True})
    delivered = []
    producer.produce(TOPIC, partition=partition, key=model_partition_key(event).encode(),
                     value=json.dumps(event).encode(),
                     on_delivery=lambda error, message: delivered.append((error, message)))
    assert producer.flush(15) == 0
    assert len(delivered) == 1 and delivered[0][0] is None
    return delivered[0][1].offset()


@pytest.fixture
def model_headers(tmp_path, monkeypatch):
    policy = tmp_path / "model-access.json"
    policy.write_text(json.dumps(model_policy())); policy.chmod(0o600)
    monkeypatch.setenv("RETAILOPS_INTELLIGENCE_MODEL_ACCESS_POLICY", str(policy))
    return {"Authorization": "Bearer " + TOKEN}


@pytest.mark.parametrize("kind", KINDS)
def test_native_model_broker_projection_deduplicates_and_literal_id_api_preserves_payload(context, model_headers, kind):
    event = fixture_event(kind)
    offset = produce_model(context, event)
    produce_model(context, event)
    run(context, count=2)
    assert positions(context)[0] == checkpoint(context)[1] == offset + 2
    assert [item[2] for item in receipts(context)] == ["projected", "duplicate"]
    assert result_count(context, event) == 1
    assert rows(context, "SELECT count(*) FROM ai_model_intelligence_inbox WHERE event_id=%s", (event["event_id"],)) == [(1,)]
    assert rows(context, "SELECT model_result_id FROM ai_intelligence_transport WHERE consumer_group=%s ORDER BY offset_number", (context.group,)) == [(identity(event),), (identity(event),)]
    path = "/intelligence/v2/" + RESOURCES[kind]
    with TestClient(app) as api:
        response = api.get(path + "/" + identity(event), headers=model_headers)
        assert response.status_code == 200, response.text
        assert response.json()["result_id"] == identity(event)
        assert response.json()["result"] == event["payload"]
        assert response.json()["source"] == "retailops-ai"
        assert response.headers["cache-control"] == "no-store"
        foreign = fixture_event(kind)
        foreign["payload"]["product_id"] = "foreign-product"
        bind(foreign); produce_model(context, foreign); run(context, bootstrap=False)
        assert api.get(path + "/" + identity(foreign), headers=model_headers).status_code == 404
        assert api.get(path + "?product_id=foreign-product", headers=model_headers).status_code == 403
        assert api.get(path + "?user_id=platform-admin", headers=model_headers).status_code == 422
        assert api.get(path).status_code == 401


@pytest.mark.parametrize("kind", KINDS)
def test_model_checkpoint_sql_failure_rolls_back_result_inbox_receipt_and_ack(context, kind):
    first, later = fixture_event(kind), fixture_event(kind)
    offset = produce_model(context, first)
    produce_model(context, later)

    class FailingCheckpoint(IntelligenceCheckpointStore):
        @staticmethod
        def advance(connection, lease, next_offset):
            connection.execute("SELECT 1/0")

    with pytest.raises(psycopg.errors.DivisionByZero):
        run(context, count=2, store=FailingCheckpoint())
    assert positions(context)[0] == checkpoint(context)[1] == offset
    assert result_count(context, first) == result_count(context, later) == 0
    assert rows(context, "SELECT count(*) FROM ai_model_intelligence_inbox WHERE event_id=%s", (first["event_id"],)) == [(0,)]
    assert receipts(context) == []
    run(context, count=2, bootstrap=False)
    assert positions(context)[0] == checkpoint(context)[1] == offset + 2
    assert result_count(context, first) == result_count(context, later) == 1


@pytest.mark.parametrize("kind", KINDS)
def test_model_sigkill_after_sql_commit_before_ack_keeps_one_native_effect(context, kind):
    event = fixture_event(kind)
    offset = produce_model(context, event)
    code = """
import os, signal
from app.services.intelligence_checkpoint_runner import CheckpointBrokerConfig, IntelligenceCheckpointRunner, build_checkpoint_client
config = CheckpointBrokerConfig(bootstrap_servers=os.environ['AI10_BROKER'], security_protocol='PLAINTEXT', allow_plaintext_loopback=True)
client, topology = build_checkpoint_client(config, os.environ['AI10_GROUP'])
class KillBeforeAck:
    def __getattr__(self, name): return getattr(client, name)
    def commit(self, **kwargs): os.kill(os.getpid(), signal.SIGKILL)
IntelligenceCheckpointRunner(kafka_consumer=KillBeforeAck(), topology=topology, group=os.environ['AI10_GROUP'], bootstrap=True).run(max_messages=1)
"""
    process = subprocess.run([sys.executable, "-c", code], capture_output=True, timeout=45,
                             env={**os.environ, "AI10_BROKER": context.bootstrap, "AI10_GROUP": context.group})
    assert process.returncode == -9, process.stderr.decode()
    assert positions(context)[0] == offset
    assert checkpoint(context)[1] == offset + 1
    assert len(receipts(context)) == result_count(context, event) == 1
    before = receipts(context)
    run(context, bootstrap=False)
    assert positions(context)[0] == offset + 1
    assert receipts(context) == before
    assert result_count(context, event) == 1


@pytest.mark.parametrize("kind", KINDS)
def test_model_poison_and_identity_collision_quarantine_without_overwriting_result(context, kind):
    event = fixture_event(kind)
    poison = copy.deepcopy(event)
    poison["payload"]["inference_run_id"] = "run-invalid"
    offset = produce_model(context, poison)
    produce_model(context, event)
    collision = copy.deepcopy(event)
    collision["payload"]["generated_at"] = (datetime.fromisoformat(event["payload"]["generated_at"]) + timedelta(seconds=1)).isoformat()
    if kind == KINDS[0]:
        collision["payload"]["detected_at"] = collision["payload"]["generated_at"]
    bind(collision)
    assert identity(collision) == identity(event)
    produce_model(context, collision)
    run(context, count=3)
    assert positions(context)[0] == checkpoint(context)[1] == offset + 3
    assert [item[2] for item in receipts(context)] == ["quarantined", "projected", "quarantined"]
    assert rows(context, "SELECT payload FROM ai_model_results WHERE result_id=%s", (identity(event),)) == [(event["payload"],)]
    assert result_count(context, event) == 1
    assert rows(context, "SELECT count(*) FROM realtime_event_log WHERE source='retailops.consumer.quarantine' AND payload->'transport'->>'consumer_group'=%s", (context.group,)) == [(2,)]


@pytest.mark.parametrize("kind", KINDS)
def test_model_history_orders_business_origin_even_if_older_result_arrives_late(context, model_headers, kind):
    newer = fixture_event(kind)
    older = copy.deepcopy(newer)
    item = older["payload"]
    # A different immutable native result with the same logical run is enough
    # to prove ordering; the contract fixture is not a claim about model quality.
    item["as_of"] = (datetime.fromisoformat(item["as_of"]) - timedelta(days=1)).isoformat()
    if kind == KINDS[0]:
        item["scoring_origin"] = (datetime.fromisoformat(item["scoring_origin"]) - timedelta(days=1)).isoformat()
    bind(older)
    assert identity(older) != identity(newer)
    produce_model(context, newer); produce_model(context, older); run(context, count=2)
    with TestClient(app) as api:
        response = api.get("/intelligence/v2/" + RESOURCES[kind], params={"inference_run_id": item["inference_run_id"], "limit": 1}, headers=model_headers)
        assert response.status_code == 200, response.text
        page = response.json()
        assert page["selection"] == "immutable_history"
        assert page["items"][0]["result_id"] == identity(newer)
        assert page["pagination"]["total"] == 2
        response = api.get("/intelligence/v2/" + RESOURCES[kind], params={"inference_run_id": item["inference_run_id"], "limit": 1, "offset": 1, "view_sha256": page["view_sha256"]}, headers=model_headers)
        assert response.status_code == 200, response.text
        assert response.json()["items"][0]["result_id"] == identity(older)
    assert result_count(context, newer) == result_count(context, older) == 1


@pytest.mark.parametrize("kind", KINDS)
def test_model_rows_and_inboxes_are_immutable_in_postgresql(context, kind):
    event = fixture_event(kind); produce_model(context, event); run(context)
    for query, params in [
        ("UPDATE ai_model_results SET payload_sha256=%s WHERE result_id=%s", ("f" * 64, identity(event))),
        ("DELETE FROM ai_model_results WHERE result_id=%s", (identity(event),)),
        ("DELETE FROM ai_model_intelligence_inbox WHERE event_id=%s", (event["event_id"],)),
    ]:
        with pytest.raises(psycopg.errors.CheckViolation), psycopg.connect(context.db) as connection:
            connection.execute(query, params)
    assert result_count(context, event) == 1


def test_populated_model_schema_refuses_destructive_downgrade(context):
    events = [fixture_event(kind) for kind in KINDS]
    for event in events:
        produce_model(context, event)
    run(context, count=2)
    before = receipts(context)
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "a10f0c7e0500"],
        cwd=Path(__file__).resolve().parents[1], capture_output=True, timeout=30,
        env={**os.environ, "DATABASE_URL": context.db},
    )
    assert result.returncode != 0
    assert b"model_schema_downgrade_requires_empty_projection" in result.stderr
    assert rows(context, "SELECT version_num FROM alembic_version") == [("a10f0c7e0600",)]
    assert receipts(context) == before
    assert all(result_count(context, event) == 1 for event in events)
