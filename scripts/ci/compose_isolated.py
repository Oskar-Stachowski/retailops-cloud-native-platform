"""Own one disposable Compose project, including cleanup on failed validation."""

import json
import os
import signal
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]


def main():
    project = "retailops-ci-" + uuid4().hex[:12]
    env = {k: v for k, v in os.environ.items() if not k.startswith("COMPOSE_")}
    values = {
        "COMPOSE_PROJECT_NAME": project,
        "COMPOSE_CI_PROFILES": "dev,observability",
        "COMPOSE_PROFILES": "dev,observability",
        "HOST_BIND": "127.0.0.1",
        "API_IMAGE": project + "-api:test",
        "FRONTEND_IMAGE": project + "-frontend:test",
        "POSTGRES_DB": "retailops",
        "POSTGRES_USER": "retailops",
        "POSTGRES_PASSWORD": "disposable-ci-only",
        "GRAFANA_ADMIN_USER": "admin",
        "GRAFANA_ADMIN_PASSWORD": "disposable-ci-only",
        "APP_ENV": "local",
    }
    sockets = []
    for name in (
        "API",
        "FRONTEND",
        "POSTGRES",
        "PROMETHEUS",
        "GRAFANA",
        "REDPANDA_KAFKA",
        "REDPANDA_ADMIN",
    ):
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        values[name + "_PORT"] = str(sock.getsockname()[1])
        sockets.append(sock)
    env.update(values)
    compose = [
        "docker",
        "compose",
        "--env-file",
        "/dev/null",
        "-p",
        project,
        "-f",
        "docker-compose.yml",
    ]
    values["COMPOSE"] = " ".join(compose)
    report = {
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "project": project,
        "status": "failed",
        "source_dirty": bool(
            subprocess.check_output(
                [
                    "git",
                    "status",
                    "--porcelain",
                    "--untracked-files=normal",
                    "--",
                    "services/api",
                    "frontend",
                    "observability",
                    "scripts/ci",
                    "docker-compose.yml",
                    "Makefile",
                    "Jenkinsfile",
                ],
                cwd=ROOT,
                text=True,
            ).strip()
        ),
    }
    report_path = ROOT / "ci-cd/reports/docker/isolated-runtime.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    def run(args, **kwargs):
        return subprocess.run(args, cwd=ROOT, env=env, text=True, timeout=2400, **kwargs)

    def interrupted(signum, _frame):
        raise RuntimeError(f"Interrupted by signal {signum}")

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    try:
        for sock in sockets:
            sock.close()
        # Command-line variables take precedence over a developer's local .env.
        run(["make", "compose-ci-internal", *[f"{k}={v}" for k, v in values.items()]], check=True)
        report["images"] = {}
        for component in ("api", "frontend"):
            tag = values[component.upper() + "_IMAGE"]
            inspected = run(["docker", "image", "inspect", tag], check=True, capture_output=True)
            report["images"][component] = {"tag": tag, "id": json.loads(inspected.stdout)[0]["Id"]}
        report["status"] = "passed"
    finally:
        cleanup = run(compose + ["down", "--volumes", "--remove-orphans"], check=False)
        # Scope every query/deletion to this randomly named project.
        containers = run(
            ["docker", "ps", "-aq", "--filter", "label=com.docker.compose.project=" + project],
            capture_output=True,
            check=True,
        )
        volumes = run(
            [
                "docker",
                "volume",
                "ls",
                "-q",
                "--filter",
                "label=com.docker.compose.project=" + project,
            ],
            capture_output=True,
            check=True,
        )
        report["cleanup_passed"] = (
            cleanup.returncode == 0 and not containers.stdout.strip() and not volumes.stdout.strip()
        )
        if not report["cleanup_passed"]:
            report["status"] = "failed"
        for key in ("API_IMAGE", "FRONTEND_IMAGE"):
            run(["docker", "image", "rm", values[key]], check=False, capture_output=True)
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        report_path.write_text(json.dumps(report, indent=2) + "\n")
        if not report["cleanup_passed"]:
            raise RuntimeError("Disposable Compose cleanup failed; inspect isolated-runtime.json")


if __name__ == "__main__":
    main()
