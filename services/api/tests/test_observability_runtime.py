import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts/ci" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "project,command",
    [
        ("retailops-cloud-native-platform", "docker compose"),
        ("retailops-ci-test", "docker compose -p another-project"),
        ("retailops-ci-test", "docker compose"),
    ],
)
def test_fault_injection_refuses_unowned_project(monkeypatch, project, command):
    module = load("observability_drill")
    monkeypatch.setenv("COMPOSE_PROJECT_NAME", project)
    monkeypatch.setenv("COMPOSE", command)
    monkeypatch.setattr(
        module.subprocess, "run", lambda *args, **kwargs: pytest.fail("must not mutate Docker")
    )
    with pytest.raises(RuntimeError, match="explicit disposable"):
        module.main()


def test_failed_runtime_cleans_only_its_own_project(monkeypatch, tmp_path):
    module = load("compose_isolated")
    module.ROOT = tmp_path
    monkeypatch.setenv("COMPOSE_PROJECT_NAME", "developer-project")
    monkeypatch.setenv("COMPOSE_FILE", "developer-compose.yml")
    monkeypatch.setenv("COMPOSE_BROWSER_TESTS", "1")
    monkeypatch.setattr(module.signal, "signal", lambda *args: None)
    monkeypatch.setattr(
        module.subprocess,
        "check_output",
        lambda args, **kwargs: "" if "status" in args else "a" * 40,
    )
    calls = []

    def run(args, **kwargs):
        calls.append((args, kwargs))
        if args[0] == "make":
            raise subprocess.CalledProcessError(1, args)
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(module.subprocess, "run", run)
    with pytest.raises(subprocess.CalledProcessError):
        module.main()
    report = json.loads((tmp_path / "ci-cd/reports/docker/isolated-runtime.json").read_text())
    assert report["status"] == "failed"
    assert report["cleanup_passed"]
    project = report["project"]
    assert project.startswith("retailops-ci-")
    assert "COMPOSE_BROWSER_TESTS=1" in calls[0][0]
    for args, kwargs in calls:
        assert "developer-project" not in " ".join(args)
        assert "COMPOSE_FILE" not in kwargs["env"]
    down = [args for args, _ in calls if "down" in args]
    assert len(down) == 1
    assert down[0][down[0].index("-p") + 1] == project


@pytest.mark.parametrize("recovers", [False, True])
def test_smoke_requires_api_scrape_and_allows_initial_scrape_delay(tmp_path, recovers):
    # No network: simulate Prometheus becoming ready before the first API scrape.
    fake_curl = tmp_path / "curl"
    fake_curl.write_text(
        f"#!{sys.executable}\n"
        + """
import json
import os
import sys
from pathlib import Path
url = sys.argv[-1]
body = {}
if url.endswith('/metrics'):
    body = 'retailops_api_info retailops_db_operations_total retailops_stream_metrics_generated_at_seconds'
elif '/targets?' in url:
    count = Path('target-calls')
    calls = int(count.read_text()) + 1 if count.exists() else 1
    count.write_text(str(calls))
    healthy = os.environ['RECOVERS'] == 'yes' and calls > 1
    body = {'data': {'activeTargets': [
        {'labels': {'job': 'prometheus'}, 'health': 'up'},
        {'labels': {'job': 'retailops-api'}, 'health': 'up' if healthy else 'down'}]}}
elif url.endswith('/rules'):
    body = ['RetailOpsApiMetricsTargetDown', 'RetailOpsApiInfoMissing', 'RetailOpsDatabaseOperationsMissing', 'RetailOpsStreamEventsStale', 'RetailOpsStreamDeadLetterEventsIncreasing']
elif '/datasources/' in url:
    body = {'type': 'prometheus'}
elif '/search?' in url:
    body = ['RetailOps Overview', 'RetailOps API', 'RetailOps Business Operations', 'RetailOps Stream Processing']
print(json.dumps(body, separators=(',', ':')))
print('200')
"""
    )
    fake_curl.chmod(0o755)
    env = dict(
        os.environ,
        PATH=str(tmp_path) + os.pathsep + os.environ["PATH"],
        RECOVERS="yes" if recovers else "no",
        SMOKE_SLEEP_SECONDS="0",
        SMOKE_MAX_ATTEMPTS="2",
        OBSERVABILITY_REPORTS_DIR=str(tmp_path / "reports"),
    )
    result = subprocess.run(
        ["bash", str(ROOT / "scripts/ci/observability_smoke.sh")],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )
    assert (result.returncode == 0) is recovers, result.stdout + result.stderr
    assert (tmp_path / "target-calls").read_text() == "2"


@pytest.mark.parametrize("health,ready", [("unknown", False), ("err", False), ("ok", True)])
def test_loaded_rule_requires_successful_evaluation(monkeypatch, health, ready):
    module = load("observability_drill")
    current = {"name": module.ALERT, "health": health, "state": "inactive"}
    monkeypatch.setattr(module, "get", lambda url: {"data": {"groups": [{"rules": [current]}]}})
    assert bool(module.rule_in_state("inactive")) is ready
    assert module.rule_in_state("firing") is None
