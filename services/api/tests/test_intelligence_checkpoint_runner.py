"""Offline boundary tests; transaction durability is covered with real PostgreSQL/Kafka."""

import json
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import psycopg
import pytest
from confluent_kafka import TopicPartition

from app.services import intelligence_checkpoint_runner as module
from app.services.intelligence_checkpoint import (
    CheckpointError,
    PartitionLease,
    StreamIdentity,
    TransportRecord,
)
from app.services.intelligence_checkpoint_runner import (
    BrokerTopology,
    CheckpointBrokerConfig,
    IntelligenceCheckpointRunner,
    build_checkpoint_client,
)
from app.services.intelligence_contract import TOPIC

STREAM = StreamIdentity("fixture-cluster", "fixture-topic")
GROUP = "fixture-checkpoint-group"


def configuration(**changes):
    return CheckpointBrokerConfig.model_validate(
        {
            "bootstrap_servers": "127.0.0.1:9092",
            "security_protocol": "PLAINTEXT",
            "allow_plaintext_loopback": True,
            **changes,
        }
    )


def message(offset=10, partition=0, **changes):
    values = {
        "topic": TOPIC,
        "partition": partition,
        "offset": offset,
        "value": b"fixture",
        "key": b"fixture-key",
        "headers": [("duplicate", b"1"), ("duplicate", b"2")],
        "timestamp": (1, 1000),
        "error": None,
        **changes,
    }
    return SimpleNamespace(**{name: lambda value=value: value for name, value in values.items()})


def runner():
    client, store, topology = Mock(), Mock(), Mock()
    topology.inspect.return_value = STREAM, (0, 1)
    instance = IntelligenceCheckpointRunner(
        kafka_consumer=client,
        topology=topology,
        group=GROUP,
        store=store,
    )
    lease = PartitionLease(GROUP, 0, instance.owner, 1, 10, 10, STREAM)
    instance.leases[0] = lease
    instance.delivery_offsets[0] = 10
    client.commit.return_value = [TopicPartition(TOPIC, 0, 11)]
    store.process.return_value = {"status": "processed", "checkpoint_next_offset": 11}
    return instance, client, store


@pytest.mark.parametrize(
    "changes",
    [
        {"bootstrap_servers": "remote.example:9092"},
        {"allow_plaintext_loopback": False},
        {"bootstrap_servers": "user:password@localhost:9092"},
        {"bootstrap_servers": "localhost:9092/path"},
        {"bootstrap_servers": "localhost:9092?token=secret"},
        {"bootstrap_servers": "localhost"},
        {"bootstrap_servers": ",".join(["localhost:9092"] * 9)},
        {"security_protocol": "SASL_SSL"},
        {"username": "private", "password": "secret"},
        {"enable.auto.commit": True},
    ],
)
def test_configuration_rejects_unsafe_or_unknown_settings(changes):
    with pytest.raises(ValueError):
        configuration(**changes)


def test_credentials_are_hidden_and_used_only_by_fixed_backend():
    config = CheckpointBrokerConfig.model_validate(
        {
            "bootstrap_servers": "broker.example:9093",
            "username": "private-user",
            "password": "private-password",
            "ca_file": "/private/ca.pem",
        }
    )
    assert "private-password" not in repr(config)
    assert "private-user" not in repr(config)
    assert config.backend()["sasl.password"] == "private-password"
    assert config.backend()["security.protocol"] == "SASL_SSL"
    assert config.backend()["log_level"] == 0


def test_private_configuration_requires_owner_only_regular_file(tmp_path):
    path = tmp_path / "broker.json"
    path.write_text(configuration().model_dump_json())
    path.chmod(0o600)
    assert CheckpointBrokerConfig.read_private(path) == configuration()
    path.chmod(0o644)
    with pytest.raises(ValueError, match="private_broker_file_required"):
        CheckpointBrokerConfig.read_private(path)
    path.chmod(0o600)
    link = tmp_path / "link"
    link.symlink_to(path)
    with pytest.raises(OSError):
        CheckpointBrokerConfig.read_private(link)
    path.write_bytes(b"x" * 65537)
    with pytest.raises(ValueError, match="private_broker_file_required"):
        CheckpointBrokerConfig.read_private(path)


