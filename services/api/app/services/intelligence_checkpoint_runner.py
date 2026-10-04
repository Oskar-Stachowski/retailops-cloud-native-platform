"""Private, eager-assignment Kafka lane with durable fencing and explicit ACKs."""

from __future__ import annotations

import os
import stat
import threading
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal
from urllib.parse import urlsplit
from uuid import uuid4

from confluent_kafka import OFFSET_INVALID, Consumer, Message, TopicCollection, TopicPartition
from confluent_kafka.admin import AdminClient, ConfigResource, ResourceType
from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator

from app.services.intelligence_checkpoint import (
    CheckpointError,
    IntelligenceCheckpointStore,
    PartitionLease,
    StreamIdentity,
    TransportRecord,
)
from app.services.intelligence_contract import TOPIC

MAX_PARTITIONS = 32

if TYPE_CHECKING:
    from pathlib import Path


class CheckpointBrokerConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, hide_input_in_errors=True)
    bootstrap_servers: str = Field(min_length=1, max_length=2048)
    security_protocol: Literal["SSL", "SASL_SSL", "PLAINTEXT"] = "SASL_SSL"
    sasl_mechanism: Literal["SCRAM-SHA-256", "SCRAM-SHA-512", "PLAIN"] = "SCRAM-SHA-256"
    username: SecretStr | None = None
    password: SecretStr | None = None
    ca_file: str | None = None
    allow_plaintext_loopback: bool = False

    @model_validator(mode="after")
    def validate_broker(self) -> CheckpointBrokerConfig:
        endpoints = self.bootstrap_servers.split(",")
        if len(endpoints) > 8:
            msg = "broker_endpoint_limit"
            raise ValueError(msg)
        loopback = True
        for endpoint in endpoints:
            url = urlsplit("//" + endpoint)
            if (
                not url.hostname
                or not url.port
                or url.username
                or url.password
                or url.path
                or url.query
                or url.fragment
            ):
                msg = "explicit_broker_host_and_port_required"
                raise ValueError(msg)
            loopback = loopback and url.hostname in ("127.0.0.1", "::1", "localhost")
        if self.security_protocol == "PLAINTEXT" and not (
            self.allow_plaintext_loopback and loopback
        ):
            msg = "verified_private_broker_tls_required"
            raise ValueError(msg)
        if self.security_protocol == "SASL_SSL" and (
            self.username is None or self.password is None
        ):
            msg = "private_broker_credentials_required"
            raise ValueError(msg)
        if self.security_protocol != "SASL_SSL" and (
            self.username is not None or self.password is not None
        ):
            msg = "broker_credentials_require_sasl_tls"
            raise ValueError(msg)
        return self

    def backend(self) -> dict[str, Any]:
        values: dict[str, Any] = {
            "bootstrap.servers": self.bootstrap_servers,
            "security.protocol": self.security_protocol,
            "log_level": 0,
        }
        if self.security_protocol == "SASL_SSL":
            if self.username is None or self.password is None:
                msg = "private_broker_credentials_required"
                raise ValueError(msg)
            values.update(
                {
                    "sasl.mechanism": self.sasl_mechanism,
                    "sasl.username": self.username.get_secret_value(),
                    "sasl.password": self.password.get_secret_value(),
                }
            )
        if self.ca_file is not None:
            values["ssl.ca.location"] = self.ca_file
        return values

    @classmethod
    def read_private(cls, path: Path) -> CheckpointBrokerConfig:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            info = os.fstat(descriptor)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o600
                or info.st_size > 65536
            ):
                msg = "private_broker_file_required"
                raise ValueError(msg)
            raw = os.read(descriptor, 65537)
            if len(raw) > 65536:
                msg = "private_broker_file_limit"
                raise ValueError(msg)
            return cls.model_validate_json(raw)
        finally:
            os.close(descriptor)


