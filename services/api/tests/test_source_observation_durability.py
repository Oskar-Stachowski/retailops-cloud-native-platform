"""Actual Source version/outbox commits and authenticated Kafka delivery, no simulated ACKs."""

import json
import os
import select
import signal
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from confluent_kafka import Consumer, TopicPartition
from source_observation_runtime import publisher_runtime as publisher_runtime
from test_source_observation_outbox import fact, private_broker_document

from app.services.source_observation_broker import BrokerConfig, TOPIC, build_producer
from app.services.source_observation_outbox import (
    ObservationError,
    ObservationOutbox,
    ObservationPublisher,
)
from app.services.source_observation_wire import Envelope, canonical

pytestmark = pytest.mark.integration_broker


class PrivateContext:
    def __init__(self, **values):
        self.__dict__.update(values)

    def __repr__(self):
        return "<isolated private Source observation context>"


@pytest.fixture
def context(publisher_runtime):
    rt = publisher_runtime
    document = json.loads(rt.config.model_dump_json())
    document.update(
        source_authority_id=rt.config.source_authority_id,
        password=rt.passwords["producer"],
        username="producer",
    )
    config = BrokerConfig.model_validate_json(json.dumps(document))
    producer, topology = build_producer(config)
    stream, partitions = topology.inspect()
    database = rt.engine.url.render_as_string(hide_password=False).replace(
        "postgresql+psycopg://", "postgresql://"
    )
    with psycopg.connect(database) as conn:
        conn.execute(
            "TRUNCATE source_observation_outbox,source_observation_versions,source_observation_keys,source_observation_streams"
        )
    outbox = ObservationOutbox(database)
    outbox.bind(stream, partitions)
    reader = Consumer(
        {
            **rt.producer_config,
            "sasl.username": "reader",
            "sasl.password": rt.passwords["reader"],
            "group.id": "ai10-observation-" + uuid4().hex,
            "enable.auto.commit": False,
            "enable.auto.offset.store": False,
        }
    )
    starts = [
        TopicPartition(
            TOPIC,
            p,
            reader.get_watermark_offsets(
                TopicPartition(TOPIC, p), timeout=5, cached=False
            )[1],
        )
        for p in range(partitions)
    ]
    reader.assign(starts)
    yield PrivateContext(
        rt=rt,
        config=config,
        producer=producer,
        topology=topology,
        stream=stream,
        partitions=partitions,
        database=database,
        outbox=outbox,
        reader=reader,
    )
    reader.close()


def rows(ctx, query, params=()):
    with psycopg.connect(ctx.database) as conn:
        return conn.execute(query, params).fetchall()


def counts(ctx):
    owner = (ctx.stream.source_authority_id,)
    return tuple(
        rows(ctx, "SELECT count(*) FROM " + table + " WHERE authority_id=%s", owner)[0][
            0
        ]
        for table in (
            "source_observation_keys",
            "source_observation_versions",
            "source_observation_outbox",
        )
    )


def messages(ctx, count):
    result = []
    for _ in range(count):
        message = ctx.reader.poll(10)
        assert message is not None and message.error() is None
        assert message.topic() == TOPIC
        result.append(message)
    return result


def revision(row, version, units):
    data = json.loads(canonical(row))
    data.update(
        id=str(uuid4()),
        version=version,
        observed_units=units,
        available_at=(row.available_at + timedelta(days=version - 1)).isoformat(),
    )
    return type(row).model_validate_json(json.dumps(data))


