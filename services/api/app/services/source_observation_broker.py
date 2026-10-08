"""Private TLS/SCRAM producer configuration and real topic identity discovery."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator

from app.services.source_observation_outbox import ObservationError, private_bytes
from app.services.source_observation_wire import Stream, UUIDText

TOPIC = "retailops.source-observations.v1"


class BrokerConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, hide_input_in_errors=True)
    source_authority_id: UUIDText
    bootstrap_servers: str = Field(min_length=1, max_length=2048, repr=False)
    security_protocol: Literal["SASL_SSL"] = "SASL_SSL"
    sasl_mechanism: Literal["SCRAM-SHA-256", "SCRAM-SHA-512"] = "SCRAM-SHA-256"
    username: SecretStr = Field(repr=False)
    password: SecretStr = Field(repr=False)
    ca_file: str = Field(min_length=1, max_length=4096, repr=False)

    @model_validator(mode="after")
    def endpoints(self) -> BrokerConfig:
        endpoints = self.bootstrap_servers.split(",")
        if len(endpoints) > 8:
            msg = "observation_broker_endpoint_limit"
            raise ValueError(msg)
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
                or endpoint != endpoint.strip()
            ):
                msg = "observation_broker_endpoint_invalid"
                raise ValueError(msg)
        if not self.username.get_secret_value() or not self.password.get_secret_value():
            msg = "observation_broker_credentials_required"
            raise ValueError(msg)
        if not Path(self.ca_file).is_absolute():
            msg = "observation_broker_absolute_ca_required"
            raise ValueError(msg)
        return self

    def backend(self) -> dict[str, Any]:
        return {
            "bootstrap.servers": self.bootstrap_servers,
            "security.protocol": self.security_protocol,
            "sasl.mechanism": self.sasl_mechanism,
            "sasl.username": self.username.get_secret_value(),
            "sasl.password": self.password.get_secret_value(),
            "ssl.ca.location": self.ca_file,
            "enable.ssl.certificate.verification": True,
            "ssl.endpoint.identification.algorithm": "https",
            "allow.auto.create.topics": False,
            "log_level": 0,
        }

    @classmethod
    def read_private(cls, path: Path) -> BrokerConfig:
        try:
            return cls.model_validate_json(private_bytes(path, limit=16384))
        except Exception:  # noqa: BLE001 - native authentication errors can contain private endpoint data
            msg = "observation_private_broker_config_invalid"
            raise ObservationError(msg) from None


class BrokerTopology:
    def __init__(self, admin: Any, authority: str) -> None:  # noqa: ANN401 - native client lacks typed metadata
        self.admin = admin
        self.authority = authority

    def inspect(self) -> tuple[Stream, int]:
        # Cluster discovery must complete before DescribeTopics negotiates IDs.
        native = import_module("confluent_kafka")
        admin_module = import_module("confluent_kafka.admin")
        try:
            cluster = self.admin.describe_cluster(request_timeout=5).result(timeout=6)
            description = self.admin.describe_topics(
                native.TopicCollection([TOPIC]), request_timeout=5
            )[TOPIC].result(timeout=6)
            resource = admin_module.ConfigResource(admin_module.ResourceType.TOPIC, TOPIC)
            configuration = self.admin.describe_configs([resource], request_timeout=5)[
                resource
            ].result(timeout=6)
            policy = configuration.get("cleanup.policy")
            if policy is None or policy.value != "delete":
                msg = "observation_delete_only_topic_required"
                raise ObservationError(msg)
            partitions = sorted(item.id for item in description.partitions)
            if (
                description.name != TOPIC
                or description.is_internal
                or not 1 <= len(partitions) <= 32
                or partitions != list(range(len(partitions)))
                or any(item.leader is None for item in description.partitions)
            ):
                msg = "observation_broker_topology_invalid"
                raise ObservationError(msg)
            if cluster.cluster_id is None or description.topic_id is None:
                msg = "observation_broker_identity_missing"
                raise ObservationError(msg)
            stream = Stream(
                source_authority_id=self.authority,
                cluster_id=str(cluster.cluster_id),
                topic_id=str(description.topic_id),
            )
            return stream, len(partitions)
        except ObservationError:
            raise
        except Exception:  # noqa: BLE001 - native authentication errors can contain private endpoint data
            msg = "observation_broker_topology_unavailable"
            raise ObservationError(msg) from None


def build_producer(config: BrokerConfig) -> tuple[Any, BrokerTopology]:
    native = import_module("confluent_kafka")
    admin = import_module("confluent_kafka.admin")
    common = config.backend()
    producer = native.Producer(
        {
            **common,
            "enable.idempotence": True,
            "acks": "all",
            "delivery.timeout.ms": 10000,
            "request.timeout.ms": 3000,
            "socket.timeout.ms": 3000,
            "queue.buffering.max.messages": 1,
            "max.in.flight.requests.per.connection": 1,
        }
    )
    return producer, BrokerTopology(admin.AdminClient(common), config.source_authority_id)
