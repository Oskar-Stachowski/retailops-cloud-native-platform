"""Real DB/broker proof of atomic checkpoints, fencing and crash recovery."""

import base64
import copy
import json
import os
import subprocess
import sys
import threading
import time
from uuid import uuid4

import psycopg
import pytest
from confluent_kafka import Producer, TopicCollection, TopicPartition
from fastapi.testclient import TestClient
from test_intelligence_durability import (
    READ_PATH,
    context as context,
    fixture_event,
    intelligence_runtime as intelligence_runtime,
    positions,
    produce,
    result_count,
    rows,
    runtime as runtime,
)

from app.main import app
from app.services.intelligence_checkpoint import (
    CheckpointError,
    IntelligenceCheckpointStore,
    StreamIdentity,
    TransportRecord,
)
from app.services.intelligence_checkpoint_runner import (
    CheckpointBrokerConfig,
    IntelligenceCheckpointRunner,
    build_checkpoint_client,
)
from app.services.intelligence_contract import TOPIC

pytestmark = pytest.mark.integration_broker


def runner(context, *, store=None, bootstrap=True, client_wrapper=None):
    config = CheckpointBrokerConfig(
        bootstrap_servers=context.bootstrap,
        security_protocol="PLAINTEXT",
        allow_plaintext_loopback=True,
    )
    client, topology = build_checkpoint_client(config, context.group)
    return IntelligenceCheckpointRunner(
        kafka_consumer=client_wrapper(client) if client_wrapper else client,
        topology=topology,
        group=context.group,
        store=store,
        bootstrap=bootstrap,
    )


def run(context, *, count=1, **kwargs):
    instance = runner(context, **kwargs)
    stop = threading.Event()
    timer = threading.Timer(45, stop.set)
    timer.start()
    try:
        assert instance.run(stop_event=stop, max_messages=count) == count
    finally:
        timer.cancel()
    return instance


def checkpoint(context, partition=0):
    return rows(
        context,
        "SELECT coverage_start,next_offset,epoch,owner_id FROM "
        "ai_intelligence_partitions WHERE consumer_group=%s AND partition=%s",
        (context.group, partition),
    )[0]


def receipts(context):
    return rows(
        context,
        "SELECT partition,offset_number,outcome,raw_sha256 FROM "
        "ai_intelligence_transport WHERE consumer_group=%s ORDER BY partition,offset_number",
        (context.group,),
    )


def claim(context, *, owner=None, committed=None, bootstrap=True, **changes):
    instance = runner(context)
    try:
        stream, _ = instance.topology.inspect()
        low, high = instance.client.get_watermark_offsets(TopicPartition(TOPIC, 0), timeout=5)
    finally:
        instance.client.close()
    initial = context.initial[0].offset if committed is None else committed
    values = dict(
        group=context.group,
        partition=0,
        owner=owner or uuid4(),
        stream=stream,
        low=low,
        high=high,
        committed=initial,
        bootstrap=bootstrap,
    )
    values.update(changes)
    return IntelligenceCheckpointStore().claim(**values)


def test_real_broker_exposes_nonzero_cluster_and_topic_identity(context):
    instance = runner(context)
    try:
        admin = instance.topology.admin
        cluster = admin.describe_cluster(request_timeout=5).result(timeout=6)
        topic = admin.describe_topics(TopicCollection([TOPIC]), request_timeout=5)[TOPIC].result(
            timeout=6
        )
        assert cluster.cluster_id is not None, "DescribeCluster did not return a cluster ID"
        assert topic.topic_id is not None, "DescribeTopics did not return a topic UUID"
        assert str(topic.topic_id) != "AAAAAAAAAAAAAAAAAAAAAA", (
            "DescribeTopics returned the zero UUID"
        )
        stream, partitions = instance.topology.inspect()
        assert stream == StreamIdentity(str(cluster.cluster_id), str(topic.topic_id))
        assert partitions == (0, 1)
    finally:
        instance.client.close()


