from __future__ import annotations

from data.generator.feature_admission import admit_feature_tables
from data.generator.source_quality import project_facts
from ml.features.worker import transform

import copy
import json
import subprocess
import sys
from collections import Counter
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from zipfile import ZipFile

import pytest

from data.generator.configuration import DatasetGenerationConfig, resolve_generation_config
from data.generator.csv_writer import write_tables
from data.generator.demand_panel import build_daily_panel
from data.generator.dimension_quality import timestamp
from data.generator.main import build_dataset, generate_demo_dataset
from data.generator.manifest_v2 import build_source_manifest_v2, load_source_manifest_v2
from data.generator.return_contract import return_contract_schema
from data.generator.return_quality import build_return_report, validate_returns
from data.generator.return_reconciliation import ReturnLedger, legacy_return_projection, return_boundaries
from data.generator.return_schema import RETURN_COLUMNS, RETURN_TAIL_DAYS
from ml.features.demand_forecast import build_demand_feature_rows
from ml.features.identity import load_feature_identity_manifest

ROOT = Path(__file__).resolve().parents[3]
CONFIG = DatasetGenerationConfig(profile="ai-smoke", days=12, products=12, stores=5, warehouses=2)


@pytest.fixture(scope="module")
def dataset():
    return build_dataset(CONFIG)


def test_windows_partial_returns_rejections_and_paid_prices_reconcile(dataset):
    report = validate_returns(dataset, resolve_generation_config(CONFIG))
    assert report["returns_ready"] and not report["inventory_ready"]
    assert len(report["checks"]) == 7 and report["return_tail_days"] == 39
    assert report["history_event_count"] > 0 and report["tail_event_count"] > 0
    items = {r["id"]: r for r in dataset["order_items"]}
    counts = Counter()
    partial, rejected = [], []
    for event in dataset["return_events"]:
        item = items[event["order_item_id"]]
        counts[item["id"]] += int(event["quantity"])
        if int(event["quantity"]) < int(item["quantity"]): partial.append(event)
        if event["status"] == "rejected": rejected.append(event)
        assert Decimal(event["refund_amount"]) == (Decimal(item["unit_price"]) * int(event["quantity"]) if event["status"] == "refunded" else 0)
    assert partial and rejected
    assert all(q <= int(items[i]["quantity"]) for i, q in counts.items())
    assert any(q > 1 for q in Counter(r["order_item_id"] for r in dataset["return_events"]).values())
    fashion = next(r["id"] for r in dataset["catalog_categories"] if r["name"] == "Fashion")
    grocery = next(r["id"] for r in dataset["catalog_categories"] if r["name"] == "Grocery")
    policies = {(r["category_id"],r["channel"]):r for r in dataset["return_policies"]}
    assert policies[fashion,"marketplace"]["window_days"] == "37"
    assert policies[grocery,"store"]["window_days"] == "3"


def test_snapshot_revenue_is_gross_minus_visible_refunds_and_tail_preserves_sales(dataset):
    boundary = timestamp(return_boundaries(resolve_generation_config(CONFIG))["history"])
    events = dataset["return_events"]
    for kind in ("history", "return_tail"):
        rows = [r for r in dataset["daily_return_cohorts"] if r["snapshot_kind"] == kind]
        visible = [r for r in events if r["status"] == "refunded" and (kind == "return_tail" or timestamp(r["available_at"]) <= boundary)]
        gross = sum((Decimal(r["total_amount"]) for r in dataset["sales"]), Decimal(0))
        refund = sum((Decimal(r["refund_amount"]) for r in visible), Decimal(0))
        assert sum(Decimal(r["gross_revenue"]) for r in rows) == gross
        assert sum(Decimal(r["net_revenue"]) for r in rows) == gross - refund
        assert sum(int(r["return_units"]) for r in rows) == sum(int(r["quantity"]) for r in visible)
        assert all(Decimal(r["net_revenue"]) + Decimal(r["refund_amount"]) == Decimal(r["gross_revenue"]) for r in rows)
    assert all(r["return_data_complete"] == "true" for r in dataset["daily_return_cohorts"] if r["snapshot_kind"] == "return_tail")
    assert any(r["return_data_complete"] == "false" for r in dataset["daily_return_cohorts"] if r["snapshot_kind"] == "history")
    assert max(timestamp(r["returned_at"]).date() for r in events) > date(2026,7,31)
    assert max(r["business_date"] for r in dataset["daily_demand_observations"]) == "2026-07-31"
    assert {r["id"] for r in dataset["returns"]} == {r["id"] for r in events if timestamp(r["available_at"]) <= boundary}