class BrokerTopology:
    def __init__(self, admin: AdminClient) -> None:
        self.admin = admin

    def inspect(self) -> tuple[StreamIdentity, tuple[int, ...]]:
        # list_topics() exposes a cached cluster ID and may return None even
        # after a successful metadata request. DescribeCluster awaits its ID.
        cluster = self.admin.describe_cluster(request_timeout=5).result(timeout=6)
        # Await cluster discovery before describing topics. A fresh client can
        # otherwise use initial metadata without topic UUIDs during negotiation.
        description = self.admin.describe_topics(TopicCollection([TOPIC]), request_timeout=5)[
            TOPIC
        ].result(timeout=6)
        resource = ConfigResource(ResourceType.TOPIC, TOPIC)
        configuration = self.admin.describe_configs([resource], request_timeout=5)[resource].result(
            timeout=6
        )
        policy = configuration.get("cleanup.policy")
        if policy is None or policy.value != "delete":
            msg = "checkpoint_requires_delete_only_topic"
            raise CheckpointError(msg)
        partitions = tuple(sorted(partition.id for partition in description.partitions))
        if (
            not partitions
            or len(partitions) > MAX_PARTITIONS
            or partitions != tuple(range(len(partitions)))
        ):
            msg = "checkpoint_partition_limit"
            raise CheckpointError(msg)
        if cluster.cluster_id is None or description.topic_id is None:
            msg = "broker_stream_identity_unavailable"
            raise CheckpointError(msg)
        return StreamIdentity(str(cluster.cluster_id), str(description.topic_id)), partitions


def broker_commits(client: Consumer, partitions: list[TopicPartition]) -> dict[int, int | None]:
    expected = {item.partition for item in partitions}
    received = client.committed(partitions, timeout=5)
    if (
        len(received) != len(expected)
        or {item.partition for item in received} != expected
        or any(
            item.topic != TOPIC
            or item.error is not None
            or (item.offset < 0 and item.offset != OFFSET_INVALID)
            for item in received
        )
    ):
        msg = "broker_commit_position_unavailable"
        raise CheckpointError(msg)
    return {
        item.partition: item.offset if item.offset != OFFSET_INVALID else None for item in received
    }


def build_checkpoint_client(
    config: CheckpointBrokerConfig, group: str
) -> tuple[Consumer, BrokerTopology]:
    if (
        not group
        or group == "retailops-intelligence-v2"
        or len(group) > 128
        or not all(
            character.isascii() and (character.isalnum() or character in "._:-")
            for character in group
        )
    ):
        msg = "separate_checkpoint_consumer_group_required"
        raise CheckpointError(msg)
    values = config.backend()
    client = Consumer(
        {
            **values,
            "group.id": group,
            "client.id": "retailops-intelligence-checkpointed",
            "enable.auto.commit": False,
            "enable.auto.offset.store": False,
            "auto.offset.reset": "error",
            "enable.partition.eof": False,
            "partition.assignment.strategy": "range",
            "isolation.level": "read_committed",
            "session.timeout.ms": 10000,
            "heartbeat.interval.ms": 3000,
        }
    )
    try:
        return client, BrokerTopology(AdminClient(values))
    except Exception:
        client.close()
        raise


