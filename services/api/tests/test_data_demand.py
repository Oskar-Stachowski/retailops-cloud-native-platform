from __future__ import annotations

import copy
import json
import random
from collections import Counter, defaultdict
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from zipfile import ZipFile

import pytest

from data.generator.configuration import DatasetGenerationConfig, resolve_generation_config
from data.generator.csv_writer import write_tables
from data.generator.demand_commerce import allocate_baskets
from data.generator.demand_contract import demand_contract_schema
from data.generator.demand_model import FACTOR_FIELDS, expected_demand, sample_units
from data.generator.demand_panel import build_daily_panel
from data.generator.demand_quality import build_demand_report, validate_demand
from data.generator.demand_schema import DEMAND_COLUMNS, DEMAND_GRAIN
from data.generator.main import build_dataset, generate_demo_dataset
from data.generator.manifest_v2 import build_source_manifest_v2, load_source_manifest_v2
from ml.features.ai_demand import AI_FEATURE_COLUMNS, ai_feature_rows, calendar_lag, validate_ai_records
from ml.features.demand_forecast import DemandFeatureGenerationConfig, build_demand_feature_rows, build_feature_manifest, generate_demand_feature_dataset
from ml.features.identity import load_feature_identity_manifest

ROOT = Path(__file__).resolve().parents[3]
CONFIG = DatasetGenerationConfig(profile="ai-smoke", days=12, products=12, stores=5, warehouses=2)


@pytest.fixture(scope="module")
def dataset():
    return build_dataset(CONFIG)


def key(row):
    return tuple(row[name] for name in DEMAND_GRAIN)


def test_full_valid_panel_zeros_closed_and_inactive_are_distinct(dataset):
    report = validate_demand(dataset, resolve_generation_config(CONFIG))
    assert report["complete_daily_panel"] and report["daily_panel_coverage_percent"] == 100
    assert report["valid_daily_combinations"] + report["inactive_combinations"] == 720
    assert report["inventory_ready"] is report["returns_ready"] is False
    assert len(report["checks"]) == 6
    assert set(report["observation_status_counts"]) == {"observed_positive", "observed_zero", "closed"}
    assert all(r["observed_units"] == "0" and r["observed_orders"] == "0" and r["gross_revenue"] == "0.00" for r in dataset["daily_demand_observations"] if r["observation_status"] in {"observed_zero", "closed"})
    assert {key(r) for r in dataset["daily_demand_observations"]}.isdisjoint({key(r) for r in dataset["daily_demand_exclusions"]})
    assert {r["observation_status"] for r in dataset["daily_demand_exclusions"]} == {"inactive"}
    assert all(r["net_revenue"] == r["return_units"] == "" and r["return_data_complete"] == "false" for r in dataset["daily_demand_observations"])


def test_demand_weight_acts_once_and_stochastic_rounding_allows_zero():
    factors = dict.fromkeys(FACTOR_FIELDS, "1")
    factors.update(base_rate="2", product_factor="3", location_factor="0.5")
    assert expected_demand(factors) == Decimal(3)
    factors["product_factor"] = "6"
    assert expected_demand(factors) == Decimal(6)
    assert sample_units(Decimal("0.2"), Decimal("0.3")) == 0
    assert sample_units(Decimal("0.2"), Decimal("0.1")) == 1
    assert sample_units(Decimal("3.2"), Decimal("0.2")) == 3
    assert sample_units(Decimal(0), Decimal(0)) == 0


@pytest.mark.parametrize("rate,draw", [("-1", "0"), ("NaN", "0"), ("1", "1"), ("1", "-0.1")])
def test_invalid_sampling_is_rejected(rate, draw):
    with pytest.raises(ValueError):
        sample_units(Decimal(rate), Decimal(draw))