def test_two_partition_receipts_preserve_original_read_payload_and_deduplicate_business_event(
    context,
):
    first, second = fixture_event(), fixture_event()
    offset0 = produce(context, first, partition=0)
    produce(context, first, partition=0)
    offset1 = produce(context, second, partition=1)
    run(context, count=3)
    assert positions(context) == {0: offset0 + 2, 1: offset1 + 1}
    assert checkpoint(context, 0)[1] == offset0 + 2
    assert checkpoint(context, 1)[1] == offset1 + 1
    assert [row[2] for row in receipts(context)] == ["projected", "duplicate", "projected"]
    assert result_count(context, first) == result_count(context, second) == 1
    with TestClient(app) as api:
        response = api.get(
            READ_PATH + "/" + first["payload"]["prediction_id"], headers=context.headers
        )
    assert response.status_code == 200
    assert response.json()["forecast"] == first["payload"]


def test_sigkill_after_atomic_commit_before_ack_replays_transport_without_second_effect(context):
    event = fixture_event()
    offset = produce(context, event)
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
    process = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        timeout=45,
        env={**os.environ, "AI10_BROKER": context.bootstrap, "AI10_GROUP": context.group},
    )
    assert process.returncode == -9, process.stderr.decode()
    assert positions(context)[0] == offset
    assert checkpoint(context)[1] == offset + 1
    assert len(receipts(context)) == result_count(context, event) == 1
    before = receipts(context)
    run(context, bootstrap=False)
    assert positions(context)[0] == offset + 1
    assert receipts(context) == before
    assert result_count(context, event) == 1


def test_checkpoint_failure_after_projection_rolls_back_all_effects_and_never_acks_later(context):
    first, later = fixture_event(), fixture_event()
    offset = produce(context, first)
    produce(context, later)

    class FailingCheckpoint(IntelligenceCheckpointStore):
        @staticmethod
        def advance(connection, lease, next_offset):
            connection.execute("SELECT 1/0")

    with pytest.raises(psycopg.errors.DivisionByZero):
        run(context, count=2, store=FailingCheckpoint())
    assert positions(context)[0] == checkpoint(context)[1] == offset
    assert result_count(context, first) == result_count(context, later) == 0
    assert rows(
        context,
        "SELECT count(*) FROM ai_intelligence_inbox WHERE event_id=%s",
        (first["event_id"],),
    ) == [(0,)]
    assert receipts(context) == []
    run(context, count=2, bootstrap=False)
    assert positions(context)[0] == checkpoint(context)[1] == offset + 2


@pytest.mark.parametrize("raw", [b"invalid-json", b"\xff", b"[]", None])
def test_exact_raw_quarantine_headers_and_cursor_commit_together(context, raw):
    producer = Producer({"bootstrap.servers": context.bootstrap})
    delivered = []
    stamp = int(time.time() * 1000) - 1000
    producer.produce(
        TOPIC,
        partition=0,
        value=raw,
        key=b"\x00private-key",
        headers=[("same", b"\x00"), ("same", b"\xff"), ("null", None)],
        timestamp=stamp,
        on_delivery=lambda error, message: delivered.append((error, message)),
    )
    assert producer.flush(15) == 0
    assert delivered[0][0] is None
    offset = delivered[0][1].offset()
    run(context)
    stored = rows(
        context,
        "SELECT payload FROM realtime_event_log WHERE source=%s "
        "AND payload->'transport'->>'consumer_group'=%s",
        ("retailops.consumer.quarantine", context.group),
    )
    assert len(stored) == 1
    payload = stored[0][0]
    assert payload["value_base64"] == (base64.b64encode(raw).decode() if raw is not None else None)
    assert payload["transport"]["key_base64"] == base64.b64encode(b"\x00private-key").decode()
    assert payload["transport"]["headers_base64"] == [
        ["same", "AA=="],
        ["same", "/w=="],
        ["null", None],
    ]
    assert payload["transport"]["timestamp_ms"] == stamp
    assert positions(context)[0] == checkpoint(context)[1] == offset + 1
    assert receipts(context)[0][2] == "quarantined"


