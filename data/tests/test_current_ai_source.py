"""Exercise the real default CLI and explicit legacy compatibility mode."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from data.export.policy import GENERATED_ROOT, ROOT


def cli(module, arguments):
    result = subprocess.run(
        [sys.executable, "-m", module, *arguments], cwd=ROOT, capture_output=True, text=True,
        check=True, timeout=120,
    )
    return result.stdout


@pytest.mark.parametrize("profile", ["ai-smoke", "ai-intermittent-v1"])
def test_default_ai_generator_publishes_inventory_and_legacy_stays_explicit(tmp_path, profile):
    args = ["--profile", profile, "--days", "10", "--products", "3", "--stores", "3", "--warehouses", "2", "--end-date", "2026-07-31"]
    result = json.loads(cli("data.generator.main", [*args, "--output-dir", str(tmp_path / "current")]))
    source = Path(result["directory"])
    manifest = json.loads((source / "dataset_manifest.v2.json").read_text())
    assert manifest["schema_version"] == "2.7.0" and manifest["facts_ready"]
    assert (source / "facts/inventory_ledger.csv").is_file()
    assert manifest["inventory_ready"] is False  # Frozen source readiness; curated is the release gate.
    cli("data.generator.main", [*args, "--source-version", "2.6", "--output-dir", str(tmp_path / "legacy")])
    old = json.loads((tmp_path / "legacy/dataset_manifest.v2.json").read_text())
    assert old["schema_version"] == "2.6.0"


@pytest.mark.parametrize("version", [None, "2.6"])
def test_default_ai_export_cli_and_explicit_frozen_snapshot(version):
    GENERATED_ROOT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ai06-default-test-", dir=GENERATED_ROOT) as tmp:
        args = ["--profile", "ai-smoke", "--seed", "42", "--end-date", "2026-07-31", "--days", "10", "--products", "3", "--stores", "3", "--warehouses", "2", "--output-root", str(Path(tmp)/"snapshots")]
        if version:
            args.extend(["--source-version",version])
        else:
            args.extend(["--require-use-case", "inventory_source"])
        result = json.loads(cli("data.export.ai_snapshot", args))
        manifest = result["manifest"]
        assert manifest["schema_version"] == ("1.0.0" if version else "1.1.0")
        assert len(manifest["tables"]) == (25 if version else 43)
        assert all(t["data_class"] != "simulation_truth" for t in manifest["tables"])
        if version is None:
            assert manifest["descriptor"]["parent_qualification_id"].startswith("inventory-labels-sha256-")