def test_actual_sql_outbox_publish_correction_and_duplicate(context):
    ctx = context
    first = fact()
    second = revision(first, 2, 4)
    assert ctx.outbox.append(ctx.stream, ctx.partitions, first) == "inserted"
    assert ctx.outbox.append(ctx.stream, ctx.partitions, first) == "duplicate"
    assert ctx.outbox.append(ctx.stream, ctx.partitions, second) == "inserted"
    assert counts(ctx) == (1, 2, 2)
    publisher = ObservationPublisher(ctx.outbox, ctx.producer, ctx.topology)
    assert publisher.run() == 2
    got = messages(ctx, 2)
    envelopes = [Envelope.model_validate_json(m.value()) for m in got]
    assert [e.fact for e in envelopes] == [first, second]
    assert all(
        e.source_authority_id == ctx.stream.source_authority_id for e in envelopes
    )
    assert all(m.key() == first.observation_id.encode() for m in got)
    assert all(m.headers() == [("source-observation-version", b"1.0")] for m in got)
    assert [m.offset() for m in got] == [0, 1]
    assert rows(
        ctx,
        "SELECT delivered_offset FROM source_observation_outbox WHERE authority_id=%s ORDER BY sequence",
        (ctx.stream.source_authority_id,),
    ) == [(0,), (1,)]
    ctx.rt.passed("actual_sql_outbox_correction_duplicate_tls_delivery")


def test_failure_in_caller_transaction_rolls_back_fact_and_outbox(context):
    ctx = context
    with pytest.raises(ObservationError), ctx.outbox.transaction() as conn:
        ctx.outbox.append_on_connection(conn, ctx.stream, ctx.partitions, fact())
        raise ObservationError("injected_after_fact_and_outbox")
    assert counts(ctx) == (0, 0, 0)
    assert ObservationPublisher(ctx.outbox, ctx.producer, ctx.topology).run() == 0
    ctx.rt.passed("atomic_caller_transaction_rollback")


def test_concurrent_duplicate_writers_create_one_fact_and_one_event(context):
    ctx = context
    row = fact()
    with ThreadPoolExecutor(max_workers=4) as pool:
        statuses = list(
            pool.map(
                lambda _: ctx.outbox.append(ctx.stream, ctx.partitions, row), range(8)
            )
        )
    assert statuses.count("inserted") == 1 and statuses.count("duplicate") == 7
    assert counts(ctx) == (1, 1, 1)
    assert ObservationPublisher(ctx.outbox, ctx.producer, ctx.topology).run() == 1
    messages(ctx, 1)
    ctx.rt.passed("concurrent_sql_writers_one_effect")


def test_version_grain_and_availability_collisions_leave_no_partial_effect(context):
    ctx = context
    row = fact()
    ctx.outbox.append(ctx.stream, ctx.partitions, row)
    bad = [
        revision(row, 3, 3),
        revision(row, 2, 4).model_copy(
            update={"available_at": row.available_at - timedelta(seconds=1)}
        ),
        revision(row, 2, 4).model_copy(update={"channel": "online"}),
        row.model_copy(update={"observed_units": 4}),
        row.model_copy(update={"observation_id": str(uuid4())}),
        fact().model_copy(update={"id": row.id}),
    ]
    for invalid in bad:
        with pytest.raises(ObservationError):
            ctx.outbox.append(ctx.stream, ctx.partitions, invalid)
    assert counts(ctx) == (1, 1, 1)
    ctx.rt.passed("sql_history_collision_guards")


def test_real_sql_disconnect_after_delivery_keeps_pending_and_replays_identical_event(
    context,
):
    ctx = context
    row = fact()
    ctx.outbox.append(ctx.stream, ctx.partitions, row)

    def killed():
        pids = rows(
            ctx,
            "SELECT pid FROM pg_stat_activity WHERE application_name='source-observation-outbox' AND state='idle in transaction'",
        )
        assert len(pids) == 1
        assert rows(ctx, "SELECT pg_terminate_backend(%s)", (pids[0][0],)) == [(True,)]

    publisher = ObservationPublisher(
        ctx.outbox, ctx.producer, ctx.topology, after_delivery=killed
    )
    with pytest.raises(ObservationError):
        publisher.once()
    assert rows(
        ctx,
        "SELECT delivered_offset FROM source_observation_outbox WHERE authority_id=%s",
        (ctx.stream.source_authority_id,),
    ) == [(None,)]
    with pytest.raises(ObservationError, match="publisher_stopped"):
        publisher.once()
    producer, topology = build_producer(ctx.config)
    assert ObservationPublisher(ctx.outbox, producer, topology).run() == 1
    got = messages(ctx, 2)
    assert got[0].value() == got[1].value() and got[1].offset() == got[0].offset() + 1
    assert counts(ctx) == (1, 1, 1)
    ctx.rt.passed("sql_disconnect_after_delivery_identical_replay")


