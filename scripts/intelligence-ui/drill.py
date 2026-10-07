"""Actual built UI, API and isolated PostgreSQL; invented model/owner fixtures only."""

# ruff: noqa: INP001, PLC0415
# Imports follow the explicitly selected repository fixture path, never a user path.

from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "ci-cd/reports/intelligence-ui"


def execute(command: list[str], *, cwd: Path, env: dict[str, str]) -> None:
    subprocess.run(command, cwd=cwd, env=env, check=True, timeout=180)  # noqa: S603 - fixed callers below


def seed(control: Path) -> dict[str, Any]:
    sys.path[:0] = [str(ROOT / "services/api"), str(ROOT / "services/api/tests")]
    from intelligence_head_fixture import publication_events, selected_policy, store_policy

    from app.repositories.intelligence_repository import IntelligenceRepository
    from app.services.intelligence_contract import TOPIC, validate_event

    products = tuple(f"fixture-product-{index:02}" for index in range(10))
    events = publication_events(products=products)
    old = publication_events(
        products=(products[0],),
        origin=datetime.fromisoformat(events[0]["payload"]["forecast_origin"]) - timedelta(days=2),
    )
    foreign = publication_events(products=("foreign-product",))
    repository = IntelligenceRepository()
    for event in [*events, *old, *foreign]:
        validate_event(event, transport_topic=TOPIC)
        repository.project(event)
    policy = selected_policy(events, products=products)
    store_policy(control / "head.json", policy)
    store_policy(control / "replacement-head.json", selected_policy(old, products=(products[0],)))
    token = secrets.token_urlsafe(48)
    access = {
        "version": "retailops-intelligence-access-1.0",
        "principals": [
            {
                "principal_id": "fixture-personal-ui-reader",
                "credential_sha256": hashlib.sha256(token.encode()).hexdigest(),
                "capabilities": ["forecast:read"],
                "product_ids": list(products),
                "selling_location_ids": ["fixture-store"],
                "channels": ["store"],
                "release_ids": [events[0]["payload"]["release_id"]],
            }
        ],
    }
    for name, value in (
        ("access.json", json.dumps(access)),
        ("credential", token),
        ("expected.json", json.dumps([event["payload"] for event in events])),
    ):
        path = control / name
        path.write_text(value)
        path.chmod(0o600)
    return {
        "active_rows": len(events),
        "history_rows": len(events) + len(old),
        "foreign_rows": len(foreign),
        "model_qualification": False,
    }


def ready(url: str, process: subprocess.Popen[bytes]) -> None:
    deadline = time.monotonic() + 30
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    while time.monotonic() < deadline:
        if process.poll() is not None:
            msg = "owned_server_stopped"
            raise RuntimeError(msg)
        try:
            with opener.open(url, timeout=1) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError):
            time.sleep(0.1)
    msg = "owned_server_not_ready"
    raise RuntimeError(msg)


