"""Actual PostgreSQL and TLS/SCRAM broker proof of the Source-owned observation producer."""

import importlib.util
import json
import os
import shutil
import socket
import ssl
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.error import URLError
from urllib.request import HTTPSHandler, ProxyHandler, Request, build_opener
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text

from app.services.source_observation_broker import BrokerConfig, TOPIC, build_producer
from app.services.source_observation_outbox import (
    ObservationOutbox,
    ObservationPublisher,
)
from app.services.source_observation_wire import Stream

ROOT = Path(__file__).resolve().parents[3]
POSTGRES = "postgres:16-alpine@sha256:721873c34ceb9f8d8fc265984940dc982404c105f19ad51be9fdc5970a6080ea"
REDPANDA = "redpandadata/redpanda:v25.3.6@sha256:ac152ec27adccf9482af2649d293f398eb03c860d7469fc49f86e30d870ea408"
STREAM = Stream(
    source_authority_id="d8006c2a-7976-485a-9d6e-fb5335a41091",
    cluster_id="fixture",
    topic_id="fixture",
)


def command(args, *, input=None, timeout=90):
    try:
        return subprocess.run(
            args, input=input, capture_output=True, check=True, timeout=timeout
        ).stdout
    except (subprocess.SubprocessError, OSError):
        raise RuntimeError("source_observation_runtime_command_failed") from None


def private_file(path, data):
    path.write_bytes(data if isinstance(data, bytes) else data.encode())
    path.chmod(0o600)


def port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@dataclass(repr=False)
class Runtime:
    engine: object
    config: BrokerConfig
    admin: object
    native: object
    producer_config: dict
    private: Path
    passwords: dict
    container: str
    checks: list[str] = field(default_factory=list)

    def __repr__(self):
        return "<isolated Source observation runtime>"

    def passed(self, name):
        assert name not in self.checks
        self.checks.append(name)


