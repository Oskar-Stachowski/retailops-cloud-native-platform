# ruff: noqa: INP001
"""Own a disposable, authenticated cross-repo output-lane Compose acceptance drill."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import signal
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


class RuntimeCommandError(RuntimeError):
    def __init__(self, code: str = "runtime_command_failed") -> None:
        self.code = code
        super().__init__(code)


def command(
    args: list[str], *, cwd: Path = ROOT, env: dict | None = None, timeout: int = 120
) -> str:
    # Commands, configuration, Docker inspection and build logs may contain credentials.
    # Capture them privately; expose only stable stage names and exception classes.
    result = subprocess.run(  # noqa: S603 - fixed argument arrays, no shell
        args, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout, check=False
    )
    if result.returncode:
        code = "runtime_command_failed"
        try:
            value = json.loads(result.stdout.strip().splitlines()[-1])
            if isinstance(value, dict) and re.fullmatch(
                r"[A-Za-z][A-Za-z0-9_]{0,79}", str(value.get("code", ""))
            ):
                code = value["code"]
        except (ValueError, IndexError):
            pass
        raise RuntimeCommandError(code)
    return result.stdout


def private_file(path: Path, content: str | bytes) -> None:
    with path.open("xb") as stream:
        path.chmod(0o600)
        stream.write(content.encode() if isinstance(content, str) else content)


def write_json(path: Path, value: dict) -> None:
    private_file(path, json.dumps(value) + "\n")


def verify_owner(owner: Path) -> dict:
    pin = json.loads((HERE / "owner.json").read_text())
    if command(["git", "rev-parse", "HEAD"], cwd=owner).strip() != pin["commit"]:
        msg = "owner_commit_mismatch"
        raise ValueError(msg)
    if command(["git", "status", "--porcelain", "--untracked-files=no"], cwd=owner).strip():
        msg = "owner_tracked_changes"
        raise ValueError(msg)
    client = json.loads(
        (ROOT / "services/api/app/contracts/source-reads-v2/client.json").read_text()
    )
    if (pin["repository"], pin["commit"]) != (client["repository"], client["commit"]):
        msg = "owner_client_pin_mismatch"
        raise ValueError(msg)
    for name, expected in pin["sha256"].items():
        if hashlib.sha256((owner / name).read_bytes()).hexdigest() != expected:
            msg = "owner_bytes_mismatch"
            raise ValueError(msg)
    return pin


def certificates(private: Path) -> None:
    ca = private / "ca"
    ca.mkdir(mode=0o700)
    for prefix in ("trusted", "untrusted"):
        command(
            [
                "openssl",
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-nodes",
                "-days",
                "2",
                "-subj",
                "/CN=AI10-" + prefix,
                "-keyout",
                str(ca / (prefix + ".key")),
                "-out",
                str(ca / (prefix + ".crt")),
            ]
        )
    command(
        [
            "openssl",
            "req",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-subj",
            "/CN=broker",
            "-keyout",
            str(private / "broker/broker.key"),
            "-out",
            str(ca / "broker.csr"),
        ]
    )
    private_file(ca / "extensions", "subjectAltName=DNS:broker\nextendedKeyUsage=serverAuth\n")
    command(
        [
            "openssl",
            "x509",
            "-req",
            "-days",
            "2",
            "-in",
            str(ca / "broker.csr"),
            "-CA",
            str(ca / "trusted.crt"),
            "-CAkey",
            str(ca / "trusted.key"),
            "-CAcreateserial",
            "-extfile",
            str(ca / "extensions"),
            "-out",
            str(private / "broker/broker.crt"),
        ]
    )
    for directory in ("broker", "ai", "source", "probe"):
        private_file(private / directory / "ca.crt", (ca / "trusted.crt").read_bytes())
    private_file(private / "probe/untrusted.crt", (ca / "untrusted.crt").read_bytes())
    (private / "broker/broker.key").chmod(0o600)


def prepare(private: Path, owner: Path) -> None:
    for name in ("broker", "broker-data", "ai", "source", "probe"):
        (private / name).mkdir(mode=0o700)
    passwords = {
        name: secrets.token_hex(24)
        for name in ("admin", "ai", "source", "ai_admin", "source_admin", "source_reader")
    }
    tokens = {name: secrets.token_hex(24) for name in ("source", "intelligence")}
    certificates(private)
    private_file(private / "broker.env", "RP_BOOTSTRAP_USER=bootstrap:" + passwords["admin"] + "\n")
    private_file(
        private / "broker/.bootstrap.yaml",
        "enable_sasl: true\nadmin_api_require_auth: true\nhttp_authentication: [BASIC]\nsuperusers: [bootstrap]\nauto_create_topics_enabled: false\nsasl_mechanisms: [SCRAM]\n",
    )
    private_file(
        private / "broker/redpanda.yaml",
        """redpanda:
  data_directory: /var/lib/redpanda/data
  node_id: 0
  seed_servers: []
  rpc_server: {address: 0.0.0.0, port: 33145}
  advertised_rpc_api: {address: broker, port: 33145}
  kafka_api: [{address: 0.0.0.0, port: 9092, name: secure}]
  advertised_kafka_api: [{address: broker, port: 9092, name: secure}]
  kafka_api_tls:
    - {name: secure, enabled: true, require_client_auth: false, key_file: /private/broker.key, cert_file: /private/broker.crt, truststore_file: /private/ca.crt}
  admin: [{address: 0.0.0.0, port: 9644, name: secure-admin}]
  admin_api_tls:
    - {name: secure-admin, enabled: true, require_client_auth: false, key_file: /private/broker.key, cert_file: /private/broker.crt, truststore_file: /private/ca.crt}
