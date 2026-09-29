from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from data.generator.configuration import DatasetGenerationConfig
from data.generator.identity import json_sha256
from data.inventory.projection import project_inventory
from data.inventory.projection_contract import ProjectionConfig
from data.inventory.run_source_commerce import run as run_commerce
from data.inventory.run_source_tables import run, validate_parent
from data.inventory.source_tables import normalize_tables, reconcile_tables, tables_from_source
from data.inventory.source_tables_contract import TABLES, table_contract_schema
from data.inventory.source_tables_io import read_tables, table_schema, write_tables
from data.inventory.simulator import ChronologicalSimulator

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "data/tests/fixtures/source-inventory-config-v1.json"


@pytest.fixture(scope="module")
def source():
    return run_commerce(
        DatasetGenerationConfig(profile="ai-smoke", days=10, products=4, stores=3, warehouses=2),
        CONFIG,
    )


@pytest.fixture(scope="module")
def prepared(source):
    settings = source["effective_configuration"]["scenario"]["settings"]
    configuration = ProjectionConfig.from_payload(
        {
            "contract_version": "inventory-projection-config-1.0.0",
            "process_version": "inventory-projection-1.0.0",
            "business_timezone": "UTC",
            "start_at": settings["start_at"],
            "end_at": settings["end_at"],
            "snapshot_policy": "utc_day_last_microsecond",
            "reservation_policy": "none",
            "stock_measure": "available_qty",
            "episode_policy": "zero_after_event_including_instantaneous",
            "diagnostic_horizon_days": 7,
            "truth_delay_seconds": 0,
        }
    )
    projection = project_inventory(
        source["inventory"],
        source["simulation_truth"],
        configuration,
        evaluated_at=configuration.end_at,
    )
    return tables_from_source(source, projection)


def test_schema_is_checked_in_and_table_grains_are_strict(prepared):
    tables, context = prepared
    assert table_contract_schema() == json.loads(
        (ROOT / "data/contracts/inventory_source_tables.v1.schema.json").read_text()
    )
    counts = reconcile_tables(tables, context)
    assert counts["tables"] == 27
    assert counts["operational_tables"] == 19
    assert counts["truth_tables"] == 8
    assert (
        counts["snapshots"]
        == counts["physical_daily_balances"]
        == counts["window_diagnostics"]
        == 80
    )
    assert counts["latent_quantity"] == counts["observed_quantity"] + counts["lost_sales_quantity"]
    for name, definition in TABLES.items():
        assert len({tuple(r[k] for k in definition.grain) for r in tables[name]}) == len(
            tables[name]
        )


def test_native_parquet_types_and_truth_allowlist():
    schema = table_schema("inventory_daily_snapshots")
    assert schema.field("on_hand").type == pa.int64() and schema.field("on_hand").nullable
    assert schema.field("snapshot_at").type == pa.timestamp("us", tz="UTC")
    assert schema.field("business_date").type == pa.date32()
    assert schema.field("is_full_business_day").type == pa.bool_()
    assert table_schema("inventory_sales").field("unit_price").type == pa.decimal128(38, 2)
    assert not table_schema("inventory_ledger").field("quantity_delta").nullable
    for name, definition in TABLES.items():
        if definition.data_class != "simulation_truth":
            assert not set(table_schema(name).names) & {
                "latent_quantity",
                "lost_sales_quantity",
                "stock_before",
                "incident_stockout",
                "lead_days",
                "disrupted",
            }


def test_csv_parquet_roundtrip_repeat_and_reuse_are_identical(prepared, source, tmp_path):
    tables, context = prepared
    first = write_tables(tables, context, tmp_path / "first", source["execution_id"])
    restored, receipt, restored_context = read_tables(first)
    second = write_tables(tables, context, tmp_path / "second", source["execution_id"])
    repeated, repeated_receipt, _ = read_tables(second)
    assert tables == restored == repeated
    assert context == restored_context
    assert receipt == repeated_receipt
    assert first.name == second.name
    before = {
        p.relative_to(first).as_posix(): p.read_bytes() for p in first.rglob("*") if p.is_file()
    }
    assert write_tables(tables, context, tmp_path / "first", source["execution_id"]) == first
    assert before == {
        p.relative_to(first).as_posix(): p.read_bytes() for p in first.rglob("*") if p.is_file()
    }
    assert all(receipt[k] is False for k in ("source_ready", "inventory_ready", "model_ready"))
    assert len(before) == 55