def test_occurrence_alone_does_not_make_late_ingestion_known(dataset):
    tables = copy.deepcopy(dataset)
    event = next(r for r in tables["return_events"] if r["status"] == "refunded")
    sale = next(r for r in tables["sales"] if r["id"] == event["sale_id"])
    cutoff = timestamp(sale["sold_at"]) + timedelta(days=1)
    event.update(returned_at=cutoff.isoformat(),ingested_at=(cutoff+timedelta(hours=2)).isoformat(),available_at=(cutoff+timedelta(hours=3)).isoformat())
    tables["return_events"] = [event]
    ledger = ReturnLedger(tables)
    before = ledger.reconcile([sale], cutoff)
    ingested = ledger.reconcile([sale], cutoff+timedelta(hours=2))
    after = ledger.reconcile([sale], cutoff+timedelta(hours=3))
    assert before["return_units"] == ingested["return_units"] == "0"
    assert before["net_revenue"] == sale["total_amount"]
    assert after["return_units"] == event["quantity"]
    assert Decimal(after["net_revenue"]) == Decimal(sale["total_amount"]) - Decimal(event["refund_amount"])
    assert legacy_return_projection(tables,cutoff.isoformat()) == []
    assert len(legacy_return_projection(tables,(cutoff+timedelta(hours=3)).isoformat())) == 1


def test_return_window_deadline_and_availability_cutoff_are_inclusive(dataset):
    tables = copy.deepcopy(dataset)
    event = next(r for r in tables["return_events"] if r["status"] == "refunded")
    sale = next(r for r in tables["sales"] if r["id"] == event["sale_id"])
    policy = next(r for r in tables["return_policies"] if r["id"] == event["policy_id"])
    deadline = timestamp(sale["sold_at"])+timedelta(days=int(policy["window_days"]))
    event.update(returned_at=deadline.isoformat(),ingested_at=deadline.isoformat(),available_at=deadline.isoformat())
    tables["return_events"] = [event]
    assert ReturnLedger(tables).reconcile([sale],deadline)["return_units"] == event["quantity"]
    assert ReturnLedger(tables).reconcile([sale],deadline-timedelta(microseconds=1))["return_units"] == "0"
    check = next(c for c in build_return_report(tables,resolve_generation_config(CONFIG))["checks"] if c["check_id"] == "return_reference_and_window")
    assert check["status"] == "passed"
    event["returned_at"] = (deadline+timedelta(microseconds=1)).isoformat()
    assert next(c for c in build_return_report(tables,resolve_generation_config(CONFIG))["checks"] if c["check_id"] == "return_reference_and_window")["status"] == "failed"


def test_absence_of_return_does_not_imply_mature_zero(dataset):
    tables = copy.deepcopy(dataset)
    tables["return_events"] = []
    sale = tables["sales"][0]
    ledger = ReturnLedger(tables)
    just_sold = ledger.reconcile([sale],timestamp(sale["ingested_at"]))
    final = ledger.reconcile([sale],timestamp(return_boundaries(resolve_generation_config(CONFIG))["return_tail"]))
    assert just_sold["return_units"] == "0" and just_sold["return_data_complete"] == "false"
    assert final["return_units"] == "0" and final["return_data_complete"] == "true"
    with pytest.raises(ValueError,match="Sale unavailable"):
        ledger.reconcile([sale],timestamp(sale["sold_at"])-timedelta(seconds=1))


