from copy import deepcopy
import importlib.util
import csv
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("cross_repo", Path(__file__).resolve().parents[2] / "scripts/data/verify_ai03_cross_repo.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)
enforce, identity, pinned = gate.enforce, gate.identity, gate.pinned


def accepted():
    return {
        "profile": "controlled-late-fact", "seconds": 299, "peak_rss_mib": 1023,
        "producer": {
            "source_dataset_id": "source", "snapshot_id": "snapshot",
            "hard_gates": 46, "inventory_ready": False,
            "logical_tables": [{"content_sha256": "facts", "grain": ["key"]}],
        },
        "consumer": {
            "source_dataset_id": "source", "snapshot_id": "snapshot",
            "curated_dataset_id": "curated", "quarantine_rows": 0,
            "evaluation_truth_in_curated": False,
            "late_correction": {"status": "passed"},
            "logical_tables": [{"content_sha256": "normalized", "grain": ["key"]}],
        },
    }


@pytest.mark.parametrize("field,value", [("seconds", 301), ("peak_rss_mib", 1025)])
def test_full_pipeline_budget_includes_both_workers(field, value):
    run = accepted()
    enforce(run)
    run[field] = value
    with pytest.raises(ValueError, match="budget_exceeded"):
        enforce(run)


@pytest.mark.parametrize("field,value", [
    ("source_dataset_id", "other"), ("snapshot_id", "other"),
    ("quarantine_rows", 1), ("evaluation_truth_in_curated", True),
    ("late_correction", {"status": "not_present"}),
])
def test_cross_repo_rejects_bad_lineage_quarantine_truth_and_missing_correction(field, value):
    run = accepted()
    run["consumer"][field] = value
    with pytest.raises(ValueError):
        enforce(run)


def test_repeat_checks_values_and_grain_even_when_ids_and_counts_match():
    run = accepted()
    other = deepcopy(run)
    other["consumer"]["logical_tables"][0]["content_sha256"] = "changed"
    assert identity(run) != identity(other)
    other = deepcopy(run)
    other["producer"]["logical_tables"][0]["grain"] = ["other"]
    assert identity(run) != identity(other)


def test_pin_requires_exact_sha_and_clean_tree(monkeypatch, tmp_path):
    revision = "a" * 40
    monkeypatch.setattr(gate, "git", lambda root, *args: revision if args[0] == "rev-parse" else " M file.py")
    with pytest.raises(ValueError, match="dirty_or_unpinned"):
        pinned(tmp_path, revision)
    with pytest.raises(ValueError, match="full_git_sha"):
        pinned(tmp_path, "a" * 7)


def test_controlled_late_fact_is_really_qualified_and_preserves_initial_quantity(tmp_path):
    source = tmp_path / "source"
    probe = gate.late_fact_source(source)
    report = json.loads((source / "source_report.json").read_text())
    assert report["status"] == "passed" and len(report["checks"]) == 46
    with (source / "daily_demand_versions.csv").open() as stream:
        versions = list(csv.DictReader(stream))
    correction = next(row for row in versions if row["version"] == "2")
    initial = next(row for row in versions if row["observation_id"] == correction["observation_id"] and row["version"] == "1")
    assert initial["available_at"] < correction["available_at"] == probe["ingested_at"]
    assert int(initial["observed_units"]) < int(correction["observed_units"])
