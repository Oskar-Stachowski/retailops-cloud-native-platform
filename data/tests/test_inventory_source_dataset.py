from __future__ import annotations

import csv
import json
from copy import deepcopy
from pathlib import Path

import pytest

from data.generator.configuration import DatasetGenerationConfig
from data.generator.identity import canonical_json, json_sha256
from data.generator.manifest_v2 import load_source_manifest_v2
from data.inventory.run_source_dataset import build_source_dataset, default_inventory_config
from data.inventory.source_contract import SourceInventoryConfig
from data.inventory.source_dataset_contract import (
    MANIFEST_FILENAME,
    SOURCE_TABLES,
    csv_path,
    grain,
    source_schema,
)
from data.inventory.source_dataset_io import (
    artifact,
    normalize_source,
    read_source_dataset,
    table_identity,
    write_source_dataset,
)
from data.inventory.source_dataset_quality import build_source_report, commerce_view
from data.inventory.source_tables_contract import TABLES
from data.inventory.source_tables_io import _csv_value
from data.generator.configuration import resolve_generation_config
from data.generator.pricing_plans import daily_price_observations


@pytest.fixture(scope="module")
def sample():
    generation = DatasetGenerationConfig(
        profile="ai-smoke", days=10, products=4, stores=3, warehouses=2
    )
    config = default_inventory_config(generation)
    tables, context = build_source_dataset(generation, config)
    return generation, config, normalize_source(tables), context


def publish(sample, root):
    generation, config, tables, context = sample
    return write_source_dataset(tables, context, generation, config, root)


def test_source_contract_schema_is_checked_in():
    path = Path("data/contracts/inventory_source_dataset.v2_7.schema.json")
    assert json.loads(path.read_text()) == source_schema()


def test_full_source_roundtrip_and_legacy_reader_dispatch(sample, tmp_path):
    path = publish(sample, tmp_path)
    tables, manifest = read_source_dataset(path)
    assert tables == sample[2]
    assert load_source_manifest_v2(path) == manifest
    assert manifest["facts_ready"] is True
    assert (
        manifest["source_ready"] is manifest["inventory_ready"] is manifest["model_ready"] is False
    )
    assert set(tables) == set(SOURCE_TABLES)
    assert len(tables) == 58
    for name, entry in manifest["descriptor"]["tables"].items():
        assert manifest["artifacts"][name]["path"].startswith(
            "simulation_truth/" if entry["data_class"] == "simulation_truth" else "facts/"
        )
    assert manifest["inventory_configuration"]["path"].startswith("simulation_truth/")
    report = json.loads((path / "source_report.json").read_text())
    assert len(report["checks"]) == 36
    assert all(r["status"] == "passed" for r in report["checks"])
    assert report["label_qualification"] == "not_evaluated"


def test_repeat_new_directory_has_same_identity_and_table_bytes(sample, tmp_path):
    first = publish(sample, tmp_path / "first")
    second = publish(sample, tmp_path / "second")
    _, a = read_source_dataset(first)
    _, b = read_source_dataset(second)
    assert a["dataset_id"] == b["dataset_id"]
    assert a["descriptor"] == b["descriptor"]
    assert a["artifacts"] == b["artifacts"]
    assert a["reports"] == b["reports"]
    assert publish(sample, tmp_path / "first") == first