@pytest.mark.parametrize("mutation,gate", [
    ("sale_before_order","transaction_chronology"), ("sale_ingestion_before_sale","transaction_chronology"),
    ("return_before_sale","return_reference_and_window"), ("outside_window","return_reference_and_window"),
    ("wrong_line","return_reference_and_window"), ("wrong_product","return_reference_and_window"),
    ("wrong_location","return_reference_and_window"), ("wrong_policy","return_reference_and_window"),
    ("late_policy","return_window_policy"), ("zero_quantity","return_quantity_and_refunds"),
    ("over_return","return_quantity_and_refunds"), ("split_over_return","return_quantity_and_refunds"),
    ("wrong_refund","return_quantity_and_refunds"), ("wrong_currency","return_quantity_and_refunds"),
    ("false_net","return_snapshot_reconciliation"), ("leak_tail","return_snapshot_reconciliation"),
    ("false_maturity","return_snapshot_reconciliation"), ("tail_clipped","return_snapshot_reconciliation"),
    ("late_ingestion","return_reference_and_window"), ("non_utc","returns_schema"),
    ("invalid_time","returns_schema"), ("fake_status","returns_schema"), ("duplicate_event","returns_schema"),
    ("missing_cohort","return_tail_completeness"), ("false_tail_complete","return_tail_completeness"),
])
def test_hard_gates_block_malformed_chronology_returns_and_revenue(dataset,mutation,gate):
    tables = copy.deepcopy(dataset)
    event = tables["return_events"][0]
    sale = next(r for r in tables["sales"] if r["id"] == event["sale_id"])
    item = next(r for r in tables["order_items"] if r["id"] == event["order_item_id"])
    order = next(r for r in tables["orders"] if r["id"] == event["order_id"])
    if mutation == "sale_before_order": sale["sold_at"] = (timestamp(order["ordered_at"])-timedelta(seconds=1)).isoformat()
    elif mutation == "sale_ingestion_before_sale": sale["ingested_at"] = (timestamp(sale["sold_at"])-timedelta(seconds=1)).isoformat()
    elif mutation == "return_before_sale": event["returned_at"] = (timestamp(sale["sold_at"])-timedelta(seconds=1)).isoformat()
    elif mutation == "outside_window": event["returned_at"] = (timestamp(sale["sold_at"])+timedelta(days=100)).isoformat()
    elif mutation == "wrong_line": event["order_item_id"] = next(r["id"] for r in tables["order_items"] if r["id"] != item["id"])
    elif mutation == "wrong_product": event["product_id"] = next(r["id"] for r in tables["products"] if r["id"] != item["product_id"])
    elif mutation == "wrong_location": event["selling_location_id"] = next(r["id"] for r in tables["selling_locations"] if r["id"] != event["selling_location_id"])
    elif mutation == "wrong_policy": event["policy_id"] = next(r["id"] for r in tables["return_policies"] if r["id"] != event["policy_id"])
    elif mutation == "late_policy": tables["return_policies"][0]["known_at"] = "2027-01-01T00:00:00+00:00"
    elif mutation == "zero_quantity": event["quantity"] = "0"
    elif mutation == "over_return": event["quantity"] = str(int(item["quantity"])+1)
    elif mutation == "split_over_return": tables["return_events"].append(dict(event,id="00000000-0000-0000-0000-000000000000",quantity=str(int(item["quantity"]))))
    elif mutation == "wrong_refund": event["refund_amount"] = "9999.00"
    elif mutation == "wrong_currency": event["currency"] = "EUR"
    elif mutation == "false_net": tables["daily_return_cohorts"][0]["net_revenue"] = "9999.00"
    elif mutation == "leak_tail": tables["returns"].append(dict(event))
    elif mutation == "false_maturity": next(r for r in tables["daily_return_cohorts"] if r["return_data_complete"] == "false")["return_data_complete"] = "true"
    elif mutation == "tail_clipped":
        late = next(r for r in tables["return_events"] if r["status"] == "refunded" and timestamp(r["available_at"]) > timestamp("2026-08-01T00:00:00+00:00"))
        late.update(returned_at="2026-07-31T23:59:59+00:00",ingested_at="2026-07-31T23:59:59+00:00",available_at="2026-07-31T23:59:59+00:00")
    elif mutation == "late_ingestion": event["available_at"] = (timestamp(event["returned_at"])+timedelta(days=3)).isoformat()
    elif mutation == "non_utc": event["available_at"] = "2026-08-01T12:00:00+02:00"
    elif mutation == "invalid_time": event["available_at"] = "garbage"
    elif mutation == "fake_status": event["status"] = "pending"
    elif mutation == "duplicate_event": tables["return_events"].append(dict(event))
    elif mutation == "missing_cohort": tables["daily_return_cohorts"] = [r for r in tables["daily_return_cohorts"] if r["snapshot_kind"] != "return_tail"]
    elif mutation == "false_tail_complete": next(r for r in tables["daily_return_cohorts"] if r["snapshot_kind"] == "return_tail")["return_data_complete"] = "false"
    report = build_return_report(tables,resolve_generation_config(CONFIG))
    assert next(c for c in report["checks"] if c["check_id"] == gate)["status"] == "failed"
    with pytest.raises(ValueError,match="hard gate"):
        validate_returns(tables,resolve_generation_config(CONFIG))
    with pytest.raises(ValueError):
        admit_feature_tables(tables,CONFIG)