@pytest.fixture(scope="module")
def publisher_runtime(tmp_path_factory):
    if os.getenv("REQUIRE_BROKER_TESTS") != "1":
        pytest.skip("Mandatory remote gate owns PostgreSQL and TLS/SCRAM Redpanda")
    docker = shutil.which("docker")
    if not docker:
        pytest.fail("Docker required for mandatory observation broker acceptance")
    native = importlib.import_module("confluent_kafka")
    admin_module = importlib.import_module("confluent_kafka.admin")
    private = tmp_path_factory.mktemp("ai10-observation-private")
    private.chmod(0o700)
    for directory in ("broker", "data"):
        (private / directory).mkdir(mode=0o700)
    names = [
        "ai10-observation-pg-" + uuid4().hex[:12],
        "ai10-observation-broker-" + uuid4().hex[:12],
    ]
    passwords = {
        key: uuid4().hex + uuid4().hex
        for key in ("database", "admin", "producer", "reader")
    }
    db_port, kafka_port, admin_port = port(), port(), port()
    engine, rt = None, None
    try:
        for name in ("trusted", "untrusted"):
            command(
                ["openssl", "genrsa", "-out", str(private / (name + ".key")), "2048"]
            )
            command(
                [
                    "openssl",
                    "req",
                    "-x509",
                    "-days",
                    "2",
                    "-subj",
                    "/CN=AI10-" + name,
                    "-key",
                    str(private / (name + ".key")),
                    "-out",
                    str(private / (name + ".crt")),
                ]
            )
        command(
            ["openssl", "genrsa", "-out", str(private / "broker/broker.key"), "2048"]
        )
        command(
            [
                "openssl",
                "req",
                "-new",
                "-subj",
                "/CN=localhost",
                "-key",
                str(private / "broker/broker.key"),
                "-out",
                str(private / "broker.csr"),
            ]
        )
        private_file(
            private / "extensions",
            "subjectAltName=IP:127.0.0.1,DNS:localhost\nextendedKeyUsage=serverAuth\n",
        )
        command(
            [
                "openssl",
                "x509",
                "-req",
                "-days",
                "2",
                "-in",
                str(private / "broker.csr"),
                "-CA",
                str(private / "trusted.crt"),
                "-CAkey",
                str(private / "trusted.key"),
                "-CAcreateserial",
                "-extfile",
                str(private / "extensions"),
                "-out",
                str(private / "broker/broker.crt"),
            ]
        )
        private_file(private / "broker/ca.crt", (private / "trusted.crt").read_bytes())
        (private / "broker/broker.key").chmod(0o600)
        private_file(
            private / "broker.env",
            "RP_BOOTSTRAP_USER=bootstrap:" + passwords["admin"] + "\n",
        )
        private_file(
            private / "broker/.bootstrap.yaml",
            "enable_sasl: true\nadmin_api_require_auth: true\nhttp_authentication: [BASIC]\nsuperusers: [bootstrap]\nauto_create_topics_enabled: false\nsasl_mechanisms: [SCRAM]\n",
        )
        private_file(
            private / "broker/redpanda.yaml",
            f"""redpanda:
  data_directory: /var/lib/redpanda/data
  node_id: 0
  seed_servers: []
  rpc_server: {{address: 0.0.0.0, port: 33145}}
  advertised_rpc_api: {{address: 127.0.0.1, port: 33145}}
  kafka_api: [{{address: 0.0.0.0, port: 9092, name: secure}}]
  advertised_kafka_api: [{{address: 127.0.0.1, port: {kafka_port}, name: secure}}]
  kafka_api_tls:
    - {{name: secure, enabled: true, require_client_auth: false, key_file: /private/broker.key, cert_file: /private/broker.crt, truststore_file: /private/ca.crt}}
  admin: [{{address: 0.0.0.0, port: 9644, name: secure-admin}}]
  admin_api_tls:
    - {{name: secure-admin, enabled: true, require_client_auth: false, key_file: /private/broker.key, cert_file: /private/broker.crt, truststore_file: /private/ca.crt}}
""",
        )
        private_file(
            private / "database.env",
            f"POSTGRES_USER=ai10\nPOSTGRES_DB=ai10\nPOSTGRES_PASSWORD={passwords['database']}\nPOSTGRES_HOST_AUTH_METHOD=scram-sha-256\n",
        )
        command(
            [
                docker,
                "run",
                "-d",
                "--name",
                names[0],
                "--cpus",
                "1",
                "--memory",
                "512m",
                "--env-file",
                str(private / "database.env"),
                "-p",
                f"127.0.0.1:{db_port}:5432",
                POSTGRES,
            ]
        )
        command(
            [
                docker,
                "run",
                "-d",
                "--name",
                names[1],
                "--user",
                f"{os.getuid()}:{os.getgid()}",
                "--cpus",
                "1",
                "--memory",
                "768m",
                "--env-file",
                str(private / "broker.env"),
                "-p",
                f"127.0.0.1:{kafka_port}:9092",
                "-p",
                f"127.0.0.1:{admin_port}:9644",
                "-v",
                f"{private / 'broker'}:/private:rw",
                "-v",
                f"{private / 'data'}:/var/lib/redpanda/data",
                REDPANDA,
                "redpanda",
                "start",
                "--config",
                "/private/redpanda.yaml",
                "--mode",
                "dev-container",
                "--smp",
                "1",
                "--memory",
                "512M",
                "--reserve-memory",
                "0M",
                "--overprovisioned",
                "--check=false",
            ]
        )
        engine = create_engine(
            f"postgresql+psycopg://ai10:{passwords['database']}@127.0.0.1:{db_port}/ai10",
            hide_parameters=True,
            connect_args={"connect_timeout": 2},
        )
        deadline = time.monotonic() + 60
        while True:
            try:
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                break
            except Exception:
                assert time.monotonic() < deadline, "isolated PostgreSQL unavailable"
                time.sleep(0.2)
        with engine.begin() as conn:
            revision = (
                ROOT
                / "services/api/alembic/versions/a10f0c7e0500_add_source_observation_outbox.py"
            )
            spec = importlib.util.spec_from_file_location(
                "source_outbox_migration", revision
            )
            migration = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(migration)
            with Operations.context(MigrationContext.configure(conn)):
                migration.upgrade()
        opener = build_opener(
            ProxyHandler({}),
            HTTPSHandler(
                context=ssl.create_default_context(cafile=str(private / "trusted.crt"))
            ),
        )
        import base64

        auth = base64.b64encode(("bootstrap:" + passwords["admin"]).encode()).decode()
        request = Request(
            f"https://127.0.0.1:{admin_port}/v1/status/ready",
            headers={"Authorization": "Basic " + auth},
        )
        deadline = time.monotonic() + 90
        while True:
            try:
                with opener.open(request, timeout=3) as response:
                    if response.status == 200:
                        break
            except (URLError, OSError):
                pass
            assert time.monotonic() < deadline, "isolated TLS/SCRAM broker unavailable"
            time.sleep(0.5)
        common = {
            "bootstrap.servers": f"127.0.0.1:{kafka_port}",
            "security.protocol": "SASL_SSL",
            "sasl.mechanism": "SCRAM-SHA-256",
            "ssl.ca.location": str(private / "trusted.crt"),
            "enable.ssl.certificate.verification": True,
            "ssl.endpoint.identification.algorithm": "https",
            "log_level": 0,
            "allow.auto.create.topics": False,
        }
        admin = admin_module.AdminClient(
            {
                **common,
                "sasl.username": "bootstrap",
                "sasl.password": passwords["admin"],
            }
        )
        for future in admin.alter_user_scram_credentials(
            [
                admin_module.UserScramCredentialUpsertion(
                    name,
                    admin_module.ScramCredentialInfo(
                        admin_module.ScramMechanism.SCRAM_SHA_256, 4096
                    ),
                    passwords[name].encode(),
                )
                for name in ("producer", "reader")
            ],
            request_timeout=10,
        ).values():
            future.result(timeout=12)
        for future in admin.create_topics(
            [
                admin_module.NewTopic(
                    TOPIC,
                    num_partitions=3,
                    replication_factor=1,
                    config={"cleanup.policy": "delete"},
                ),
                admin_module.NewTopic(
                    "foreign-topic", num_partitions=1, replication_factor=1
                ),
            ],
            request_timeout=10,
        ).values():
            future.result(timeout=12)
        grants = [
            (
                "producer",
                admin_module.ResourceType.TOPIC,
                TOPIC,
                admin_module.ResourcePatternType.LITERAL,
                [
                    admin_module.AclOperation.WRITE,
                    admin_module.AclOperation.DESCRIBE,
                    admin_module.AclOperation.DESCRIBE_CONFIGS,
                ],
            ),
            (
                "reader",
                admin_module.ResourceType.TOPIC,
                TOPIC,
                admin_module.ResourcePatternType.LITERAL,
                [
                    admin_module.AclOperation.READ,
                    admin_module.AclOperation.DESCRIBE,
                    admin_module.AclOperation.DESCRIBE_CONFIGS,
                ],
            ),
            (
                "reader",
                admin_module.ResourceType.GROUP,
                "ai10-observation-",
                admin_module.ResourcePatternType.PREFIXED,
                [admin_module.AclOperation.READ, admin_module.AclOperation.DESCRIBE],
            ),
            (
                "reader",
                admin_module.ResourceType.BROKER,
                "kafka-cluster",
                admin_module.ResourcePatternType.LITERAL,
                [admin_module.AclOperation.DESCRIBE],
            ),
        ]
        grants.append(
            (
                "producer",
                admin_module.ResourceType.BROKER,
                "kafka-cluster",
                admin_module.ResourcePatternType.LITERAL,
                [
                    admin_module.AclOperation.DESCRIBE,
                    admin_module.AclOperation.IDEMPOTENT_WRITE,
                ],
            )
        )
        bindings = [
            admin_module.AclBinding(
                kind,
                resource,
                pattern,
                "User:" + principal,
                "*",
                operation,
                admin_module.AclPermissionType.ALLOW,
            )
            for principal, kind, resource, pattern, operations in grants
            for operation in operations
        ]
        for future in admin.create_acls(bindings, request_timeout=10).values():
            future.result(timeout=12)
        config = BrokerConfig.model_validate_json(
            json.dumps(
                dict(
                    source_authority_id=STREAM.source_authority_id,
                    bootstrap_servers=common["bootstrap.servers"],
                    username="producer",
                    password=passwords["producer"],
                    ca_file=common["ssl.ca.location"],
                )
            )
        )
        producer_config = {
            **common,
            "sasl.username": "producer",
            "sasl.password": passwords["producer"],
            "enable.idempotence": False,
            "acks": "all",
            "delivery.timeout.ms": 10000,
        }
        rt = Runtime(
            engine, config, admin, native, producer_config, private, passwords, names[0]
        )
        yield rt
    finally:
        if rt is not None:
            target = os.getenv("SOURCE_OBSERVATION_OUTBOX_REPORT")
            if target:
                report = {
                    "status": "passed" if len(rt.checks) == 12 else "incomplete",
                    "actual_source_sql_outbox_and_broker_publication": True,
                    "broker": REDPANDA,
                    "database": POSTGRES,
                    "tls_hostname_verified": True,
                    "sasl": "SCRAM-SHA-256",
                    "checks": sorted(rt.checks),
                    "source_authority": "explicit acceptance fixture; source-owned operational publisher executed",
                    "source_live_capture_supported": False,
                    "full_43_table_handoff": False,
                    "models_qualified": False,
                }
                path = Path(target)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        if engine is not None:
            engine.dispose()
        for name in names:
            subprocess.run([docker, "rm", "-fv", name], capture_output=True, timeout=45)
        shutil.rmtree(private)
        if rt is not None and len(rt.checks) != 12:
            pytest.fail(
                "Mandatory broker acceptance did not complete every runtime check"
            )


def fetch(runner, partition=0):
    runner.assigned(runner.client, [runner._partition(partition)])
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        message = runner.client.poll(0.25)
        if message is not None:
            assert message.error() is None
            return message
    pytest.fail("actual broker message unavailable")


def close(runner):
    try:
        for lease in runner.leases.values():
            runner.store.release(lease)
    finally:
        runner.client.close()