""",
    )
    urls = {}
    for lane in ("ai", "source"):
        private_file(
            private / ("db-" + lane + ".env"),
            f"POSTGRES_DB={lane}_data\nPOSTGRES_USER={lane}_admin\nPOSTGRES_PASSWORD={passwords[lane + '_admin']}\nPOSTGRES_HOST_AUTH_METHOD=scram-sha-256\n",
        )
        for role, key in ((lane + "_admin", lane + "_admin"), (lane + "_worker", lane)):
            urls[role] = f"postgresql://{role}:{passwords[key]}@db-{lane}:5432/{lane}_data"
    urls["source_reader"] = (
        f"postgresql://source_reader:{passwords['source_reader']}@db-source:5432/source_data"
    )
    ai_settings = (
        "APP_ENV=test\nARTIFACT_ROOT=/tmp/ai10-artifacts\nNETWORK_MODE=compose\nDATABASE_URL="
    )
    for lane, role in (("ai", "ai_worker"), ("ai-migrate", "ai_admin")):
        private_file(
            private / (lane + ".env"),
            ai_settings + urls[role].replace("postgresql://", "postgresql+psycopg://") + "\n",
        )
    for lane, role in (
        ("source", "source_reader"),
        ("consumer", "source_worker"),
        ("source-migrate", "source_admin"),
    ):
        private_file(
            private / (lane + ".env"),
            "APP_ENV=local\nDATABASE_URL="
            + urls[role]
            + "\nRETAILOPS_INTELLIGENCE_ACCESS_POLICY=/private/intelligence.json\nRETAILOPS_SOURCE_ACCESS_POLICY=/private/source.json\n",
        )
    base = {
        "bootstrap.servers": "broker:9092",
        "security.protocol": "SASL_SSL",
        "sasl.mechanism": "SCRAM-SHA-256",
        "ssl.ca.location": "/private/ca.crt",
        "log_level": 0,
    }
    configs = {
        name: {**base, "sasl.username": username, "sasl.password": passwords[name]}
        for name, username in (
            ("ai", "ai-producer"),
            ("source", "source-consumer"),
            ("admin", "bootstrap"),
        )
    }
    write_json(private / "ai/broker.json", configs["ai"])
    write_json(
        private / "source/broker.json",
        {
            "bootstrap_servers": "broker:9092",
            "security_protocol": "SASL_SSL",
            "sasl_mechanism": "SCRAM-SHA-256",
            "username": "source-consumer",
            "password": passwords["source"],
            "ca_file": "/private/ca.crt",
        },
    )
    event = json.loads((owner / "contracts/events/v2/forecast_generated.fixture.json").read_text())
    payload = event["payload"]
    write_json(
        private / "source/intelligence.json",
        {
            "version": "retailops-intelligence-access-1.0",
            "principals": [
                {
                    "principal_id": "fixture-ui-reader",
                    "credential_sha256": hashlib.sha256(
                        tokens["intelligence"].encode()
                    ).hexdigest(),
                    "capabilities": ["forecast:read"],
                    "product_ids": [payload["product_id"]],
                    "selling_location_ids": [payload["selling_location_id"]],
                    "channels": [payload["channel"]],
                    "release_ids": [payload["release_id"]],
                }
            ],
        },
    )
    write_json(
        private / "source/source.json",
        {
            "version": "retailops-source-access-1.0",
            "principals": [
                {
                    "principal_id": "fixture-ai-source-reader",
                    "credential_sha256": hashlib.sha256(tokens["source"].encode()).hexdigest(),
                    "resources": ["products"],
                    "product_ids": ["11111111-1111-4111-8111-111111111111"],
                    "channels": [],
                    "warehouse_codes": [],
                }
            ],
        },
    )
    write_json(
        private / "probe/config.json",
        {
            "broker": configs,
            "database": urls,
            "passwords": passwords,
            "tokens": tokens,
            "event": event,
        },
    )


def validate_configuration(configuration: dict, project: str) -> None:
    if configuration.get("name") != project:
        msg = "runtime_project_mismatch"
        raise ValueError(msg)
    for service in configuration["services"].values():
        if (
            service.get("ports")
            or service.get("container_name")
            or service.get("privileged")
            or service.get("network_mode")
        ):
            msg = "isolated_runtime_required"
            raise ValueError(msg)
    if any(
        not value.get("internal") or value.get("external")
        for value in configuration["networks"].values()
    ):
        msg = "private_project_networks_required"
        raise ValueError(msg)
    if any(value.get("external") for value in configuration.get("volumes", {}).values()):
        msg = "owned_project_volumes_required"
        raise ValueError(msg)
    services = configuration["services"]
    if (
        "source-db" in services["delivery"]["networks"]
        or "ai-db" in services["source"]["networks"]
        or "ai-db" in services["consumer"]["networks"]
    ):
        msg = "separate_database_networks_required"
        raise ValueError(msg)


def main() -> int:  # noqa: PLR0915
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner-root", type=Path, required=True)
    parser.add_argument(
        "--verify-config",
        action="store_true",
        help="Validate without starting Docker or containers.",
    )
    args = parser.parse_args()
    project = "retailops-ai10-runtime-" + uuid4().hex[:12]
    report: dict[str, Any] = {
        "version": "ai10-runtime-mechanics-1.0",
        "evidence_class": "invented_transport_fixture",
        "project": project,
        "status": "failed",
        "started_at": datetime.now(UTC).isoformat(),
        "stages": [],
        "cleanup": "not_started",
    }
    report_path = ROOT / "ci-cd/reports/intelligence-runtime/report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    started = False

    def interrupted(_signum: int, _frame: object) -> None:
        msg = "runtime_interrupted"
        raise RuntimeError(msg)

    signal.signal(signal.SIGINT, interrupted)
    signal.signal(signal.SIGTERM, interrupted)
    try:
        owner = args.owner_root.resolve(strict=True)
        report["owner"] = verify_owner(owner)
        report["source_commit"] = command(["git", "rev-parse", "HEAD"]).strip()
        with tempfile.TemporaryDirectory(prefix=project + "-") as directory:
            private = Path(directory)
            prepare(private, owner)
            env = {
                key: value
                for key, value in os.environ.items()
                if not key.startswith(("COMPOSE_", "AI10_"))
            }
            env.update(
                {
                    "COMPOSE_PROJECT_NAME": project,
                    "AI10_PRIVATE": str(private),
                    "AI10_OWNER_ROOT": str(owner),
                    "AI10_UID": str(os.getuid()),
                    "AI10_GID": str(os.getgid()),
                }
            )
            compose = [
                "docker",
                "compose",
                "--env-file",
                "/dev/null",
                "-p",
                project,
                "-f",
                str(HERE / "compose.yml"),
                "--profile",
                "tools",
            ]

            def stage(name: str, arguments: list[str], timeout: int = 120) -> str:
                sys.stdout.write("AI10 runtime: " + name + "\n")
                sys.stdout.flush()
                try:
                    output = command([*compose, *arguments], env=env, timeout=timeout)
                except RuntimeCommandError as exc:
                    report.update(failure_stage=name, failure_code=exc.code)
                    if name == "bootstrap_auth_and_database_roles":
                        try:
                            raw = command(
                                [*compose, "logs", "--no-color", "--tail", "100", "broker"], env=env
                            )
                            sensitive = json.loads((private / "probe/config.json").read_text())
                            for value in [
                                *sensitive["passwords"].values(),
                                *sensitive["tokens"].values(),
                            ]:
                                raw = raw.replace(value, "[redacted]")
                            report["broker_diagnostics"] = [
                                line[:800]
                                for line in raw.splitlines()
                                if re.search(
                                    r"error|failed|permission|read.only|exception|fatal|panic",
                                    line,
                                    re.IGNORECASE,
                                )
                            ][-12:]
                        except (OSError, RuntimeError, ValueError):
                            report["broker_diagnostics"] = ["diagnostics_unavailable"]
                    raise
                report["stages"].append(name)
                return output

            configuration = json.loads(command([*compose, "config", "--format", "json"], env=env))
            validate_configuration(configuration, project)
            if args.verify_config:
                report.update(status="configuration_passed", cleanup="no_containers_started")
                return 0
            command(["docker", "info"], timeout=15)  # Never start or recover a stopped daemon.
            started = True
            try:
                stage("build_pinned_images", ["build", "source", "delivery"], 900)
                stage(
                    "start_owned_databases",
                    ["up", "-d", "--wait", "--wait-timeout", "120", "db-ai", "db-source"],
                    150,
                )
                stage("start_private_broker", ["up", "-d", "broker"])
                stage(
                    "bootstrap_auth_and_database_roles",
                    ["run", "--rm", "--no-deps", "probe", "python", "/probe.py", "bootstrap"],
                    180,
                )
                stage("migrate_source", ["run", "--rm", "--no-deps", "migrate"])
                stage("prepare_invented_ai_outbox", ["run", "--rm", "--no-deps", "ai-fixture"])
                stage(
                    "grant_scoped_source_tables",
                    ["run", "--rm", "--no-deps", "probe", "python", "/probe.py", "grant"],
                )
                stage("start_api_and_checkpoint_consumer", ["up", "-d", "source", "consumer"])
                first = stage("deliver_pinned_ai_outbox", ["run", "--rm", "--no-deps", "delivery"])
                if json.loads(first.strip().splitlines()[-1]) != {
                    "status": "completed",
                    "delivered": 1,
                }:
                    msg = "outbox_receipt_required"
                    raise RuntimeError(msg)
                report["first_delivery"] = json.loads(first.strip().splitlines()[-1])
                report["initial"] = json.loads(
                    stage(
                        "verify_projection_and_negative_auth",
                        ["run", "--rm", "--no-deps", "probe", "python", "/probe.py", "verify", "1"],
                        180,
                    )
                    .strip()
                    .splitlines()[-1]
                )
                stage("kill_owned_consumer", ["kill", "-s", "SIGKILL", "consumer"])
                stage(
                    "simulate_delivery_after_broker_ack_before_db_receipt",
                    ["run", "--rm", "--no-deps", "probe", "python", "/probe.py", "redeliver"],
                )
                second = stage(
                    "redeliver_identical_ai_event", ["run", "--rm", "--no-deps", "delivery"]
                )
                report["second_delivery"] = json.loads(second.strip().splitlines()[-1])
                if report["second_delivery"] != {"status": "completed", "delivered": 1}:
                    msg = "redelivery_receipt_required"
                    raise RuntimeError(msg)
                stage("restart_owned_consumer", ["up", "-d", "consumer"])
                report["final"] = json.loads(
                    stage(
                        "verify_durable_resume_and_exact_dedup",
                        ["run", "--rm", "--no-deps", "probe", "python", "/probe.py", "verify", "2"],
                        180,
                    )
                    .strip()
                    .splitlines()[-1]
                )
                report["status"] = "passed"
            finally:
                try:
                    stage("cleanup_owned_project", ["down", "--volumes", "--remove-orphans"], 120)
                    remaining = {}
                    for resource in ("container", "volume", "network"):
                        remaining[resource] = command(
                            [
                                "docker",
                                resource,
                                "ls",
                                "-q",
                                *(["--all"] if resource == "container" else []),
                                "--filter",
                                "label=com.docker.compose.project=" + project,
                            ]
                        ).split()
                    if any(remaining.values()):
                        msg = "owned_resource_cleanup_incomplete"
                        raise RuntimeError(msg)
                    for image in (project + "-source", project + "-delivery"):
                        try:
                            command(["docker", "image", "inspect", image])
                        except RuntimeCommandError:
                            continue
                        command(["docker", "image", "rm", image])
                    report["cleanup"] = "passed"
                except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
                    report.update(
                        status="failed", cleanup="failed", cleanup_error=type(exc).__name__
                    )
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        report["error_class"] = type(exc).__name__
        if not started:
            report["cleanup"] = "no_containers_started"
    finally:
        report["completed_at"] = datetime.now(UTC).isoformat()
        report_path.write_text(json.dumps(report, indent=2) + "\n")
        sys.stdout.write(
            json.dumps(
                {
                    "status": report["status"],
                    "cleanup": report["cleanup"],
                    "report": str(report_path.relative_to(ROOT)),
                }
            )
            + "\n"
        )
    return int(report["status"] != "passed")


if __name__ == "__main__":
    raise SystemExit(main())