def test_later_events_do_not_rewrite_daily_sales_labels_or_day_close_net(dataset):
    tables = copy.deepcopy(dataset)
    original = build_daily_panel(tables,resolve_generation_config(CONFIG))
    tables["return_events"] = []
    assert build_daily_panel(tables,resolve_generation_config(CONFIG)) == original
    assert all(r["return_units"] == "0" and r["net_revenue"] == r["gross_revenue"] for r in original)


def test_row_order_does_not_change_return_semantics_or_ai_features(dataset):
    reordered = {name:list(reversed(rows)) if name in {*RETURN_COLUMNS,"returns"} else rows for name,rows in dataset.items()}
    assert validate_returns(reordered,resolve_generation_config(CONFIG)) == validate_returns(dataset,resolve_generation_config(CONFIG))
    assert transform(admit_feature_tables(reordered,CONFIG)) == transform(admit_feature_tables(dataset,CONFIG))


def test_empty_closed_history_matures_without_fictitious_returns():
    config = DatasetGenerationConfig(profile="ai-smoke",days=1,products=1,stores=1,warehouses=1,end_date=date(2026,7,5))
    tables = build_dataset(config)
    assert tables["return_events"] == tables["returns"] == []
    assert all(r["gross_revenue"] == r["net_revenue"] == "0.00" and r["return_data_complete"] == "true" for r in tables["daily_return_cohorts"])
    assert validate_returns(tables,resolve_generation_config(config))["status"] == "passed"
    assert not set(RETURN_COLUMNS) & build_dataset(DatasetGenerationConfig()).keys()


def test_export_checks_semantics_even_with_recomputed_hashes_and_schema(tmp_path):
    config = replace(CONFIG,days=3,products=8,stores=3)
    generate_demo_dataset(tmp_path,config)
    source = load_source_manifest_v2(tmp_path)
    assert source["schema_version"] == "2.6.0" and len(source["artifacts"]) == 40
    assert source["descriptor"]["versions"]["returns"] == "retail-returns-1.0.0"
    assert source["watermarks"]["return_events"]["as_of_time"] == "2026-09-09T00:00:00+00:00"
    assert source["watermarks"]["daily_return_cohorts.history"]["as_of_time"] == "2026-08-01T00:00:00+00:00"
    tables = build_dataset(config)
    tables["return_events"][0]["quantity"] = "9999"
    write_tables(tmp_path,tables)
    with pytest.raises(ValueError,match="hard gate"):
        build_source_manifest_v2(config,tables,tmp_path)
    assert json.loads((ROOT/"data/contracts/retail_returns.v1.schema.json").read_text()) == return_contract_schema()


def test_genuine_23_source_features_and_parent_unchanged(tmp_path):
    with ZipFile(Path(__file__).parent/"fixtures/source_manifest_v2_3.zip") as archive:
        for name in archive.namelist():
            assert Path(name).name == name
            (tmp_path/name).write_bytes(archive.read(name))
    source,features = load_source_manifest_v2(tmp_path),load_feature_identity_manifest(tmp_path)
    assert source["schema_version"] == "2.3.0"
    assert source["provenance"]["git_commit"] == "36dca1f48b475f1d77d2f01b95b257cf931c02f7" and source["provenance"]["code_state"] == "clean"
    assert source["dataset_id"] == "source-sha256-f93e0b7c0949fce7e1893f2dff63ef818b3c8fa7989bead422c5febe0a33260d"
    assert features["dataset_id"] == "features-sha256-f813965e89e513871a77ee5e8ca23080faa22dc9efc82e295fd79f90eacd3b20"
    assert features["descriptor"]["parent_ids"] == [source["dataset_id"]]


def test_actual_source_cli_accepts_valid_export_and_rejects_modified_returns(tmp_path):
    config = replace(CONFIG,days=3,products=8,stores=3)
    generate_demo_dataset(tmp_path,config)
    command = [sys.executable,"-m","data.generator.manifest_v2","--data-dir",str(tmp_path)]
    assert subprocess.run(command,cwd=ROOT,capture_output=True,check=False).returncode == 0
    tables = build_dataset(config)
    tables["return_events"][0]["returned_at"] = "2020-01-01T00:00:00+00:00"
    write_tables(tmp_path,tables)
    assert subprocess.run(command,cwd=ROOT,capture_output=True,check=False).returncode == 1