def test_actual_sigkill_after_delivery_before_sql_commit(context):
    ctx = context
    row = fact()
    ctx.outbox.append(ctx.stream, ctx.partitions, row)
    config = private_broker_document(ctx.config)
    config["password"] = ctx.rt.passwords["producer"]
    child = subprocess.Popen(
        [sys.executable, str(Path(__file__).with_name("source_observation_child.py"))],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])},
    )
    try:
        child.stdin.write(
            json.dumps({"database": ctx.database, "broker": config}).encode() + b"\n"
        )
        child.stdin.flush()
        ready, _, _ = select.select([child.stdout], [], [], 30)
        assert ready and child.stdout.readline() == b"DELIVERED\n"
        child.send_signal(signal.SIGKILL)
        assert child.wait(timeout=10) == -signal.SIGKILL
        assert rows(
            ctx,
            "SELECT delivered_offset FROM source_observation_outbox WHERE authority_id=%s",
            (ctx.stream.source_authority_id,),
        ) == [(None,)]
        assert ObservationPublisher(ctx.outbox, ctx.producer, ctx.topology).run() == 1
        got = messages(ctx, 2)
        assert got[0].value() == got[1].value()
        assert counts(ctx) == (1, 1, 1)
        ctx.rt.passed("actual_sigkill_delivery_before_sql_commit")
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=10)
        for pipe in (child.stdin, child.stdout, child.stderr):
            pipe.close()


def test_outbox_corruption_stops_without_delivery(context):
    ctx = context
    row = fact()
    ctx.outbox.append(ctx.stream, ctx.partitions, row)
    with psycopg.connect(ctx.database) as conn:
        conn.execute(
            "UPDATE source_observation_outbox SET event_bytes=%s WHERE authority_id=%s",
            (b"{}", ctx.stream.source_authority_id),
        )
    publisher = ObservationPublisher(ctx.outbox, ctx.producer, ctx.topology)
    with pytest.raises(ObservationError):
        publisher.once()
    assert ctx.reader.poll(0.2) is None
    assert rows(
        ctx,
        "SELECT delivered_offset FROM source_observation_outbox WHERE authority_id=%s",
        (ctx.stream.source_authority_id,),
    ) == [(None,)]
    ctx.rt.passed("outbox_corruption_no_delivery")


def test_broker_stream_binding_change_stops_before_delivery(context):
    ctx = context
    row = fact()
    ctx.outbox.append(ctx.stream, ctx.partitions, row)
    with psycopg.connect(ctx.database) as conn:
        conn.execute(
            "UPDATE source_observation_streams SET topic_id='foreign-native-topic' WHERE authority_id=%s",
            (ctx.stream.source_authority_id,),
        )
    with pytest.raises(ObservationError):
        ObservationPublisher(ctx.outbox, ctx.producer, ctx.topology).once()
    assert ctx.reader.poll(0.2) is None
    ctx.rt.passed("stream_binding_change_no_delivery")


def test_wrong_scram_credentials_keep_pending(context):
    ctx = context
    ctx.outbox.append(ctx.stream, ctx.partitions, fact())
    document = private_broker_document(ctx.config)
    document["password"] = "wrong-private-fixture"
    producer, topology = build_producer(
        BrokerConfig.model_validate_json(json.dumps(document))
    )
    with pytest.raises(ObservationError):
        ObservationPublisher(ctx.outbox, producer, topology).once()
    assert rows(
        ctx,
        "SELECT delivered_offset FROM source_observation_outbox WHERE authority_id=%s",
        (ctx.stream.source_authority_id,),
    ) == [(None,)]
    ctx.rt.passed("wrong_scram_no_completed_sql_receipt")