def main() -> int:  # noqa: PLR0915 - one owned-resource lifecycle
    REPORT.mkdir(parents=True, exist_ok=True)
    result: dict[str, Any] = {
        "status": "failed",
        "started_at": datetime.now(UTC).isoformat(),
        "source_commit": subprocess.check_output(  # noqa: S603 - fixed read-only Git query
            [shutil.which("git") or "/usr/bin/git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "scope": "actual built frontend and PostgreSQL/API over loopback HTTP; invented forecast and operator fixtures; no model or deployment qualification",
    }
    processes: list[subprocess.Popen[bytes]] = []
    private = Path(tempfile.mkdtemp(prefix="retailops-intelligence-ui-"))
    private.chmod(0o700)
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + str(ROOT / "services/api")
    try:
        # The CI caller owns this disposable DB. Refuse to touch a normal local DB.
        if env.get("RETAILOPS_UI_DISPOSABLE_DB") != "1":
            msg = "disposable_database_confirmation_required"
            raise RuntimeError(msg)
        execute(
            [sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT / "services/api", env=env
        )
        result["fixture"] = seed(private)
        env["RETAILOPS_ENABLE_SUGGESTION_FIXTURE_TRANSPORT"] = "1"
        os.environ["RETAILOPS_ENABLE_SUGGESTION_FIXTURE_TRANSPORT"] = "1"
        from suggestion_fixture import seed as seed_suggestions

        result["suggestion_fixture"] = seed_suggestions(private)
        from model_fixture import seed as seed_models

        result["model_fixture"] = seed_models(private)
        env["RETAILOPS_INTELLIGENCE_ACCESS_POLICY"] = str(private / "access.json")
        env["RETAILOPS_INTELLIGENCE_HEAD_POLICY"] = str(private / "head.json")
        env["RETAILOPS_INTELLIGENCE_MODEL_ACCESS_POLICY"] = str(private / "model-access.json")
        env["RETAILOPS_INTELLIGENCE_SUGGESTION_ACCESS_POLICY"] = str(
            private / "suggestion-access.json"
        )
        env["INTELLIGENCE_UI_PYTHON"] = sys.executable
        # Own port 8000 only in the isolated CI runner; fail if another process owns it.
        with socket.socket() as owned:
            owned.bind(("127.0.0.1", 8000))
            owned.listen()
            with (REPORT / "api.log").open("wb") as log:
                api = subprocess.Popen(  # noqa: S603 - fixed Uvicorn and owned inherited socket
                    [
                        sys.executable,
                        "-m",
                        "uvicorn",
                        "app.main:app",
                        "--fd",
                        str(owned.fileno()),
                        "--no-access-log",
                    ],
                    cwd=ROOT / "services/api",
                    env=env,
                    pass_fds=(owned.fileno(),),
                    stdout=log,
                    stderr=log,
                )
                processes.append(api)
                ready("http://127.0.0.1:8000/health", api)
        execute(["npm", "run", "build"], cwd=ROOT / "frontend", env=env)
        with (REPORT / "frontend.log").open("wb") as log:
            frontend = subprocess.Popen(  # noqa: S603 - fixed repository Vite server
                [
                    shutil.which("node") or "/usr/bin/node",
                    "node_modules/vite/bin/vite.js",
                    "preview",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "4173",
                    "--strictPort",
                ],
                cwd=ROOT / "frontend",
                env=env,
                stdout=log,
                stderr=log,
            )
            processes.append(frontend)
            ready("http://127.0.0.1:4173/forecasts", frontend)
        env["FRONTEND_BASE_URL"] = "http://127.0.0.1:4173"
        env["INTELLIGENCE_UI_CONTROL_DIR"] = str(private)
        execute(
            [
                "node",
                "node_modules/@playwright/test/cli.js",
                "test",
                "--project=intelligence-chromium",
            ],
            cwd=ROOT / "frontend",
            env=env,
        )
        result["browser"] = json.loads((private / "browser-report.json").read_text())
        result["suggestion_browser"] = json.loads(
            (private / "suggestion-browser-report.json").read_text()
        )
        result["model_browser"] = json.loads((private / "model-browser-report.json").read_text())
        if (
            result["browser"]["status"] != "passed"
            or result["suggestion_browser"]["status"] != "passed"
            or result["model_browser"]["status"] != "passed"
        ):
            msg = "browser_acceptance_failed"
            raise RuntimeError(msg)
        shutil.copyfile(private / "forecast-lineage.png", REPORT / "forecast-lineage.png")
        result["screenshot_sha256"] = hashlib.sha256(
            (REPORT / "forecast-lineage.png").read_bytes()
        ).hexdigest()
        shutil.copyfile(private / "suggestion-evidence.png", REPORT / "suggestion-evidence.png")
        result["suggestion_screenshot_sha256"] = hashlib.sha256(
            (REPORT / "suggestion-evidence.png").read_bytes()
        ).hexdigest()
        shutil.copyfile(private / "model-lineage.png", REPORT / "model-lineage.png")
        result["model_screenshot_sha256"] = hashlib.sha256(
            (REPORT / "model-lineage.png").read_bytes()
        ).hexdigest()
        result["status"] = "passed"
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
        result["error_type"] = type(exc).__name__
        raise
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
        shutil.rmtree(private)
        result["cleanup"] = {
            "owned_servers_stopped": all(process.poll() is not None for process in processes),
            "private_files_removed": not private.exists(),
            "database_lifecycle": "owned by CI service; no shared database cleanup",
        }
        result["finished_at"] = datetime.now(UTC).isoformat()
        (REPORT / "report.json").write_text(json.dumps(result, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