class IntelligenceCheckpointRunner:
    def __init__(
        self,
        *,
        kafka_consumer: Consumer,
        topology: BrokerTopology,
        group: str,
        store: IntelligenceCheckpointStore | None = None,
        bootstrap: bool = False,
    ) -> None:
        self.client = kafka_consumer
        self.topology = topology
        self.group = group
        self.store = store or IntelligenceCheckpointStore()
        self.bootstrap = bootstrap
        self.owner = uuid4()
        self.leases: dict[int, PartitionLease] = {}
        self.delivery_offsets: dict[int, int] = {}

    def assigned(self, client: Consumer, partitions: list[TopicPartition]) -> None:
        stream, allowed = self.topology.inspect()
        if any(
            partition.topic != TOPIC or partition.partition not in allowed
            for partition in partitions
        ):
            msg = "unexpected_partition_assignment"
            raise CheckpointError(msg)
        committed = broker_commits(client, partitions)
        assigned = []
        for partition in partitions:
            low, high = client.get_watermark_offsets(partition, timeout=5, cached=False)
            offset = committed.get(partition.partition)
            lease = self.store.claim(
                group=self.group,
                partition=partition.partition,
                owner=self.owner,
                stream=stream,
                low=low,
                high=high,
                committed=offset,
                bootstrap=self.bootstrap,
            )
            self.leases[partition.partition] = lease
            self.delivery_offsets[partition.partition] = lease.resume_offset
            assigned.append(TopicPartition(TOPIC, partition.partition, lease.resume_offset))
        client.assign(assigned)

    def revoked(self, client: Consumer, partitions: list[TopicPartition]) -> None:
        for partition in partitions:
            lease = self.leases.pop(partition.partition, None)
            self.delivery_offsets.pop(partition.partition, None)
            if lease is not None:
                self.store.release(lease)
        client.unassign()

    def handle(self, message: Message) -> dict[str, Any]:
        partition = message.partition()
        offset = message.offset()
        if partition is None or offset is None:
            msg = "invalid_transport_position"
            raise CheckpointError(msg)
        lease = self.leases.get(partition)
        if message.topic() != TOPIC or lease is None:
            msg = "partition_not_owned"
            raise CheckpointError(msg)
        if offset != self.delivery_offsets[partition]:
            # Dense non-transactional v2 is the supported lane. Even an offset
            # gap caused by broker control records fails closed without an ACK.
            msg = "partition_offset_gap"
            raise CheckpointError(msg)
        timestamp = message.timestamp()[1]
        raw_headers = message.headers()
        if isinstance(raw_headers, dict):
            msg = "invalid_transport_headers"
            raise CheckpointError(msg)
        headers: list[tuple[str, bytes | None]] = []
        for key, value in raw_headers or ():
            if value is not None and not isinstance(value, bytes):
                msg = "invalid_transport_headers"
                raise CheckpointError(msg)
            headers.append((key, value))
        record = TransportRecord(
            partition,
            offset,
            message.value(),
            message.key(),
            tuple(headers),
            timestamp if timestamp >= 0 else None,
        )
        result = self.store.process(lease, record)
        self.delivery_offsets[partition] = record.offset + 1
        offsets = self.client.commit(message=message, asynchronous=False)
        if (
            not offsets
            or len(offsets) != 1
            or offsets[0].error is not None
            or offsets[0].topic != TOPIC
            or offsets[0].partition != partition
            or offsets[0].offset != record.offset + 1
        ):
            msg = "broker_ack_receipt_missing"
            raise CheckpointError(msg)
        return result

    def run(
        self, *, stop_event: threading.Event | None = None, max_messages: int | None = None
    ) -> int:
        stop_event = stop_event or threading.Event()
        count = 0
        try:
            self.client.subscribe(
                [TOPIC], on_assign=self.assigned, on_revoke=self.revoked, on_lost=self.revoked
            )
            while not stop_event.is_set():
                message = self.client.poll(0.25)
                if message is None:
                    continue
                if message.error() is not None:
                    msg = "intelligence_broker_poll_failed"
                    raise CheckpointError(msg)
                self.handle(message)
                count += 1
                if max_messages is not None and count >= max_messages:
                    break
        finally:
            try:
                for lease in self.leases.values():
                    self.store.release(lease)
            finally:
                self.leases.clear()
                self.delivery_offsets.clear()
                self.client.close()
        return count

    def status(self) -> dict[str, Any]:
        """Operator-only metadata, never an assertion of business freshness."""
        stream, partitions = self.topology.inspect()
        states = {row["partition"]: row for row in self.store.states(self.group)}
        if len(states) > MAX_PARTITIONS or set(states) - set(partitions):
            msg = "checkpoint_partition_layout_changed"
            raise CheckpointError(msg)
        committed = broker_commits(
            self.client, [TopicPartition(TOPIC, partition) for partition in partitions]
        )
        rows = []
        now = datetime.now(UTC)
        for partition in partitions:
            low, high = self.client.get_watermark_offsets(
                TopicPartition(TOPIC, partition), timeout=5, cached=False
            )
            state = states.get(partition)
            row: dict[str, Any] = {
                "partition": partition,
                "log_low": low,
                "log_high": high,
                "broker_committed": committed.get(partition),
                "initialized": state is not None,
            }
            if state is not None:
                stamp = state["checkpoint_at"]
                row.update(
                    coverage_start=state["coverage_start"],
                    next_offset=state["next_offset"],
                    epoch=state["epoch"],
                    owner_claimed=state["owner_id"] is not None,
                    checkpoint_age_seconds=(now - stamp).total_seconds()
                    if stamp is not None
                    else None,
                    backlog_offsets=max(0, high - state["next_offset"]),
                    retention_gap=low > state["next_offset"],
                    broker_log_rewound=high < state["next_offset"],
                    stream_changed=(state["cluster_id"], state["topic_id"])
                    != (stream.cluster_id, stream.topic_id),
                    broker_checkpoint_ahead=(committed.get(partition) or 0) > state["next_offset"],
                )
            rows.append(row)
        return {
            "consumer_group": self.group,
            "topic": TOPIC,
            "coverage": "since_explicit_partition_bootstrap",
            "snapshot_handoff": "unsupported",
            "business_freshness": "not_evaluated_by_transport",
            "worker_liveness": "not_inferred_from_owner_record",
            "partitions": rows,
        }
