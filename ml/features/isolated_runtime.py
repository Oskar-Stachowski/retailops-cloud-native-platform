from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from ml.features.fact_input import validate_fact_input

ISOLATION_VERSION = "facts-docker-runtime-1.0.0"
WORKER_IMAGE = "python@sha256:90744cff8f32887f075c47d747a173ff333e9e98801667af93c357fa9f5e28ff"
WORKER_FILES = (
    "ml/__init__.py",
    "ml/features/__init__.py",
    "ml/features/fact_input.py",
    "ml/features/observation_history.py",
    "ml/features/ai_demand.py",
    "ml/features/worker.py",
    "ml/features/runtime_probe.py",
)
ROOT = Path(__file__).resolve().parents[2]


def _run(payload: dict, module: str) -> object:
    if module not in {"ml.features.worker", "ml.features.runtime_probe"}:
        msg = "Unknown isolated runtime entry point."
        raise ValueError(msg)
    docker = shutil.which("docker")
    if docker is None:
        msg = "Isolated feature runtime requires Docker and its pinned worker image."
        raise RuntimeError(msg)
    with TemporaryDirectory(prefix="retailops-facts-worker-") as temporary:
        bundle = Path(temporary)
        bundle.chmod(0o755)
        for name in WORKER_FILES:
            destination = bundle / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, destination)
        command = [
            docker,
            "run",
            "--rm",
            "-i",
            "--pull=never",
            "--network=none",
            "--read-only",
            "--user=65534:65534",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--pids-limit=64",
            "--memory=256m",
            "--cpus=1",
            "--mount",
            f"type=bind,source={bundle},target=/worker,readonly",
            WORKER_IMAGE,
            "python",
            "-I",
            "-B",
            "-c",
            (
                "import runpy,sys;sys.path.insert(0,'/worker');"
                f"runpy.run_module('{module}',run_name='__main__')"
            ),
        ]
        result = subprocess.run(  # noqa: S603 - fixed command/allowlisted module, no shell
            command,
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            check=False,
            timeout=60,
        )
    if result.returncode:
        msg = "Isolated feature runtime failed; no host execution fallback. " + result.stderr[:1000]
        raise RuntimeError(msg)
    return json.loads(result.stdout)


def isolated_feature_rows(payload: dict) -> list[dict]:
    validate_fact_input(payload)
    return _run(payload, "ml.features.worker")


def verify_runtime_isolation(source_dir: Path | None = None) -> dict:
    return _run(
        {"source_path": str(source_dir) if source_dir is not None else "/source"},
        "ml.features.runtime_probe",
    )