@pytest.mark.parametrize("seed", list(range(10)))
def test_basket_allocation_conserves_budgets_without_replacement(seed):
    budgets = {"p0": 15, "p1": 17, "p2": 11, "p3": 0, "p4": 13, "p5": 8}
    categories = dict.fromkeys(budgets, "Electronics")
    first = allocate_baskets(budgets, categories, "online", random.Random(seed))
    assert first == allocate_baskets(budgets, categories, "online", random.Random(seed))
    counts = Counter()
    for basket in first:
        assert len({p for p, q in basket}) == len(basket)
        assert all(q > 0 for p, q in basket)
        counts.update({p: q for p, q in basket})
    assert counts == Counter(budgets)
    assert budgets["p0"] == 15


def test_complementary_candidates_are_sampled_across_products():
    budgets = {"anchor": 100, **dict.fromkeys(["a", "b", "c", "d"], 20)}
    categories = {"anchor": "Fashion", **dict.fromkeys(["a", "b", "c", "d"], "Beauty")}
    companions = set()
    for seed in range(15):
        baskets = allocate_baskets(budgets, categories, "online", random.Random(seed))
        for basket in baskets:
            if basket[0][0] == "anchor":
                companions.update(p for p, q in basket[1:])
    assert companions == {"a", "b", "c", "d"}


def test_actual_transactions_reconcile_to_daily_budget_and_unique_skus(dataset):
    refs = {r["sale_id"]: r for r in dataset["sale_price_references"]}
    units, revenue, orders = Counter(), defaultdict(Decimal), defaultdict(set)
    for sale in dataset["sales"]:
        k = key(refs[sale["id"]])
        units[k] += int(sale["quantity"])
        revenue[k] += Decimal(sale["total_amount"])
        orders[k].add(sale["order_reference"])
        assert sale["latent_demand"] == sale["demand_noise"] == sale["stockout_flag"] == ""
    for row in dataset["daily_demand_observations"]:
        k = key(row)
        assert int(row["observed_units"]) == units[k]
        assert Decimal(row["gross_revenue"]) == revenue[k]
        assert int(row["observed_orders"]) == len(orders[k])
    for row in dataset["daily_demand_truth"]:
        assert int(row["latent_units"]) == units[key(row)]
        assert Decimal(row["expected_rate"]) == expected_demand(row)


@pytest.mark.parametrize("mutation,check", [
    ("remove_day", "daily_panel_coverage"), ("duplicate_day", "daily_panel_coverage"),
    ("fake_units", "daily_transaction_aggregation"), ("fake_closed", "daily_transaction_aggregation"),
    ("fake_availability", "daily_transaction_aggregation"), ("drop_exclusion", "daily_panel_coverage"),
    ("repeated_sku", "basket_sku_totals"), ("wrong_order_total", "basket_sku_totals"),
    ("doubled_weight", "daily_demand_budget"), ("invented_net", "daily_source_completeness"),
])
def test_demand_hard_gates_reject_broken_data(dataset, mutation, check):
    tables = copy.deepcopy(dataset)
    panel = tables["daily_demand_observations"]
    if mutation == "remove_day": panel.pop()
    elif mutation == "duplicate_day": panel.append(dict(panel[0]))
    elif mutation == "fake_units": panel[0]["observed_units"] = "999999"
    elif mutation == "fake_closed": panel[0]["location_open"] = "false"
    elif mutation == "fake_availability": panel[0]["available_at"] = "2027-01-01T00:00:00+00:00"
    elif mutation == "drop_exclusion": tables["daily_demand_exclusions"].pop()
    elif mutation == "repeated_sku": tables["order_items"].append(dict(tables["order_items"][0], id="bad-duplicate"))
    elif mutation == "wrong_order_total": tables["orders"][0]["order_total"] = "0.00"
    elif mutation == "doubled_weight": tables["daily_demand_truth"][0]["product_factor"] = "999"
    elif mutation == "invented_net": panel[0]["net_revenue"] = panel[0]["gross_revenue"]
    report = build_demand_report(tables, resolve_generation_config(CONFIG))
    assert next(c for c in report["checks"] if c["check_id"] == check)["status"] == "failed"
    with pytest.raises(ValueError, match="hard gate"):
        validate_demand(tables, resolve_generation_config(CONFIG))