def test_builder_fixes_manual_ack_and_eager_read_committed_assignment(monkeypatch):
    constructor, admin = Mock(), Mock()
    monkeypatch.setattr(module, "Consumer", constructor)
    monkeypatch.setattr(module, "AdminClient", admin)
    build_checkpoint_client(configuration(), GROUP)
    config = constructor.call_args.args[0]
    assert config["enable.auto.commit"] is False
    assert config["enable.auto.offset.store"] is False
    assert config["auto.offset.reset"] == "error"
    assert config["partition.assignment.strategy"] == "range"
    assert config["isolation.level"] == "read_committed"
    assert config["group.id"] == GROUP
    assert config["bootstrap.servers"] == "127.0.0.1:9092"


@pytest.mark.parametrize(
    "group", ["retailops-intelligence-v2", "", "ą", "group with space", "x" * 129]
)
def test_builder_rejects_legacy_or_invalid_group(group):
    with pytest.raises(CheckpointError, match="separate_checkpoint_consumer_group_required"):
        build_checkpoint_client(configuration(), group)


def test_failed_admin_construction_closes_consumer(monkeypatch):
    client = Mock()
    monkeypatch.setattr(module, "Consumer", Mock(return_value=client))
    monkeypatch.setattr(module, "AdminClient", Mock(side_effect=RuntimeError("private")))
    with pytest.raises(RuntimeError):
        build_checkpoint_client(configuration(), GROUP)
    client.close.assert_called_once()


def test_assignment_resumes_at_store_receipt_and_checks_all_watermarks():
    instance, client, store = runner()
    instance.leases.clear()
    client.committed.return_value = [TopicPartition(TOPIC, 0, 10)]
    client.get_watermark_offsets.return_value = (5, 20)
    store.claim.return_value = PartitionLease(GROUP, 0, instance.owner, 2, 10, 12, STREAM)
    instance.assigned(client, [TopicPartition(TOPIC, 0)])
    assert store.claim.call_args.kwargs == {
        "group": GROUP,
        "partition": 0,
        "owner": instance.owner,
        "stream": STREAM,
        "low": 5,
        "high": 20,
        "committed": 10,
        "bootstrap": False,
    }
    assigned = client.assign.call_args.args[0]
    assert [(item.topic, item.partition, item.offset) for item in assigned] == [(TOPIC, 0, 12)]
    assert instance.delivery_offsets == {0: 12}


def test_commit_follows_durable_store_and_contains_exact_raw_transport():
    instance, client, store = runner()
    order = []
    store.process.side_effect = lambda *args: (
        order.append("db_committed") or {"status": "processed"}
    )
    client.commit.side_effect = lambda **kwargs: (
        order.append("broker_ack") or [TopicPartition(TOPIC, 0, 11)]
    )
    instance.handle(message())
    assert order == ["db_committed", "broker_ack"]
    record = store.process.call_args.args[1]
    assert record == TransportRecord(
        0, 10, b"fixture", b"fixture-key", (("duplicate", b"1"), ("duplicate", b"2")), 1000
    )
    assert client.commit.call_args.kwargs["asynchronous"] is False


@pytest.mark.parametrize(
    "failure", [CheckpointError("partition_fenced"), psycopg.OperationalError("db offline")]
)
def test_database_or_fencing_failure_never_acks(failure):
    instance, client, store = runner()
    store.process.side_effect = failure
    with pytest.raises(type(failure)):
        instance.handle(message())
    client.commit.assert_not_called()
    assert instance.delivery_offsets[0] == 10


@pytest.mark.parametrize("offset", [9, 11])
def test_delivery_gap_fails_before_projection_or_ack(offset):
    instance, client, store = runner()
    with pytest.raises(CheckpointError, match="partition_offset_gap"):
        instance.handle(message(offset))
    store.process.assert_not_called()
    client.commit.assert_not_called()


@pytest.mark.parametrize(
    "receipt", [None, [], [TopicPartition(TOPIC, 0, 12)], [TopicPartition(TOPIC, 1, 11)]]
)
def test_missing_or_wrong_commit_receipt_fails_stop(receipt):
    instance, client, store = runner()
    client.commit.return_value = receipt
    with pytest.raises(CheckpointError, match="broker_ack_receipt_missing"):
        instance.handle(message())
    store.process.assert_called_once()