@pytest.mark.parametrize(
    "case",
    [
        "opening_duplicate",
        "missing_issue",
        "negative_opening",
        "sale_quantity",
        "sales_location",
        "missing_arrival",
        "duplicate_demand",
        "lost_quantity",
        "snapshot_quantity",
        "missing_snapshot",
        "physical_balance",
        "episode_duration",
        "lost_impact",
        "premature_label",
        "missing_supplier",
        "over_receipt",
        "tail_in_history",
        "tail_duplicate_receipt",
        "missing_future_receipt",
        "supplier_sample",
        "missing_return_decision",
        "wrong_disposition",
        "route_revision",
        "wrong_rule_scope",
        "coverage_outside_window",
        "integer_is_bool",
        "extra_table",
        "extra_column",
    ],
)
def test_semantic_mutations_fail_before_publication(case, prepared, tmp_path):
    tables, context = prepared
    tables = copy.deepcopy(tables)
    if case == "opening_duplicate":
        tables["inventory_ledger"].append(tables["inventory_ledger"][0])
    elif case == "missing_issue":
        row = next(r for r in tables["inventory_ledger"] if r["movement_type"] == "sale")
        tables["inventory_ledger"].remove(row)
    elif case == "negative_opening":
        next(r for r in tables["inventory_ledger"] if r["movement_type"] == "opening_stock")[
            "quantity_delta"
        ] = -1
    elif case == "sale_quantity":
        tables["inventory_sales"][0]["quantity"] += 1
    elif case == "sales_location":
        tables["inventory_sales"][0]["stock_location_id"] = "00000000-0000-0000-0000-000000000000"
    elif case == "missing_arrival":
        tables["inventory_demand_arrivals"].pop()
    elif case == "duplicate_demand":
        tables["inventory_demand_outcomes"].append(tables["inventory_demand_outcomes"][0])
    elif case == "lost_quantity":
        tables["inventory_demand_outcomes"][0]["lost_sales_quantity"] += 1
    elif case == "snapshot_quantity":
        tables["inventory_daily_snapshots"][0]["on_hand"] += 1
    elif case == "missing_snapshot":
        tables["inventory_daily_snapshots"].pop()
    elif case == "physical_balance":
        tables["inventory_physical_daily_balances"][0]["closing_quantity"] += 1
    elif case == "episode_duration":
        tables["stockout_episodes"][0]["duration_microseconds"] += 1
    elif case == "lost_impact":
        tables["inventory_lost_sales_impacts"].pop()
    elif case == "premature_label":
        next(
            r for r in tables["inventory_window_diagnostics"] if r["reason"] == "incomplete_window"
        )["incident_stockout"] = 0
    elif case == "missing_supplier":
        tables["suppliers"].clear()
    elif case == "over_receipt":
        tables["replenishment_receipts"][0]["received_quantity"] += 1000
    elif case == "tail_in_history":
        tables["inventory_scheduled_receipt_tail"][0]["received_at"] = context.opening_at
    elif case == "tail_duplicate_receipt":
        tables["inventory_scheduled_receipt_tail"].append(tables["replenishment_receipts"][0])
    elif case == "missing_future_receipt":
        tables["inventory_scheduled_receipt_tail"].pop()
    elif case == "supplier_sample":
        tables["inventory_supplier_samples"].pop()
    elif case == "missing_return_decision":
        tables["return_inventory_decisions"].pop()
    elif case == "wrong_disposition":
        row = tables["return_inventory_decisions"][0]
        row["inventory_disposition"] = (
            "restocked" if row["inventory_disposition"] != "restocked" else "not_refunded"
        )
    elif case == "route_revision":
        tables["inventory_route_versions"][0]["inventory_revision"] += 1
    elif case == "wrong_rule_scope":
        tables["inventory_reorder_rules"].pop()
    elif case == "coverage_outside_window":
        tables["inventory_history_coverage"][0]["covered_through_at"] = "2099-01-01T00:00:00+00:00"
    elif case == "integer_is_bool":
        tables["inventory_sales"][0]["quantity"] = True
    elif case == "extra_table":
        tables["supplier_reliability_features"] = []
    elif case == "extra_column":
        tables["inventory_sales"][0]["latent_quantity"] = 2
    with pytest.raises(ValueError):
        write_tables(tables, context, tmp_path, "source-inventory-candidate-sha256-" + "a" * 64)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(
    "case",
    [
        "csv_corruption",
        "parquet_schema",
        "extra_file",
        "truth_reclassification",
        "false_readiness",
        "wrong_identity",
        "path_escape",
        "context_cutoff",
        "symlink",
    ],
)
def test_reader_rejects_corruption_and_reuse_does_not_repair(case, prepared, source, tmp_path):
    tables, context = prepared
    directory = write_tables(tables, context, tmp_path, source["execution_id"])
    manifest = directory / "tables.json"
    receipt = json.loads(manifest.read_text())
    if case == "csv_corruption":
        with (directory / receipt["tables"]["inventory_sales"]["csv_path"]).open("a") as stream:
            stream.write("corruption\n")
    elif case == "parquet_schema":
        path = directory / receipt["tables"]["inventory_sales"]["parquet_path"]
        pq.write_table(pa.table({"sale_id": ["wrong"]}), path)
    elif case == "extra_file":
        (directory / "facts/private_supplier_truth.json").write_text("{}")
    elif case == "truth_reclassification":
        receipt["tables"]["stockout_episodes"]["data_class"] = "source_observation"
    elif case == "false_readiness":
        receipt["inventory_ready"] = True
    elif case == "wrong_identity":
        receipt["candidate_id"] = "inventory-tables-candidate-sha256-" + "a" * 64
    elif case == "path_escape":
        receipt["tables"]["inventory_sales"]["csv_path"] = "../../private.csv"
    elif case == "context_cutoff":
        receipt["context"]["evaluated_at"] = "2099-01-01T00:00:00+00:00"
    elif case == "symlink":
        (directory / "alias").symlink_to(directory / "facts", target_is_directory=True)
    manifest.write_text(json.dumps(receipt))
    before = manifest.read_bytes()
    with pytest.raises(ValueError):
        read_tables(directory)
    with pytest.raises(ValueError):
        write_tables(tables, context, tmp_path, source["execution_id"])
    assert manifest.read_bytes() == before