def test_missing_window_stays_null_and_blocks_complete_export(dataset):
    tables = copy.deepcopy(dataset)
    zero = next(r for r in tables["daily_demand_observations"] if r["observation_status"] == "observed_zero")
    tables["daily_demand_observations"] = build_daily_panel(tables, resolve_generation_config(CONFIG), missing_keys=frozenset([key(zero)]))
    missing = next(r for r in tables["daily_demand_observations"] if r["observation_status"] == "missing")
    assert missing["observed_units"] == missing["gross_revenue"] == ""
    features = ai_feature_rows(tables["daily_demand_observations"], tables["product_catalog"], tables["catalog_categories"])
    row = next(r for r in features if r["observation_status"] == "missing")
    assert row["units_sold"] is None and row["source_data_complete"] is False
    with pytest.raises(ValueError, match="daily_source_completeness"):
        validate_demand(tables, resolve_generation_config(CONFIG))


def test_feature_rows_use_physical_grain_and_no_truth_inventory_revenue(dataset):
    rows = build_demand_feature_rows(dataset, CONFIG)
    manifest = build_feature_manifest(CONFIG, rows)
    assert len(rows) == len(dataset["daily_demand_observations"])
    assert all(set(r) == set(AI_FEATURE_COLUMNS) for r in rows)
    assert manifest["schema_version"] == "3.0" and manifest["complete_daily_panel"]
    assert manifest["target_type"] == "observed_sales_units"
    assert manifest["grain"] == ["date", "product_id", "selling_location_id", "channel"]
    assert not {"stock_quantity", "latent_units", "expected_rate", "gross_revenue", "realized_unit_price", "promotion_factor"} & set(AI_FEATURE_COLUMNS)
    selling = {r["id"] for r in dataset["selling_locations"]}
    assert all(r["selling_location_id"] in selling for r in rows)
    with pytest.raises(ValueError, match="allowlist"):
        ai_feature_rows([dict(dataset["daily_demand_observations"][0], noise="1")], dataset["product_catalog"], dataset["catalog_categories"])
    schema = json.loads((ROOT/"ml/contracts/demand_forecast_features.v3.schema.json").read_text())
    assert set(schema["properties"]) == set(AI_FEATURE_COLUMNS)


def test_calendar_lag_does_not_use_previous_sparse_row_or_late_data():
    series = ("p", "l", "online")
    rows = [{"date": "2026-07-08", "product_id":"p", "selling_location_id":"l", "channel":"online", "observation_status":"observed_positive", "units_sold":8, "source_data_complete":True, "observation_available_at":"2026-07-09T00:00:00+00:00"}, {"date":"2026-07-10", "product_id":"p", "selling_location_id":"l", "channel":"online", "observation_status":"observed_zero", "units_sold":0, "source_data_complete":True, "observation_available_at":"2026-07-11T00:00:00+00:00"}]
    assert calendar_lag(rows, series, date(2026,7,12), 1) == 0
    assert calendar_lag(rows, series, date(2026,7,12), 2) is None
    assert calendar_lag(rows, series, date(2026,7,12), 3) == 8
    rows[1]["observation_available_at"] = "2026-07-11T23:59:59.000001+00:00"
    assert calendar_lag(rows, series, date(2026,7,12), 1) is None
    rows[0]["observation_status"] = "closed"
    assert calendar_lag(rows, series, date(2026,7,12), 3) is None


def test_export_semantic_checks_cannot_be_bypassed_by_recomputed_hashes(tmp_path):
    config = replace(CONFIG, days=3, products=8, stores=3)
    generate_demo_dataset(tmp_path, config)
    source = load_source_manifest_v2(tmp_path)
    assert source["schema_version"] == "2.3.0" and len(source["artifacts"]) == 34
    assert source["watermarks"]["daily_demand_observations"]["complete_through"] == "2026-07-31"
    tables = build_dataset(config)
    tables["daily_demand_observations"].pop()
    write_tables(tmp_path, tables)
    with pytest.raises(ValueError, match="daily_panel_coverage"):
        build_source_manifest_v2(config, tables, tmp_path)