def test_loop_stops_on_first_failure_and_closes_without_polling_later_record():
    instance, client, store = runner()
    client.poll.side_effect = [message(), message(11)]
    store.process.side_effect = CheckpointError("partition_fenced")
    with pytest.raises(CheckpointError, match="partition_fenced"):
        instance.run(max_messages=2)
    assert client.poll.call_count == 1
    client.commit.assert_not_called()
    store.release.assert_called_once()
    client.close.assert_called_once()


def test_revoke_releases_owned_epoch_and_removes_delivery_position():
    instance, client, store = runner()
    lease = instance.leases[0]
    instance.revoked(client, [TopicPartition(TOPIC, 0)])
    store.release.assert_called_once_with(lease)
    assert instance.leases == instance.delivery_offsets == {}
    client.unassign.assert_called_once()


@pytest.mark.parametrize("policy", ["compact", "delete,compact"])
def test_topology_rejects_compaction(policy):
    admin = Mock()
    admin.describe_topics.return_value = {
        TOPIC: Mock(
            result=Mock(
                return_value=SimpleNamespace(
                    topic_id="fixture-topic",
                    partitions=[SimpleNamespace(id=0)],
                )
            )
        )
    }
    admin.list_topics.return_value = SimpleNamespace(cluster_id="fixture-cluster")
    admin.describe_configs.side_effect = lambda resources, **kwargs: {
        resources[0]: Mock(
            result=Mock(return_value={"cleanup.policy": SimpleNamespace(value=policy)})
        ),
    }
    with pytest.raises(CheckpointError, match="checkpoint_requires_delete_only_topic"):
        BrokerTopology(admin).inspect()


def test_status_is_read_only_and_does_not_claim_freshness_or_liveness():
    instance, client, store = runner()
    client.committed.return_value = [TopicPartition(TOPIC, 0, 9), TopicPartition(TOPIC, 1, -1001)]
    client.get_watermark_offsets.return_value = (0, 12)
    store.states.return_value = [
        {
            "partition": 0,
            "cluster_id": STREAM.cluster_id,
            "topic_id": STREAM.topic_id,
            "coverage_start": 10,
            "next_offset": 11,
            "epoch": 2,
            "owner_id": uuid4(),
            "checkpoint_at": datetime.now(UTC),
        }
    ]
    result = instance.status()
    assert result["business_freshness"] == "not_evaluated_by_transport"
    assert result["worker_liveness"] == "not_inferred_from_owner_record"
    assert result["snapshot_handoff"] == "unsupported"
    assert result["partitions"][0]["backlog_offsets"] == 1
    assert result["partitions"][0]["owner_claimed"] is True
    assert result["partitions"][1]["initialized"] is False
    assert "owner_id" not in json.dumps(result)
    store.claim.assert_not_called()
    store.process.assert_not_called()
    client.commit.assert_not_called()


@pytest.mark.parametrize(
    "receipt", [[], [TopicPartition(TOPIC, 1, 10)], [TopicPartition(TOPIC, 0, -2)]]
)
def test_incomplete_or_invalid_broker_commit_vector_does_not_bootstrap(receipt):
    instance, client, store = runner()
    client.committed.return_value = receipt
    with pytest.raises(CheckpointError, match="broker_commit_position_unavailable"):
        instance.assigned(client, [TopicPartition(TOPIC, 0)])
    store.claim.assert_not_called()
    client.assign.assert_not_called()


def test_unknown_broker_commit_is_distinct_from_offset_zero():
    instance, client, store = runner()
    client.committed.return_value = [TopicPartition(TOPIC, 0, -1001)]
    client.get_watermark_offsets.return_value = (0, 10)
    store.claim.return_value = PartitionLease(GROUP, 0, instance.owner, 2, 0, 0, STREAM)
    instance.assigned(client, [TopicPartition(TOPIC, 0)])
    assert store.claim.call_args.kwargs["committed"] is None


def test_private_fifo_is_rejected_without_waiting_for_a_writer(tmp_path):
    import os

    path = tmp_path / "fifo"
    os.mkfifo(path, 0o600)
    with pytest.raises(ValueError, match="private_broker_file_required"):
        CheckpointBrokerConfig.read_private(path)
