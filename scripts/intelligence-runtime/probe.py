# ruff: noqa: INP001, EM101, FBT001, PLR0912, PLR0915, SLF001
"""Mandatory real-runtime assertions. No mocks, skips, production approvals or ML claims."""

from __future__ import annotations

import base64
import hashlib
import json
import ssl
import sys
import time
from pathlib import Path
from typing import Self
from urllib.error import HTTPError, URLError
from urllib.request import HTTPSHandler, ProxyHandler, Request, build_opener

import psycopg
from confluent_kafka import (
    Consumer,
    KafkaError,
    KafkaException,
    Producer,
    TopicCollection,
    TopicPartition,
)
from confluent_kafka.admin import (
    AclBinding,
    AclOperation,
    AclPermissionType,
    AdminClient,
    NewTopic,
    ResourcePatternType,
    ResourceType,
    ScramCredentialInfo,
    ScramMechanism,
    UserScramCredentialUpsertion,
)
from psycopg import sql
from psycopg.rows import dict_row

TOPIC = "retailops.intelligence.v2"
GROUP = "retailops-intelligence-v2-checkpointed"
CONFIG = Path("/private/config.json")


class HttpResponse:
    def __init__(self, status: int, body: bytes) -> None:
        self.status_code = status
        self.body = body

    def json(self) -> dict:
        return json.loads(self.body)


class HttpClient:
    """Use only the production image's standard library; never inherit proxies."""

    def __init__(self, *, base_url: str = "", verify: str | None = None, timeout: int = 3) -> None:
        self.base_url = base_url
        self.timeout = timeout
        self.opener = build_opener(
            ProxyHandler({}), HTTPSHandler(context=ssl.create_default_context(cafile=verify))
        )

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_args: object) -> None:
        pass

    def get(
        self, url: str, *, headers: dict | None = None, auth: tuple | None = None
    ) -> HttpResponse:
        values = dict(headers or {})
        if auth is not None:
            values["Authorization"] = (
                "Basic " + base64.b64encode((auth[0] + ":" + auth[1]).encode()).decode()
            )
        request = Request(self.base_url + url, headers=values)  # noqa: S310 - fixed private HTTP(S) endpoints
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                return HttpResponse(response.status, response.read(65537))
        except HTTPError as exc:
            return HttpResponse(exc.code, exc.read(65537))