def test_genuine_22_archive_and_feature_parent_remain_unchanged(tmp_path):
    with ZipFile(Path(__file__).parent/"fixtures/source_manifest_v2_2.zip") as fixture:
        for name in fixture.namelist():
            assert Path(name).name == name
            (tmp_path/name).write_bytes(fixture.read(name))
    source, feature = load_source_manifest_v2(tmp_path), load_feature_identity_manifest(tmp_path)
    assert source["schema_version"] == "2.2.0"
    assert source["dataset_id"] == "source-sha256-b8d99ab8e08f59d344be2cc42599e138b80f31d213cca4a89ddc1688e334135b"
    assert feature["dataset_id"] == "features-sha256-3b61cd73d4e27488b767004d6a4fa90a66f58a9591541f85920a67ade27db1f0"
    assert feature["descriptor"]["parent_ids"] == [source["dataset_id"]]


def test_demand_schema_and_minimal_closed_profile():
    assert json.loads((ROOT/"data/contracts/retail_demand.v1.schema.json").read_text()) == demand_contract_schema()
    config = DatasetGenerationConfig(profile="ai-smoke",days=1,products=1,stores=1,warehouses=1,end_date=date(2026,7,5))
    tables = build_dataset(config)
    assert not tables["sales"] and not tables["daily_demand_truth"]
    assert tables["daily_demand_observations"][0]["observation_status"] == "closed"
    assert validate_demand(tables, resolve_generation_config(config))["status"] == "passed"
    assert not set(DEMAND_COLUMNS) & set(build_dataset(DatasetGenerationConfig()))


def test_ai_feature_export_is_verified_and_not_silently_legacy(tmp_path):
    config = replace(CONFIG, days=3, products=8, stores=3)
    manifest = generate_demand_feature_dataset(DemandFeatureGenerationConfig(config,tmp_path))
    identity = load_feature_identity_manifest(tmp_path)
    assert identity["descriptor"]["schema_version"] == manifest["schema_version"] == "3.0"
    assert identity["complete_daily_panel"] is True
    assert identity["readiness"] == "not_ready"


@pytest.mark.parametrize("mutation", ["negative_label", "fake_status", "fake_calendar", "fake_flag", "duplicate"])
def test_ai_feature_semantics_reject_malformed_records(dataset, mutation):
    rows = ai_feature_rows(dataset["daily_demand_observations"], dataset["product_catalog"], dataset["catalog_categories"])
    if mutation == "negative_label": rows[0]["units_sold"] = -1
    elif mutation == "fake_status": rows[0]["observation_status"] = "unknown"
    elif mutation == "fake_calendar": rows[0]["month"] = 99
    elif mutation == "fake_flag": rows[0]["source_data_complete"] = "false"
    elif mutation == "duplicate": rows.append(dict(rows[0]))
    with pytest.raises(ValueError):
        validate_ai_records(rows)


def test_late_fact_after_declared_snapshot_cannot_claim_completeness(dataset):
    tables = copy.deepcopy(dataset)
    tables["sales"][0]["ingested_at"] = "2026-08-01T00:00:00.000001+00:00"
    tables["daily_demand_observations"] = build_daily_panel(tables, resolve_generation_config(CONFIG))
    report = build_demand_report(tables, resolve_generation_config(CONFIG))
    assert next(c for c in report["checks"] if c["check_id"] == "daily_source_completeness")["status"] == "failed"


def test_feature_label_cannot_claim_availability_before_day_close(dataset):
    rows = ai_feature_rows(dataset["daily_demand_observations"], dataset["product_catalog"], dataset["catalog_categories"])
    rows[0]["observation_available_at"] = rows[0]["date"] + "T12:00:00+00:00"
    with pytest.raises(ValueError, match="day close"):
        validate_ai_records(rows)
