"""Complete native parity of both closed planned Source 2.8 processes."""

from copy import deepcopy
import gc
import json
from pathlib import Path
import tempfile
import weakref

import pytest

from data.anomalies.example import example_plan
from data.anomalies.physical_scenarios import physical_example_plan
from data.anomalies import source_cohort as cached
from data.anomalies.source_process import build_tables as ordinary_build
from data.export.inventory_snapshot import export_inventory_snapshot, verify_inventory_snapshot
from data.export.policy import GENERATED_ROOT
from data.generator.configuration import DatasetGenerationConfig, resolve_generation_config
from data.generator.identity import canonical_json
from data.generator.main import build_dataset
from data.inventory.qualification_io import write_qualification
from data.inventory.run_source_dataset import default_inventory_config
from data.inventory.source_dataset_contract import SOURCE_TABLES, csv_path
from data.inventory.source_dataset_io import normalize_source, read_source_dataset, write_source_dataset


@pytest.fixture(scope="module", params=[(kind, seed) for kind in ("demand", "physical") for seed in (42, 137, 2026)])
def case(request):
    kind, seed = request.param
    generation = DatasetGenerationConfig(
        profile="ai-smoke", days=30, products=8, stores=3, warehouses=2,
        seed=seed, forecast_plan_days=14,
    )
    payload = (example_plan if kind == "demand" else physical_example_plan)(generation)
    original = deepcopy(payload)
    config = default_inventory_config(generation)
    expected, expected_context = ordinary_build(generation, payload, config)
    actual, actual_context = cached.build_tables(generation, payload, config)
    assert payload == original
    return {
        "kind": kind, "seed": seed, "generation": generation, "payload": payload, "config": config,
        "expected": normalize_source(expected), "expected_context": expected_context,
        "actual": normalize_source(actual), "actual_context": actual_context,
    }


def test_all_58_tables_and_context_match_original_for_all_three_seeds(case):
    assert case["actual_context"] == case["expected_context"]
    assert set(case["actual"]) == set(SOURCE_TABLES)
    assert len(case["actual"]) == 58
    assert case["actual"] == case["expected"]
    for name in SOURCE_TABLES:
        assert canonical_json(case["actual"][name]) == canonical_json(case["expected"][name])


def test_ordinary_publication_csv_and_complete_independent_plan_replay(case, tmp_path):
    paths = []
    for label in ("expected", "actual"):
        paths.append(write_source_dataset(
            case[label], case[label + "_context"], case["generation"], case["config"],
            tmp_path / label, scenario_plan=case["payload"],
        ))
    restored, manifest = read_source_dataset(paths[1])
    assert restored == case["expected"]
    assert manifest["schema_version"] == "2.8.0" and manifest["facts_ready"] is True
    assert manifest["descriptor"]["resolved_parameters"]["forecast_plan_days"] == 14
    for name in SOURCE_TABLES:
        assert (paths[0] / csv_path(name)).read_bytes() == (paths[1] / csv_path(name)).read_bytes()
    assert (paths[0] / "source_report.json").read_bytes() == (paths[1] / "source_report.json").read_bytes()
    report = json.loads((paths[1] / "source_report.json").read_text())
    assert len(report["checks"]) == 38 and all(c["status"] == "passed" for c in report["checks"])


def test_cached_planned_native_snapshot_is_1_2_and_has_no_evaluation_truth(case):
    GENERATED_ROOT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="cached-planned-control-", dir=GENERATED_ROOT) as temporary:
        root = Path(temporary)
        source = write_source_dataset(
            case["actual"], case["actual_context"], case["generation"], case["config"],
            root / "raw", scenario_plan=case["payload"],
        )
        qualification = write_qualification(source, root / "qualification")
        result = export_inventory_snapshot(
            source, source.name, qualification, root / "snapshots",
            required_use_cases=("forecast_source", "inventory_source", "anomaly_source"),
        )
        destination = Path(result["path"])
        manifest = verify_inventory_snapshot(destination)
        assert manifest["schema_version"] == "1.2.0"
        assert manifest["source"]["descriptor"]["resolved_parameters"]["forecast_plan_days"] == 14
        assert not (destination / "evaluation_truth").exists()
        for name, original in (
            ("anomaly_snapshot.v1_2.schema.json", "anomaly_snapshot.v1_2.forecast.schema.json"),
            ("anomaly_source_dataset.v2_8.schema.json", "anomaly_source_dataset.v2_8.forecast.schema.json"),
        ):
            assert (destination / "schemas" / name).read_bytes() == (Path("data/contracts") / original).read_bytes()


@pytest.mark.parametrize("kind", ["demand", "physical"])
def test_inputs_are_detached_and_full_physical_scenario_is_retained_when_events_expire(kind, monkeypatch):
    generation = DatasetGenerationConfig(
        profile="ai-smoke", days=30, products=8, stores=3, warehouses=2, seed=42,
        forecast_plan_days=14,
    )
    payload = (example_plan if kind == "demand" else physical_example_plan)(generation)
    plan = cached.parse_candidate_plan(payload)
    demand = plan if isinstance(plan, cached.AnomalyPlan) else None
    physical = plan if isinstance(plan, cached.PhysicalAnomalyPlan) else None
    candidate = build_dataset(generation, anomaly_plan=demand)
    original = deepcopy(candidate)
    effective = resolve_generation_config(generation)
    config = default_inventory_config(generation)
    captured = {}
    original_execute = cached.CachedPlannedSimulator.execute

    def execute(simulator):
        captured["before"] = simulator.scenario.model_dump()
        refs = [weakref.ref(row) for _, _, _, kind, row in simulator.queue if kind != "review"]
        captured["queued_rows"] = len(refs)
        result = original_execute(simulator)
        gc.collect()
        captured["retained_typed_rows"] = sum(ref() is not None for ref in refs)
        return result

    monkeypatch.setattr(cached.CachedPlannedSimulator, "execute", execute)
    result = cached.simulate_planned_source(candidate, effective, config, anomaly_plan=demand, physical_plan=physical)
    assert candidate == original
    assert captured["queued_rows"] > 0 and captured["retained_typed_rows"] == 0
    assert result["effective_configuration"]["scenario"] == captured["before"]
    assert result["effective_configuration"]["scenario"]["demand_arrivals"]
    if physical is not None:
        assert result["simulation_truth"]["physical_interventions"]
        assert all(row["sequence"] % 2 == 1 for row in captured["before"]["demand_arrivals"])
    result["commerce"]["product_catalog"][0]["name"] = "changed output only"
    assert candidate == original


def test_unreviewed_upstream_is_rejected_before_source_generation(monkeypatch):
    monkeypatch.setitem(cached.UPSTREAM_SHA256, "anomalies/physical_process.py", "0" * 64)
    with pytest.raises(ValueError, match="upstream changed"):
        cached.verify_upstream_pins()