def test_compaction_change_stops_before_delivery(context):
    ctx = context
    ctx.outbox.append(ctx.stream, ctx.partitions, fact())
    from confluent_kafka.admin import ConfigResource, ResourceType

    resource = ConfigResource(
        ResourceType.TOPIC, TOPIC, set_config={"cleanup.policy": "compact"}
    )
    ctx.rt.admin.alter_configs([resource], request_timeout=10)[resource].result(
        timeout=12
    )
    try:
        with pytest.raises(ObservationError):
            ObservationPublisher(ctx.outbox, ctx.producer, ctx.topology).once()
        assert ctx.reader.poll(0.2) is None
        ctx.rt.passed("actual_compaction_change_no_delivery")
    finally:
        resource = ConfigResource(
            ResourceType.TOPIC, TOPIC, set_config={"cleanup.policy": "delete"}
        )
        ctx.rt.admin.alter_configs([resource], request_timeout=10)[resource].result(
            timeout=12
        )


def test_untrusted_ca_keeps_pending(context):
    ctx = context
    ctx.outbox.append(ctx.stream, ctx.partitions, fact())
    document = private_broker_document(ctx.config)
    document.update(
        password=ctx.rt.passwords["producer"],
        ca_file=str(ctx.rt.private / "untrusted.crt"),
    )
    producer, topology = build_producer(
        BrokerConfig.model_validate_json(json.dumps(document))
    )
    with pytest.raises(ObservationError):
        ObservationPublisher(ctx.outbox, producer, topology).once()
    assert rows(
        ctx,
        "SELECT delivered_offset FROM source_observation_outbox WHERE authority_id=%s",
        (ctx.stream.source_authority_id,),
    ) == [(None,)]
    ctx.rt.passed("untrusted_ca_no_completed_sql_receipt")


def test_backup_restore_nonempty_source_history_and_pending_publication(context):
    ctx = context
    row = fact()
    ctx.outbox.append(ctx.stream, ctx.partitions, row)
    assert ObservationPublisher(ctx.outbox, ctx.producer, ctx.topology).run() == 1
    ctx.outbox.append(ctx.stream, ctx.partitions, revision(row, 2, 4))
    name = "restored_" + uuid4().hex[:12]
    # Only this disposable PostgreSQL container/database is touched. Credentials
    # stay in private stdin/env of the owned docker process and are not printed.
    with psycopg.connect(ctx.database, autocommit=True) as conn:
        conn.execute(
            psycopg.sql.SQL("CREATE DATABASE {}").format(psycopg.sql.Identifier(name))
        )
    target = ctx.database.rsplit("/", 1)[0] + "/" + name
    before = {
        table: rows(ctx, "SELECT * FROM " + table + " ORDER BY 1,2")
        for table in (
            "source_observation_streams",
            "source_observation_keys",
            "source_observation_versions",
            "source_observation_outbox",
        )
    }
    from source_observation_runtime import command

    container = ctx.rt.container
    dump = command(
        [
            "docker",
            "exec",
            container,
            "pg_dump",
            "-U",
            "ai10",
            "-d",
            "ai10",
            "--format=custom",
        ]
    )
    command(
        [
            "docker",
            "exec",
            "-i",
            container,
            "pg_restore",
            "-U",
            "ai10",
            "-d",
            name,
            "--exit-on-error",
        ],
        input=dump,
    )
    restored = PrivateContext(database=target)
    for table, expected in before.items():
        assert rows(restored, "SELECT * FROM " + table + " ORDER BY 1,2") == expected
    assert (
        ObservationPublisher(
            ObservationOutbox(target), ctx.producer, ctx.topology
        ).run()
        == 1
    )
    got = messages(ctx, 2)
    assert [Envelope.model_validate_json(m.value()).fact.version for m in got] == [1, 2]
    ctx.rt.passed("nonempty_source_backup_restore_pending_resume")
