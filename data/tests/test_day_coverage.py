"""Explicit closure, finite parent scope, typed source parity and tamper rejection."""

from copy import deepcopy
from datetime import timedelta
from pathlib import Path

import pytest

from data.anomalies.example import example_plan
from data.anomalies.physical_scenarios import physical_example_plan
from data.anomalies.source_process import build_tables
from data.day_coverage.contract import TABLES, schemas
from data.day_coverage.package import build, verify
from data.day_coverage.projection import KEY, days
from data.dq.source import load_source
from data.generator.configuration import DatasetGenerationConfig
from data.generator.identity import file_sha256, json_sha256
from data.inventory.contract import utc_timestamp
from data.inventory.run_source_dataset import default_inventory_config
from data.inventory.source_dataset_io import write_source_dataset


@pytest.fixture(scope="module", params=["demand", "physical"])
def source(request, tmp_path_factory):
    root = tmp_path_factory.mktemp("day-coverage-" + request.param)
    generation = DatasetGenerationConfig(profile="ai-smoke", days=30, products=8, stores=3, warehouses=2)
    config = default_inventory_config(generation)
    plan = (example_plan if request.param == "demand" else physical_example_plan)(generation)
    tables, context = build_tables(generation, plan, config)
    directory = write_source_dataset(tables, context, generation, config, root / "source", scenario_plan=plan)
    tables, manifest = load_source(directory)
    operational = {n: tables[n] for n in TABLES}
    return root, directory, operational, manifest, days(operational, manifest)


def test_schema_registry_is_additive():
    import json
    for name, schema in schemas().items():
        assert json.loads(Path(f"data/day_coverage/contracts/{name}.schema.json").read_bytes()) == schema


def test_unchanged_parent_ids_and_native_claim_tail(source):
    _, directory, tables, manifest, rows = source
    assert directory.name == "source-sha256-" + json_sha256(manifest["descriptor"])
    # General data regressions also cover newer 3.11 patches. The fixture identity
    # is frozen on 3.11.15; only that declared runtime dimension may differ.
    frozen_runtime = {**manifest["descriptor"], "python_version": "3.11.15"}
    assert "source-sha256-" + json_sha256(frozen_runtime) in {
        "source-sha256-3c13e783d52b74bb0955122fd70403eb8f10624acfa11e8b54d587b487cff2fd",
        "source-sha256-be2db97edbb94dfc52d220cdb49c8de7228027eda927a25d982524a875435a09",
    }
    declared = {identifier for r in rows if r["event_type"] == "return_completed" for identifier in r["expected_business_ids"]}
    assert declared == {r["id"] for r in tables["return_events"]}
    assert any(r["business_date"] > "2026-07-31" and r["expected_business_ids"] for r in rows)
    assert all(utc_timestamp(r["known_at"]) >= utc_timestamp(r["window_end"]) for r in rows)


def test_sales_missing_and_closed_are_explicit_and_not_zero(source):
    _, _, _, _, rows = source
    sales = [r for r in rows if r["event_type"] == "sale_completed"]
    assert len(sales) == source[3]["descriptor"]["tables"]["daily_demand_observations"]["row_count"] == 678
    assert any(r["activity"] == "closed" and not r["expected_business_ids"] for r in sales)
    assert any(r["activity"] == "open" and r["source_complete"] and not r["expected_business_ids"] for r in sales)
    modified = deepcopy(source[2])
    observation = modified["daily_demand_observations"][0]
    observation.update(source_data_complete="false", quality_status="incomplete", observation_status="missing")
    projected = days(modified, source[3])
    assert any(r["activity"] == "missing" and not r["source_complete"] for r in projected)


def test_returns_require_original_purchases_and_bounded_ingestion(source):
    _, _, tables, _, rows = source
    purchases = {r["sale_id"]: r for r in tables["inventory_sales"]}
    claims = {r["id"]: r for r in tables["return_events"]}
    for row in rows:
        if row["event_type"] != "return_completed":
            continue
        assert all(utc_timestamp(purchases[i]["sold_at"]) < utc_timestamp(row["window_end"]) for i in row["required_sale_ids"])
        for identifier in row["expected_business_ids"]:
            claim = claims[identifier]
            assert claim["sale_id"] in row["required_sale_ids"]
            assert tuple(claim[k] for k in KEY) == tuple(row[k] for k in KEY)
            assert utc_timestamp(claim["available_at"]) <= utc_timestamp(row["known_at"])
    assert any(not r["expected_business_ids"] for r in rows if r["event_type"] == "return_completed")


@pytest.mark.parametrize("change", ["extra_table", "cohort_flag", "sales_units", "return_delay"])
def test_public_allowlist_and_native_semantics_are_enforced(source, change):
    _, _, tables, manifest, expected = source
    modified = deepcopy(tables)
    if change == "extra_table":
        modified["daily_return_cohorts"] = []
    elif change == "cohort_flag":
        for row in modified["daily_demand_observations"]:
            row["return_data_complete"] = "false" if row["return_data_complete"] == "true" else "true"
        assert days(modified, manifest) == expected
        return
    elif change == "sales_units":
        row = next(r for r in modified["daily_demand_observations"] if r["source_data_complete"] == "true")
        row["observed_units"] = str(int(row["observed_units"]) + 1)
    else:
        row = modified["return_events"][0]
        row["available_at"] = (utc_timestamp(row["available_at"]) + timedelta(days=100)).isoformat()
    with pytest.raises(ValueError):
        days(modified, manifest)


def test_sealed_artifact_is_idempotent_and_modified_rows_are_rejected(source):
    root, directory, _, _, _ = source
    before = {p.relative_to(directory).as_posix(): file_sha256(p) for p in directory.rglob("*") if p.is_file()}
    result = build(directory, root / "coverage")
    artifact = Path(result["directory"])
    assert verify(artifact, directory).coverage_id == result["coverage_id"]
    assert build(directory, root / "coverage")["status"] == "reused"
    assert {p.relative_to(directory).as_posix(): file_sha256(p) for p in directory.rglob("*") if p.is_file()} == before
    path = artifact / "days.jsonl"
    path.write_bytes(path.read_bytes().replace(b'"source_complete":true', b'"source_complete":false', 1))
    with pytest.raises(ValueError, match="days differ"):
        verify(artifact, directory)