def test_checkpoint_failure_after_quarantine_rolls_back_raw_receipt_and_cursor(context):
    offset = produce(context, b"invalid-json")

    class FailingCheckpoint(IntelligenceCheckpointStore):
        @staticmethod
        def advance(connection, lease, next_offset):
            connection.execute("SELECT 1/0")

    with pytest.raises(psycopg.errors.DivisionByZero):
        run(context, store=FailingCheckpoint())
    assert positions(context)[0] == checkpoint(context)[1] == offset
    assert receipts(context) == []
    assert rows(
        context,
        "SELECT count(*) FROM realtime_event_log WHERE payload->'transport'->>'consumer_group'=%s",
        (context.group,),
    ) == [(0,)]
    run(context, bootstrap=False)
    assert positions(context)[0] == checkpoint(context)[1] == offset + 1


def test_identity_poison_quarantines_without_overwriting_projection(context):
    event = fixture_event()
    changed = copy.deepcopy(event)
    changed["payload"]["prediction"]["candidate"]["mean"] += 1
    offset = produce(context, event)
    produce(context, changed)
    run(context, count=2)
    assert [row[2] for row in receipts(context)] == ["projected", "quarantined"]
    assert positions(context)[0] == checkpoint(context)[1] == offset + 2
    assert rows(
        context,
        "SELECT payload FROM ai_forecast_results WHERE prediction_id=%s",
        (event["payload"]["prediction_id"],),
    ) == [(event["payload"],)]


def test_new_owner_fences_stale_worker_and_stale_release_cannot_clear_owner(context):
    event = fixture_event()
    offset = produce(context, event)
    old = claim(context)
    new = claim(context, bootstrap=False)
    assert new.epoch == old.epoch + 1
    store = IntelligenceCheckpointStore()
    record = TransportRecord(0, offset, json.dumps(event).encode())
    with pytest.raises(CheckpointError, match="partition_fenced"):
        store.process(old, record)
    store.release(old)
    assert checkpoint(context)[2:] == (new.epoch, new.owner)
    assert result_count(context, event) == 0
    assert receipts(context) == []
    store.process(new, record)
    assert checkpoint(context)[1] == offset + 1
    assert result_count(context, event) == 1
    assert positions(context)[0] == offset  # Direct DB proof never commits Kafka.


def test_future_offset_gap_fails_before_projection_and_does_not_move_cursor(context):
    event = fixture_event()
    offset = produce(context, event)
    lease = claim(context)
    with pytest.raises(CheckpointError, match="partition_offset_gap"):
        IntelligenceCheckpointStore().process(
            lease, TransportRecord(0, offset + 1, json.dumps(event).encode())
        )
    assert checkpoint(context)[1] == positions(context)[0] == offset
    assert result_count(context, event) == 0
    assert receipts(context) == []


@pytest.mark.parametrize(
    "changes",
    [
        {"value": b"changed"},
        {"key": b"changed"},
        {"headers": (("a", b"changed"),)},
        {"timestamp_ms": 2},
    ],
)
def test_replayed_transport_identity_includes_raw_key_headers_and_timestamp(context, changes):
    event = fixture_event()
    offset = produce(context, event)
    lease = claim(context)
    store = IntelligenceCheckpointStore()
    values = dict(
        partition=0,
        offset=offset,
        value=json.dumps(event).encode(),
        key=b"key",
        headers=(("a", b"one"), ("a", b"two")),
        timestamp_ms=1,
    )
    record = TransportRecord(**values)
    store.process(lease, record)
    before = receipts(context)
    assert store.process(lease, record)["transport_replayed"] is True
    with pytest.raises(CheckpointError, match="transport_identity_collision"):
        store.process(lease, TransportRecord(**{**values, **changes}))
    assert receipts(context) == before
    assert result_count(context, event) == 1


@pytest.mark.parametrize(
    "reason",
    ["broker_stream_changed", "broker_checkpoint_ahead", "retention_gap", "broker_log_rewound"],
)
def test_claim_rejects_changed_namespace_missing_log_or_unproven_broker_commit(context, reason):
    event = fixture_event()
    offset = produce(context, event)
    old = claim(context)
    changes = {
        "broker_stream_changed": {"stream": StreamIdentity("another-cluster", "another-topic")},
        "broker_checkpoint_ahead": {"committed": offset + 1},
        "retention_gap": {"low": offset + 1},
        "broker_log_rewound": {"high": offset - 1},
    }[reason]
    # Ensure a valid low/high range for the rewind guard, independently of retention.
    if reason == "broker_log_rewound" and offset == 0:
        IntelligenceCheckpointStore().process(
            old, TransportRecord(0, offset, json.dumps(event).encode())
        )
        changes = {"high": offset}
    before = checkpoint(context)
    with pytest.raises(CheckpointError, match=reason):
        claim(context, bootstrap=False, **changes)
    assert checkpoint(context) == before


