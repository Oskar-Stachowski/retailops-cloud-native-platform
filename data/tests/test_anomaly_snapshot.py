"""Process anomalies survive a versioned, truth-isolated source/snapshot handoff."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

import pytest

from data.anomalies.example import example_plan
from data.anomalies.physical_scenarios import physical_example_plan
from data.anomalies.source_process import build_tables
from data.dq.source import load_source
from data.export.anomaly_contract import FACT_TABLES, GATES
from data.export.inventory_snapshot import export_inventory_snapshot, verify_inventory_snapshot
from data.export.policy import GENERATED_ROOT
from data.generator.configuration import DatasetGenerationConfig
from data.generator.identity import canonical_json, file_sha256
from data.inventory.qualification_io import write_qualification
from data.inventory.run_source_dataset import default_inventory_config
from data.inventory.source_dataset_io import artifact, read_source_dataset, write_source_dataset


def hashes(root):
    return {p.relative_to(root).as_posix(): file_sha256(p) for p in root.rglob("*") if p.is_file()}


@pytest.fixture(scope="module", params=["demand", "physical"])
def sample(request):
    GENERATED_ROOT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ai07-handoff-test-", dir=GENERATED_ROOT) as temporary:
        base = Path(temporary)
        generation = DatasetGenerationConfig(profile="ai-smoke", days=30, products=8, stores=3, warehouses=2)
        config = default_inventory_config(generation)
        plan = (example_plan if request.param == "demand" else physical_example_plan)(generation)
        tables, context = build_tables(generation, plan, config)
        source = write_source_dataset(tables, context, generation, config, base / "sources", scenario_plan=plan)
        qualification = write_qualification(source, base / "qualifications")
        before = hashes(source), hashes(qualification)
        public = export_inventory_snapshot(source, source.name, qualification, base / "public", required_use_cases=("anomaly_source",))
        private = export_inventory_snapshot(source, source.name, qualification, base / "private", include_truth=True, required_use_cases=("anomaly_source",))
        assert before == (hashes(source), hashes(qualification))
        yield base, source, qualification, public, private


def test_versioned_facts_and_explicit_private_plan(sample):
    _, source, _, public, private = sample
    _, parent = read_source_dataset(source)
    assert parent["schema_version"] == "2.8.0" and parent["facts_ready"]
    report = json.loads((source / "source_report.json").read_text())
    assert {c["check_id"] for c in report["checks"]} == set(GATES)
    public_manifest = verify_inventory_snapshot(Path(public["path"]))
    assert public_manifest["schema_version"] == "1.2.0"
    assert [t["table"] for t in public_manifest["tables"]] == list(FACT_TABLES)
    assert not (Path(public["path"]) / "evaluation_truth").exists()
    with pytest.raises(ValueError, match="opt-in"):
        verify_inventory_snapshot(Path(private["path"]))
    private_manifest = verify_inventory_snapshot(Path(private["path"]), allow_evaluation_truth=True)
    assert private_manifest["snapshot_id"] != public_manifest["snapshot_id"]
    assert (Path(private["path"]) / "evaluation_truth/anomaly_scenario.json").is_file()


def test_dq_can_bind_to_anomaly_facts_without_mutating_them(sample):
    source = sample[1]
    before = hashes(source)
    tables, manifest = load_source(source)
    assert manifest["dataset_id"] == source.name and len(tables) == 58
    assert hashes(source) == before


def test_resealed_truth_only_change_is_rejected_by_process_replay(sample, tmp_path):
    root = Path(shutil.copytree(sample[1], tmp_path / "source"))
    private = root / "simulation_truth/anomaly_scenario.json"
    scenario = json.loads(private.read_text())
    scenario["effects"]["episodes"][0]["affected_daily_grains"] += 1
    private.write_bytes(canonical_json(scenario) + b"\n")
    manifest = json.loads((root / "dataset_manifest.v2.json").read_text())
    manifest["scenario"] = artifact(private, root)
    (root / "dataset_manifest.v2.json").write_bytes(canonical_json(manifest) + b"\n")
    with pytest.raises(ValueError, match="truth disagree"):
        read_source_dataset(root)


def test_public_injection_file_is_rejected(sample, tmp_path):
    root = Path(shutil.copytree(sample[3]["path"], tmp_path / "snapshot"))
    (root / "facts/anomaly_injections.json").write_text("{}")
    with pytest.raises(ValueError, match="Extra"):
        verify_inventory_snapshot(root)


def test_chunking_and_republication_preserve_identity(sample):
    base, source, qualification, public, _ = sample
    before = hashes(Path(public["path"]))
    alternate = export_inventory_snapshot(source, source.name, qualification, base / "alternate", chunk_rows=127, required_use_cases=("anomaly_source",))
    assert alternate["manifest"]["snapshot_id"] == public["manifest"]["snapshot_id"]
    repeated = export_inventory_snapshot(source, source.name, qualification, base / "public", required_use_cases=("anomaly_source",))
    assert repeated["publication"] == "reused" and hashes(Path(public["path"])) == before