class ProbeError(RuntimeError):
    """Fixed, credential-free acceptance failure."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ProbeError(code)


def db(config: dict, role: str) -> psycopg.Connection:
    return psycopg.connect(config["database"][role], connect_timeout=3, row_factory=dict_row)


def bootstrap(config: dict) -> dict:
    with HttpClient(verify="/private/ca.crt", timeout=3) as http:
        deadline = time.monotonic() + 90
        while True:
            try:
                response = http.get(
                    "https://broker:9644/v1/status/ready",
                    auth=("bootstrap", config["passwords"]["admin"]),
                )
                if response.status_code == 200:
                    break
            except (URLError, OSError):
                pass
            require(time.monotonic() < deadline, "broker_tls_admin_not_ready")
            time.sleep(1)
        require(
            http.get("https://broker:9644/v1/security/users").status_code == 401,
            "admin_anonymous_denied",
        )
    admin = AdminClient(config["broker"]["admin"])
    credentials = [
        UserScramCredentialUpsertion(
            config["broker"][name]["sasl.username"],
            ScramCredentialInfo(ScramMechanism.SCRAM_SHA_256, 4096),
            config["passwords"][name].encode(),
        )
        for name in ("ai", "source")
    ]
    for future in admin.alter_user_scram_credentials(credentials, request_timeout=10).values():
        future.result(timeout=12)
    for future in admin.create_topics(
        [
            NewTopic(
                TOPIC, num_partitions=3, replication_factor=1, config={"cleanup.policy": "delete"}
            ),
            NewTopic("foreign-topic", num_partitions=1, replication_factor=1),
        ],
        request_timeout=10,
    ).values():
        future.result(timeout=12)
    bindings = []
    grants = (
        ("ai-producer", ResourceType.TOPIC, TOPIC, (AclOperation.WRITE, AclOperation.DESCRIBE)),
        ("ai-producer", ResourceType.CLUSTER, "kafka-cluster", (AclOperation.IDEMPOTENT_WRITE,)),
        (
            "source-consumer",
            ResourceType.TOPIC,
            TOPIC,
            (AclOperation.READ, AclOperation.DESCRIBE, AclOperation.DESCRIBE_CONFIGS),
        ),
        ("source-consumer", ResourceType.GROUP, GROUP, (AclOperation.READ, AclOperation.DESCRIBE)),
        ("source-consumer", ResourceType.CLUSTER, "kafka-cluster", (AclOperation.DESCRIBE,)),
    )
    for principal, resource, name, operations in grants:
        for operation in operations:
            bindings.append(
                AclBinding(
                    resource,
                    name,
                    ResourcePatternType.LITERAL,
                    "User:" + principal,
                    "*",
                    operation,
                    AclPermissionType.ALLOW,
                )
            )
    for future in admin.create_acls(bindings, request_timeout=10).values():
        future.result(timeout=12)
    for lane in ("ai", "source"):
        with db(config, lane + "_admin") as connection:
            connection.execute(
                sql.SQL("REVOKE CONNECT ON DATABASE {} FROM PUBLIC").format(
                    sql.Identifier(lane + "_data")
                )
            )
            connection.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
            roles = [(lane + "_worker", config["passwords"][lane])]
            if lane == "source":
                roles.append(("source_reader", config["passwords"]["source_reader"]))
            for role, password in roles:
                connection.execute(
                    sql.SQL(
                        "CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD {}"
                    ).format(sql.Identifier(role), sql.Literal(password))
                )
                connection.execute(
                    sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                        sql.Identifier(lane + "_data"), sql.Identifier(role)
                    )
                )
    return {"status": "bootstrapped", "literal_acl_count": len(bindings), "topic_partitions": 3}


def grant(config: dict) -> dict:
    with db(config, "source_admin") as connection:
        connection.execute(
            "GRANT SELECT ON ai_forecast_results,ai_intelligence_inbox TO source_reader"
        )
        connection.execute(
            "GRANT SELECT,INSERT,UPDATE ON ai_forecast_results,ai_intelligence_inbox,ai_intelligence_partitions,ai_intelligence_transport,realtime_event_log TO source_worker"
        )
    return {"status": "scoped_tables_granted"}


def kafka_error(exception: KafkaException) -> int:
    return exception.args[0].code()


def expect_kafka(action: object, code: int, name: str) -> None:
    try:
        action()  # type: ignore[operator]
    except KafkaException as exc:
        require(kafka_error(exc) == code, name + "_unexpected_error")
    else:
        raise ProbeError(name + "_unexpected_success")


def negative_auth(config: dict) -> list[str]:
    checks = []
    # An authenticated consumer has metadata/read permission, so a Produce denial
    # is a broker authorization error, never an ambiguous metadata timeout.
    receipts = []
    producer = Producer({**config["broker"]["source"], "delivery.timeout.ms": 5000})
    producer.produce(
        TOPIC, b"forbidden", partition=0, on_delivery=lambda error, _message: receipts.append(error)
    )
    require(
        producer.flush(8) == 0
        and len(receipts) == 1
        and receipts[0] is not None
        and receipts[0].code() == KafkaError.TOPIC_AUTHORIZATION_FAILED,
        "consumer_write_denied",
    )
    checks.append("consumer_write_topic_authorization_failed")
    # Producer can Describe this topic, but manual Fetch cannot use its Write ACL.
    client = Consumer(
        {
            **config["broker"]["ai"],
            "group.id": "forbidden-producer-group",
            "enable.auto.commit": False,
        }
    )
    try:
        client.assign([TopicPartition(TOPIC, 0, 0)])
        deadline = time.monotonic() + 10
        while True:
            message = client.poll(1)
            if message is not None:
                require(
                    message.error() is not None
                    and message.error().code() == KafkaError.TOPIC_AUTHORIZATION_FAILED,
                    "producer_fetch_denied",
                )
                break
            require(time.monotonic() < deadline, "producer_fetch_denial_missing")
    finally:
        client.close()
    checks.append("producer_read_topic_authorization_failed")
    client = Consumer(
        {**config["broker"]["source"], "group.id": "foreign-group", "enable.auto.commit": False}
    )
    try:
        expect_kafka(
            lambda: client.committed([TopicPartition(TOPIC, 0)], timeout=5),
            KafkaError.GROUP_AUTHORIZATION_FAILED,
            "foreign_group_denied",
        )
    finally:
        client.close()
    checks.append("foreign_group_authorization_failed")
    admin = AdminClient(config["broker"]["source"])
    expect_kafka(
        lambda: admin.describe_topics(TopicCollection(["foreign-topic"]), request_timeout=5)[
            "foreign-topic"
        ].result(timeout=6),
        KafkaError.TOPIC_AUTHORIZATION_FAILED,
        "foreign_topic_denied",
    )
    checks.append("foreign_topic_authorization_failed")
    expect_kafka(
        lambda: admin.create_topics(
            [NewTopic("forbidden-created-topic", num_partitions=1, replication_factor=1)],
            request_timeout=5,
        )["forbidden-created-topic"].result(timeout=6),
        KafkaError.TOPIC_AUTHORIZATION_FAILED,
        "workload_create_topic_denied",
    )
    checks.append("workload_create_topic_authorization_failed")
    for name, change, expected in (
        ("wrong_password", {"sasl.password": "intentionally-wrong"}, KafkaError._AUTHENTICATION),
        ("untrusted_ca", {"ssl.ca.location": "/private/untrusted.crt"}, KafkaError._SSL),
    ):
        errors = []
        invalid = AdminClient({**config["broker"]["source"], **change, "error_cb": errors.append})
        try:
            invalid.list_topics(timeout=5)
        except KafkaException:
            require(
                any(error.code() == expected for error in errors), name + "_explicit_error_required"
            )
        else:
            raise ProbeError(name + "_unexpected_success")
        checks.append(name + "_explicit_client_rejection")
    anonymous = AdminClient(
        {
            "bootstrap.servers": "broker:9092",
            "security.protocol": "SSL",
            "ssl.ca.location": "/private/ca.crt",
            "log_level": 0,
        }
    )
    try:
        anonymous.list_topics(timeout=5)
    except KafkaException:
        checks.append("anonymous_cannot_obtain_kafka_metadata")
    else:
        raise ProbeError("anonymous_metadata_unexpected_success")
    with HttpClient(verify="/private/ca.crt", timeout=3) as http:
        require(
            http.get("https://broker:9644/v1/security/users").status_code == 401,
            "anonymous_admin_denied",
        )
        require(
            http.get(
                "https://broker:9644/v1/security/users",
                auth=("source-consumer", config["passwords"]["source"]),
            ).status_code
            == 403,
            "workload_admin_denied",
        )
    checks.extend(("anonymous_admin_401", "workload_admin_403"))
    for lane, foreign in (("ai", "source"), ("source", "ai")):
        kwargs = {
            "host": "db-" + lane,
            "dbname": lane + "_data",
            "user": foreign + "_worker",
            "password": config["passwords"][foreign],
            "connect_timeout": 3,
        }
        try:
            psycopg.connect(**kwargs)
        except psycopg.OperationalError as exc:
            require(
                "password authentication failed" in str(exc),
                "foreign_database_auth_denial_required",
            )
        else:
            raise ProbeError("foreign_database_auth_unexpected_success")
        checks.append(f"{foreign}_credential_rejected_by_{lane}_database")
    for role in ("ai_worker", "source_worker", "source_reader"):
        with db(config, role) as connection:
            info = connection.execute(
                "SELECT rolsuper,rolcreatedb,rolcreaterole FROM pg_roles WHERE rolname=current_user"
            ).fetchone()
            require(not any(info.values()), "workload_privileged_database_role")
            try:
                connection.execute("CREATE ROLE forbidden_role")
            except psycopg.errors.InsufficientPrivilege:
                connection.rollback()
            else:
                raise ProbeError("workload_role_creation_unexpected_success")
        checks.append(role + "_cannot_create_roles")
    with db(config, "source_reader") as connection:
        try:
            connection.execute("DELETE FROM ai_forecast_results")
        except psycopg.errors.InsufficientPrivilege:
            connection.rollback()
        else:
            raise ProbeError("source_reader_write_unexpected_success")
    checks.append("api_reader_cannot_delete_results")
    return checks


def verify(config: dict, expected: int) -> dict:
    deadline = time.monotonic() + 65
    while True:
        with db(config, "source_admin") as connection:
            transport = connection.execute(
                "SELECT outcome,partition,offset_number FROM ai_intelligence_transport ORDER BY partition,offset_number"
            ).fetchall()
            counts = {
                name: connection.execute(
                    sql.SQL("SELECT count(*) AS n FROM {}").format(sql.Identifier(name))
                ).fetchone()["n"]
                for name in (
                    "ai_forecast_results",
                    "ai_intelligence_inbox",
                    "ai_intelligence_partitions",
                )
            }
            positions = connection.execute(
                "SELECT partition,next_offset,coverage_start FROM ai_intelligence_partitions ORDER BY partition"
            ).fetchall()
            payload = connection.execute(
                "SELECT payload,payload_sha256 FROM ai_forecast_results"
            ).fetchone()
        if len(transport) == expected and counts == {
            "ai_forecast_results": 1,
            "ai_intelligence_inbox": 1,
            "ai_intelligence_partitions": 3,
        }:
            break
        require(time.monotonic() < deadline, "durable_projection_not_complete")
        time.sleep(1)
    require(
        [row["outcome"] for row in transport]
        == (["projected"] if expected == 1 else ["projected", "duplicate"]),
        "exact_transport_outcomes_required",
    )
    require(
        sum(row["next_offset"] for row in positions) == expected
        and all(row["coverage_start"] == 0 for row in positions),
        "exact_contiguous_checkpoint_required",
    )
    require(payload["payload"] == config["event"]["payload"], "exact_functional_payload_required")
    with db(config, "ai_admin") as connection:
        receipt = connection.execute(
            "SELECT document,delivered_at,delivered_partition,delivered_offset FROM ai.intelligence_outbox"
        ).fetchone()
    require(
        receipt["document"] == config["event"] and receipt["delivered_at"] is not None,
        "exact_outbox_document_and_receipt_required",
    )
    require(
        (receipt["delivered_partition"], receipt["delivered_offset"])
        == (transport[-1]["partition"], transport[-1]["offset_number"]),
        "outbox_transport_position_binding",
    )
    # Source API uses the separate read-only DB account and private access file.
    with HttpClient(base_url="http://source:8000", timeout=5) as http:
        deadline = time.monotonic() + 30
        while True:
            try:
                if http.get("/ready").status_code == 200:
                    break
            except (URLError, OSError):
                pass
            require(time.monotonic() < deadline, "source_api_not_ready")
            time.sleep(1)
        headers = {"Authorization": "Bearer " + config["tokens"]["intelligence"]}
        page = http.get("/intelligence/v2/forecasts", headers=headers)
        require(page.status_code == 200, "history_read_denied")
        body = page.json()
        require(
            body["selection"] == "immutable_history"
            and body["data_status"] == "available"
            and len(body["items"]) == 1
            and body["items"][0]["forecast"] == config["event"]["payload"],
            "exact_http_payload_required",
        )
        require(
            body["items"][0]["freshness"]["status"] != "current",
            "fixture_freshness_cannot_become_current",
        )
        require(
            http.get("/intelligence/v2/forecasts").status_code == 401, "anonymous_history_denied"
        )
        source_headers = {"Authorization": "Bearer " + config["tokens"]["source"]}
        require(
            http.get("/intelligence/v2/forecasts", headers=source_headers).status_code == 401,
            "source_token_not_intelligence_token",
        )
        require(
            http.get("/integration/v2/products", headers=headers).status_code == 401,
            "intelligence_token_not_source_token",
        )
        require(
            http.get("/intelligence/v2/forecasts/active", headers=headers).status_code == 503,
            "mechanics_fixture_cannot_activate_production_head",
        )
        http_checks = [
            "anonymous_history_401",
            "source_token_history_401",
            "intelligence_token_source_401",
            "active_head_unconfigured_503",
            "original_unknown_freshness_preserved",
        ]
    negatives = negative_auth(config) if expected == 1 else []
    return {
        "status": "passed",
        "transport": transport,
        "checkpoint": positions,
        "counts": counts,
        "prediction_id": config["event"]["payload"]["prediction_id"],
        "payload_sha256": payload["payload_sha256"],
        "event_sha256": hashlib.sha256(
            json.dumps(config["event"], sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "negative_auth": negatives,
        "http_checks": http_checks,
    }


def main() -> int:
    try:
        config = json.loads(CONFIG.read_text())
        mode = sys.argv[1]
        if mode == "bootstrap":
            result = bootstrap(config)
        elif mode == "grant":
            result = grant(config)
        elif mode == "redeliver":
            with db(config, "ai_admin") as connection:
                connection.execute(
                    "UPDATE ai.intelligence_outbox SET delivered_at=NULL,delivered_partition=NULL,delivered_offset=NULL"
                )
            result = {"status": "pending_again", "simulation": "broker_ack_before_outbox_receipt"}
        elif mode == "verify":
            result = verify(config, int(sys.argv[2]))
        else:
            raise ProbeError("unknown_probe_mode")
        sys.stdout.write(json.dumps(result) + "\n")
        return 0
    except Exception as exc:  # noqa: BLE001 - never print credentials or exception bodies
        code = str(exc) if isinstance(exc, ProbeError) else type(exc).__name__
        sys.stdout.write(json.dumps({"status": "failed", "code": code}) + "\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