@pytest.mark.parametrize(
    "table,field",
    [
        ("sales", "observed_sales"),
        ("inventory_route_versions", "source_version"),
        ("daily_demand_truth", "latent_units"),
        ("inventory_supplier_samples", "lead_days"),
    ],
)
def test_self_resealed_tamper_is_rejected_by_independent_gates(sample, tmp_path, table, field):
    path = publish(sample, tmp_path)
    manifest = json.loads((path / MANIFEST_FILENAME).read_text())
    rows = deepcopy(sample[2][table])
    rows[0][field] = int(rows[0][field]) + 1 if table in TABLES else str(int(rows[0][field]) + 1)
    target = path / csv_path(table)
    with target.open("w", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=manifest["descriptor"]["tables"][table]["columns"],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows({k: _csv_value(v) for k, v in r.items()} for r in rows)
    manifest["artifacts"][table] = artifact(target, path)
    manifest["descriptor"]["tables"][table] = table_identity(table, rows)
    manifest["dataset_id"] = "source-sha256-" + json_sha256(manifest["descriptor"])
    (path / MANIFEST_FILENAME).write_bytes(canonical_json(manifest) + b"\n")
    with pytest.raises(ValueError):
        read_source_dataset(path)


@pytest.mark.parametrize(
    "fault", ["extra_file", "symlink", "truth_placement", "ready_claim", "duplicate_json"]
)
def test_source_allowlists_and_readiness_are_strict(sample, tmp_path, fault):
    path = publish(sample, tmp_path)
    manifest_path = path / MANIFEST_FILENAME
    manifest = json.loads(manifest_path.read_text())
    if fault == "extra_file":
        (path / "surprise.csv").write_text("unsafe\n")
    elif fault == "symlink":
        (path / "alias").symlink_to(path / "source_report.json")
    elif fault == "truth_placement":
        manifest["artifacts"]["inventory_demand_arrivals"]["path"] = (
            "facts/inventory_demand_arrivals.csv"
        )
    elif fault == "ready_claim":
        manifest["inventory_ready"] = True
    else:
        manifest_path.write_text('{"schema_version":"2.7.0",' + manifest_path.read_text()[1:])
    if fault in {"truth_placement", "ready_claim"}:
        manifest_path.write_bytes(canonical_json(manifest) + b"\n")
    with pytest.raises(ValueError):
        load_source_manifest_v2(path)


def test_corrupt_existing_source_is_not_repaired(sample, tmp_path):
    path = publish(sample, tmp_path)
    target = path / csv_path("sales")
    target.write_text(target.read_text() + "broken,row\n")
    before = target.read_bytes()
    with pytest.raises(ValueError):
        publish(sample, tmp_path)
    assert target.read_bytes() == before


@pytest.mark.parametrize("mutation", ["opening", "supplier", "seed"])
def test_configuration_changes_identity_or_fail_bound_gates(sample, tmp_path, mutation):
    generation, config, tables, context = sample
    changed = config.model_dump()
    if mutation == "opening":
        changed["stock"]["opening_quantity"] += 1
    elif mutation == "supplier":
        changed["supplier_parameters"]["reliability"] = "0"
    else:
        changed["fulfillment"]["seed"] += 1
    with pytest.raises(ValueError):
        write_source_dataset(
            tables, context, generation, SourceInventoryConfig.from_payload(changed), tmp_path
        )
    assert not list(tmp_path.glob("source-sha256-*"))


def test_price_projection_uses_causal_availability(sample):
    view = commerce_view(sample[2])
    assert sample[2]["daily_price_observations"] == sorted(
        daily_price_observations(view["sales"], view["sale_price_references"]),
        key=lambda r: tuple(r[f] for f in grain("daily_price_observations")),
    )
    assert any(
        r["ingested_at"] != s["available_at"]
        for r, s in zip(
            sorted(sample[2]["sales"], key=lambda r: r["id"]),
            sorted(sample[2]["inventory_sales"], key=lambda r: r["sale_id"]),
            strict=True,
        )
    )


@pytest.mark.parametrize("case", ["zero_opening", "supplier_poor", "late_sales"])
def test_controlled_configs_keep_readiness_explicit(sample, tmp_path, case):
    generation, config, _, _ = sample
    changed = config.model_dump()
    if case == "zero_opening":
        changed["stock"]["opening_quantity"] = 0
    elif case == "supplier_poor":
        changed["supplier_parameters"]["reliability"] = "0"
        changed["supplier_parameters"]["lead_time_mean_days"] = "5"
    else:
        changed["sale_availability_delay_seconds"] = 86400
    controlled = SourceInventoryConfig.from_payload(changed)
    tables, context = build_source_dataset(generation, controlled)
    path = write_source_dataset(tables, context, generation, controlled, tmp_path)
    _, manifest = read_source_dataset(path)
    assert manifest["facts_ready"] is (case != "late_sales")
    assert (
        manifest["source_ready"] is manifest["inventory_ready"] is manifest["model_ready"] is False
    )


def test_inventory_source_rejects_demo():
    generation = DatasetGenerationConfig(profile="demo")
    with pytest.raises(ValueError, match="requires an AI profile"):
        build_source_dataset(generation, default_inventory_config(generation))


def test_structural_failure_is_not_accepted_as_readiness(sample):
    generation, config, tables, context = sample
    changed = deepcopy(tables)
    changed["sales"][0]["observed_sales"] = "9999"
    report = build_source_report(changed, context, resolve_generation_config(generation), config)
    assert report["status"] == "failed"
    assert report["facts_ready"] is False