def test_first_assignment_requires_explicit_bootstrap(context):
    produce(context, fixture_event())
    with pytest.raises(CheckpointError, match="partition_bootstrap_required"):
        run(context, bootstrap=False)
    assert receipts(context) == []
    assert rows(
        context,
        "SELECT count(*) FROM ai_intelligence_partitions WHERE consumer_group=%s",
        (context.group,),
    ) == [(0,)]


def test_real_rebalance_fences_revoked_worker_before_projection(context):
    first, second = runner(context), runner(context)
    clients = [first, second]
    old_leases = {}
    try:
        first.client.subscribe(
            [TOPIC], on_assign=first.assigned, on_revoke=first.revoked, on_lost=first.revoked
        )
        deadline = time.monotonic() + 45
        while len(first.leases) != 2 and time.monotonic() < deadline:
            first.client.poll(0.1)
        assert len(first.leases) == 2
        old_leases = dict(first.leases)
        second.client.subscribe(
            [TOPIC], on_assign=second.assigned, on_revoke=second.revoked, on_lost=second.revoked
        )
        while (len(first.leases) != 1 or len(second.leases) != 1) and time.monotonic() < deadline:
            for instance in clients:
                instance.client.poll(0.1)
        assert len(first.leases) == len(second.leases) == 1
        partition = next(iter(second.leases))
        event = fixture_event()
        offset = produce(context, event, partition=partition)
        with pytest.raises(CheckpointError, match="partition_fenced"):
            first.store.process(
                old_leases[partition],
                TransportRecord(partition, offset, json.dumps(event).encode()),
            )
        first.store.release(old_leases[partition])
        assert checkpoint(context, partition)[3] == second.owner
        assert result_count(context, event) == 0
        received = False
        while time.monotonic() < deadline:
            item = second.client.poll(0.1)
            first.client.poll(0.1)
            if item is not None and item.error() is None:
                second.handle(item)
                received = True
                break
        assert received
        assert checkpoint(context, partition)[1] == positions(context)[partition] == offset + 1
        assert result_count(context, event) == 1
    finally:
        for instance in clients:
            for lease in list(instance.leases.values()):
                instance.store.release(lease)
            instance.client.close()


def test_claim_waits_for_inflight_atomic_transaction_then_fences_its_old_epoch(context):
    from concurrent.futures import ThreadPoolExecutor

    from app.repositories.intelligence_repository import IntelligenceRepository

    event = fixture_event()
    offset = produce(context, event)
    lease = claim(context)
    staged, finish = threading.Event(), threading.Event()

    class HoldingProjection(IntelligenceRepository):
        def project_on_connection(self, connection, document):
            result = super().project_on_connection(connection, document)
            staged.set()
            assert finish.wait(2)
            return result

    store = IntelligenceCheckpointStore(projection=HoldingProjection())
    with ThreadPoolExecutor(max_workers=2) as pool:
        process = pool.submit(
            store.process, lease, TransportRecord(0, offset, json.dumps(event).encode())
        )
        assert staged.wait(2)
        claimant = pool.submit(
            IntelligenceCheckpointStore().claim,
            group=context.group,
            partition=0,
            owner=uuid4(),
            stream=lease.stream,
            low=0,
            high=offset + 1,
            committed=offset,
            bootstrap=False,
        )
        try:
            time.sleep(0.1)
            assert not claimant.done()
        finally:
            finish.set()
        assert process.result(timeout=3)["checkpoint_next_offset"] == offset + 1
        new = claimant.result(timeout=3)
    assert new.epoch == lease.epoch + 1
    assert checkpoint(context)[1] == offset + 1
    assert result_count(context, event) == 1
    with pytest.raises(CheckpointError, match="partition_fenced"):
        store.process(lease, TransportRecord(0, offset, json.dumps(event).encode()))