@pytest.mark.parametrize("case", ["facts_hash", "truth_hash", "execution_id", "false_readiness"])
def test_parent_receipt_integrity(case, source):
    changed = copy.deepcopy(source)
    if case == "facts_hash":
        changed["inventory_snapshots"][0]["on_hand"] += 1
    elif case == "truth_hash":
        changed["simulation_truth"]["demand_outcomes"][0]["latent_quantity"] += 1
    elif case == "execution_id":
        changed["generation_configuration"]["seed"] += 1
    else:
        changed["source_ready"] = True
    with pytest.raises(ValueError):
        validate_parent(changed)


def test_cli_reconciles_roundtrip_without_promoting_source_readiness(source, tmp_path):
    candidate, output = tmp_path / "parent.json", tmp_path / "receipt.json"
    candidate.write_text(json.dumps(source))
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "data.inventory.run_source_tables",
            "--candidate",
            str(candidate),
            "--output-root",
            str(tmp_path / "tables"),
            "--output",
            str(output),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    receipt = json.loads(output.read_text())
    assert (
        receipt["status"] == "passed"
        and receipt["lifecycle_label_qualification"] == "not_evaluated"
    )
    assert receipt["parent_execution_id"] == source["execution_id"]
    assert all(receipt[k] is False for k in ("inventory_ready", "source_ready", "model_ready"))
    tables, _, _ = read_tables(Path(receipt["directory"]))
    assert tables == normalize_tables(tables)


def test_parent_and_native_data_are_immutable(prepared, source, tmp_path):
    tables, context = prepared
    before = json_sha256({"tables": tables, "source": source})
    write_tables(tables, context, tmp_path, source["execution_id"])
    assert json_sha256({"tables": tables, "source": source}) == before


@pytest.mark.parametrize("opening", [12, 0])
def test_no_demand_and_zero_opening_preserve_empty_native_tables(
    opening, source, prepared, tmp_path
):
    inputs = copy.deepcopy(source["effective_configuration"])
    arrival = copy.deepcopy(inputs["scenario"]["demand_arrivals"][0])
    arrival["latent_quantity"] = 0
    inputs["scenario"]["demand_arrivals"] = [arrival]
    for row in inputs["inventory"]["movements"]:
        row["quantity_delta"] = opening
    parent = ChronologicalSimulator(
        inputs["inventory"],
        inputs["supply"],
        inputs["scenario"],
        inputs["policy"],
        inputs["fulfillment"],
        inputs["truth"],
    ).execute()
    parent["operational"]["source_route_versions"] = inputs["source_route_versions"]
    configuration = prepared[1].projection
    projection = project_inventory(
        parent["operational"],
        parent["simulation_truth"],
        configuration,
        evaluated_at=configuration.end_at,
    )
    controlled = {
        "inventory": parent["operational"],
        "simulation_truth": parent["simulation_truth"],
        "effective_configuration": inputs,
        "commerce": {"return_events": []},
        "return_inventory_decisions": [],
    }
    tables, context = tables_from_source(controlled, projection)
    directory = write_tables(tables, context, tmp_path, source["execution_id"])
    restored, _, _ = read_tables(directory)
    assert restored == tables
    assert not restored["inventory_sales"] and not restored["inventory_returns"]
    assert not restored["inventory_lost_sales_impacts"]
    assert restored["inventory_demand_outcomes"][0]["reason"] == "no_demand"
    assert restored["inventory_demand_outcomes"][0]["latent_quantity"] == 0
    episodes = restored["stockout_episodes"]
    assert (len(episodes) == 8) if opening == 0 else (len(episodes) == 0)
    assert not any(r["lost_sales_quantity"] for r in episodes)
    assert pq.ParquetFile(directory / "facts/inventory_sales.parquet").schema_arrow.equals(
        table_schema("inventory_sales"), check_metadata=True
    )
