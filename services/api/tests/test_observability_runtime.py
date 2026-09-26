import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts/ci" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("project,command", [
    ("retailops-cloud-native-platform", "docker compose"),
    ("retailops-ci-test", "docker compose -p another-project"),
    ("retailops-ci-test", "docker compose"),
])
def test_fault_injection_refuses_unowned_project(monkeypatch, project, command):
    module = load("observability_drill")
    monkeypatch.setenv("COMPOSE_PROJECT_NAME", project)
    monkeypatch.setenv("COMPOSE", command)
    monkeypatch.setattr(module.subprocess, "run", lambda *args, **kwargs: pytest.fail("must not mutate Docker"))
    with pytest.raises(RuntimeError, match="explicit disposable"):
        module.main()


def test_failed_runtime_cleans_only_its_own_project(monkeypatch, tmp_path):
    module = load("compose_isolated")
    module.ROOT = tmp_path
    monkeypatch.setenv("COMPOSE_PROJECT_NAME", "developer-project")
    monkeypatch.setenv("COMPOSE_FILE", "developer-compose.yml")
    monkeypatch.setattr(module.signal, "signal", lambda *args: None)
    monkeypatch.setattr(module.subprocess, "check_output", lambda args, **kwargs: "" if "status" in args else "a" * 40)
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
    for args, kwargs in calls:
        assert "developer-project" not in " ".join(args)
        assert "COMPOSE_FILE" not in kwargs["env"]
    down = [args for args, _ in calls if "down" in args]
    assert len(down) == 1
    assert down[0][down[0].index("-p") + 1] == project
