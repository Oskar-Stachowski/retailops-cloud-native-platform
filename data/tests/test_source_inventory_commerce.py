from __future__ import annotations

import copy
import json
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from data.generator.commerce_pricing import CommercePricing
from data.generator.configuration import DatasetGenerationConfig, resolve_generation_config
from data.generator.dimensions import DimensionIndex
from data.generator.identity import json_sha256
from data.generator.main import build_dataset
from data.generator.observation_history import feature_history, validate_daily_versions
from data.inventory.contract import utc_timestamp
from data.inventory.ledger import InventoryLedger
from data.inventory.source_bridge import COMMERCE_TABLES, simulate_source_commerce
from data.inventory.source_commerce import SourceCommerceSimulator
from data.inventory.source_contract import SourceInventoryConfig, source_inventory_schema
from data.inventory.source_foundation import source_foundation
from data.inventory.source_observations import rebuild_observations
from data.inventory.source_reconciliation import reconcile_source_commerce

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "data/tests/fixtures/source-inventory-config-v1.json"


@pytest.fixture(scope="module")
def generation():
    return DatasetGenerationConfig(profile="ai-smoke", days=8, products=8, stores=3, warehouses=2)


@pytest.fixture(scope="module")
def candidate(generation):
    return build_dataset(generation)


@pytest.fixture
def configuration():
    return json.loads(CONFIG.read_text())


@pytest.fixture(scope="module")
def normal(candidate, generation):
    return simulate_source_commerce(
        candidate,
        resolve_generation_config(generation),
        SourceInventoryConfig.from_payload(json.loads(CONFIG.read_text())),
    )


def test_fulfilled_daily_units_plus_losses_equal_sampled_demand(normal, candidate):
    report = normal["reconciliation"]
    assert normal["status"] == "passed"
    assert report["latent_quantity"] == report["observed_quantity"] + report["lost_sales_quantity"]
    assert report["lost_sales_quantity"] > 0
    assert report["observed_quantity"] < sum(int(r["quantity"]) for r in candidate["sales"])
    assert report["sales"] == report["sale_issues"] == len(normal["commerce"]["sales"])
    assert report["daily_grains"] == len(candidate["daily_demand_observations"])
    assert report["pricing_checks"] == 6 and report["return_checks"] == 7


def test_candidate_is_immutable_and_repeat_is_identical(
    normal, candidate, generation, configuration
):
    before = json_sha256(candidate)
    repeat = simulate_source_commerce(
        candidate,
        resolve_generation_config(generation),
        SourceInventoryConfig.from_payload(configuration),
    )
    assert json_sha256(candidate) == before
    assert repeat == normal


def test_opening_is_once_and_snapshots_sum_shared_physical_stock(normal):
    inventory = normal["inventory"]
    ledger = InventoryLedger.from_payload(inventory["ledger"])
    openings = [m for m in ledger.movements if m.movement_type == "opening_stock"]
    assert len(openings) == len(ledger.scope) == 16
    assert {m.quantity_delta for m in openings} == {12}
    assert len(normal["inventory_snapshots"]) == 8 * 16
    for snapshot in normal["inventory_snapshots"]:
        cutoff = utc_timestamp(snapshot["as_of_time"])
        visible = [
            m
            for m in ledger.movements
            if m.position == (snapshot["product_id"], snapshot["stock_location_id"])
            and utc_timestamp(m.occurred_at) <= cutoff
            and utc_timestamp(m.available_at) <= cutoff
        ]
        assert snapshot["on_hand"] == sum(m.quantity_delta for m in visible) >= 0
        assert snapshot["reserved_qty"] == 0
    assert (
        sum(r["movement_type"] == "initial_stock" for r in normal["legacy_stock_movements"]) == 16
    )
    groups = defaultdict(set)
    for sale in inventory["sales"]:
        groups[sale["stock_location_id"]].add((sale["selling_location_id"], sale["channel"]))
    assert any(len(channels) > 1 for channels in groups.values())


def test_actual_baskets_have_no_empty_lines_and_totals_are_recomputed(normal, candidate):
    tables = normal["commerce"]
    original_items = {r["id"]: r for r in candidate["order_items"]}
    grouped = defaultdict(list)
    for item in tables["order_items"]:
        assert 0 < int(item["quantity"]) <= int(original_items[item["id"]]["quantity"])
        grouped[item["order_id"]].append(item)
    assert any(
        int(item["quantity"]) < int(original_items[item["id"]]["quantity"])
        for item in tables["order_items"]
    )
    assert len(tables["orders"]) < len(candidate["orders"])
    for order in tables["orders"]:
        lines = grouped[order["id"]]
        assert lines and len({r["product_id"] for r in lines}) == len(lines)
        assert Decimal(order["order_total"]) == sum(Decimal(r["total_amount"]) for r in lines)


def test_partial_quantity_requotes_bundle_discount(candidate, generation, configuration):
    candidate = copy.deepcopy(candidate)
    effective = resolve_generation_config(generation)
    configuration["stock"]["opening_quantity"] = 1
    config = SourceInventoryConfig.from_payload(configuration)
    inputs = source_foundation(candidate, effective, config)
    arrival = next(r for r in inputs["scenario"]["demand_arrivals"] if r["latent_quantity"] >= 2)
    inputs["scenario"]["demand_arrivals"] = [arrival]
    promotion = copy.deepcopy(candidate["promotion_plans"][0])
    promotion.update(
        product_id=arrival["product_id"],
        selling_location_id="",
        channel="all",
        scope="global",
        promotion_type="bundle",
        minimum_quantity="2",
        discount_percent="15.00",
        status="active",
        effective_from=effective.start_date.isoformat(),
        effective_to=(effective.end_date + timedelta(days=1)).isoformat(),
        known_at=inputs["policy"]["known_at"],
        available_at=inputs["policy"]["known_at"],
    )
    candidate["promotion_plans"] = [promotion]
    ref = next(
        r for r in candidate["sale_price_references"] if r["sale_id"] == arrival["demand_id"]
    )
    item = next(r for r in candidate["order_items"] if r["id"] == ref["order_item_id"])
    order = next(r for r in candidate["orders"] if r["id"] == item["order_id"])
    store = next(r for r in candidate["stores"] if r["id"] == order["store_id"])
    pricing = CommercePricing(candidate, DimensionIndex(candidate))
    wanted = pricing.quote(
        arrival["product_id"], store, ref["business_date"], order["ordered_at"], 2
    )
    actual = pricing.quote(
        arrival["product_id"], store, ref["business_date"], order["ordered_at"], 1
    )
    assert wanted.promotion_plan_id == promotion["id"] and actual.promotion_plan_id == ""
    assert wanted.unit_price < actual.unit_price
    engine = SourceCommerceSimulator(inputs, candidate, effective, config)
    result = engine.execute()
    sale = result["operational"]["sales"][0]
    assert sale["quantity"] == 1 and Decimal(sale["unit_price"]) == actual.unit_price
    assert engine.actual_items[0]["quantity"] == "1"
    assert engine.actual_orders()[0]["order_total"] == sale["gross_revenue"]
    assert candidate["sale_price_references"][0]["promotion_plan_id"] == ""


def test_refunds_quality_and_financial_tail_are_distinct(normal):
    decisions = normal["return_inventory_decisions"]
    counts = Counter(r["inventory_disposition"] for r in decisions)
    assert all(
        counts[k]
        for k in ("restocked", "quality_rejected", "not_refunded", "outside_inventory_window")
    )
    processed = {r["return_id"]: r for r in normal["inventory"]["returns"]}
    restocks = {
        r["source_reference"]
        for r in normal["inventory"]["ledger"]["movements"]
        if r["movement_type"] == "return_to_stock"
    }
    for row in decisions:
        if row["inventory_disposition"] == "restocked":
            assert row["return_id"] in restocks
            assert row["inventory_available_at"] is not None
        elif row["inventory_disposition"] == "quality_rejected":
            assert row["return_id"] not in restocks
            assert Decimal(processed[row["return_id"]]["refund_amount"]) > 0
        else:
            assert row["return_id"] not in processed and row["inventory_available_at"] is None
    assert any(
        r["inventory_available_at"] != r["financial_available_at"]
        for r in decisions
        if r["return_id"] in processed
    )
    end = utc_timestamp(normal["inventory"]["history_end_at"])
    assert all(
        utc_timestamp(m["occurred_at"]) < end for m in normal["inventory"]["ledger"]["movements"]
    )


def test_supply_truth_changes_receipts_but_not_initial_orders(
    normal, candidate, generation, configuration
):
    configuration["supplier_parameters"]["reliability"] = "0"
    configuration["fulfillment"]["disruption_delay_days"] = 1
    poor = simulate_source_commerce(
        candidate,
        resolve_generation_config(generation),
        SourceInventoryConfig.from_payload(configuration),
    )
    assert poor["status"] == "passed"
    assert poor["inventory"]["reviews"][0] == normal["inventory"]["reviews"][0]
    assert all(r["disrupted"] for r in poor["simulation_truth"]["supplier_samples"])
    assert (
        poor["reconciliation"]["observed_quantity"] < normal["reconciliation"]["observed_quantity"]
    )
    grouped = defaultdict(list)
    for receipt in poor["inventory"]["supply"]["replenishment_receipts"]:
        grouped[receipt["replenishment_order_id"]].append(receipt)
    assert any(len(parts) == 2 for parts in grouped.values())
    assert "reliability" not in json.dumps(poor["commerce"])


def test_truth_tables_are_not_exposed_as_commerce(normal):
    assert set(normal["commerce"]) == set(COMMERCE_TABLES)
    for name in (
        "daily_demand_truth",
        "promotion_effect_truth",
        "product_simulation_parameters",
        "store_simulation_parameters",
    ):
        assert name not in normal["commerce"]
    for sale in normal["commerce"]["sales"]:
        assert not {"latent_demand", "stockout_flag", "demand_noise"} & sale.keys()


def test_route_ids_periods_and_source_versions_are_preserved(normal, candidate):
    canonical = {r["id"]: r for r in candidate["fulfillment_routes"]}
    mapping = {r["route_id"]: r for r in normal["inventory"]["source_route_versions"]}
    assert any(r["source_version"] == 2 and r["inventory_revision"] == 1 for r in mapping.values())
    for route in normal["inventory"]["fulfillment_routes"]:
        assert canonical[route["id"]]["stock_location_id"] == route["stock_location_id"]
        assert mapping[route["id"]]["source_version"] == int(canonical[route["id"]]["version"])


def test_late_availability_does_not_rewrite_past_history_or_cohort(normal, generation):
    tables, sales = copy.deepcopy(normal["commerce"]), copy.deepcopy(normal["inventory"]["sales"])
    sale = sales[0]
    cutoff = utc_timestamp(normal["inventory"]["history_end_at"])
    sale["available_at"] = (cutoff + timedelta(hours=1)).isoformat()
    raw = next(r for r in tables["sales"] if r["id"] == sale["sale_id"])
    raw_ingestion = raw["ingested_at"]
    rebuild_observations(tables, sales, resolve_generation_config(generation))
    assert raw["ingested_at"] == raw_ingestion
    ref = next(r for r in tables["sale_price_references"] if r["sale_id"] == sale["sale_id"])
    grain = tuple(ref[f] for f in ("business_date", "product_id", "selling_location_id", "channel"))
    panel = next(
        r
        for r in tables["daily_demand_observations"]
        if tuple(r[f] for f in ("business_date", "product_id", "selling_location_id", "channel"))
        == grain
    )
    versions = [r for r in tables["daily_demand_versions"] if r["observation_id"] == panel["id"]]
    assert len(versions) > 1
    history = feature_history(versions)
    assert history[-1]["units_sold"] - history[0]["units_sold"] == sale["quantity"]
    cohort = next(
        r
        for r in tables["daily_return_cohorts"]
        if r["snapshot_kind"] == "history"
        and tuple(r[f] for f in ("business_date", "product_id", "selling_location_id", "channel"))
        == grain
    )
    assert int(cohort["observed_units"]) == int(panel["observed_units"]) - sale["quantity"]
    assert cohort["return_data_complete"] == "false"
    assert validate_daily_versions(tables) == len(tables["daily_demand_versions"])


@pytest.mark.parametrize(
    "mutation",
    [
        "sale_qty",
        "sale_price",
        "sale_ingestion",
        "item_qty",
        "empty_order",
        "order_total",
        "duplicate_sale",
        "missing_ref",
        "latent_in_fact",
        "daily_units",
        "history_units",
        "cohort_units",
        "return_quantity",
        "return_disposition",
        "return_stock_location",
        "route_lineage",
        "route_location",
        "snapshot_balance",
        "snapshot_missing",
        "snapshot_lineage",
        "legacy_quantity",
        "legacy_opening",
        "loss_quantity",
        "receipt_quantity",
        "history_boundary",
    ],
)
def test_corrupt_source_integration_fails(mutation, normal, candidate, generation):
    broken = copy.deepcopy(normal)
    tables = broken["commerce"]
    if mutation == "sale_qty":
        tables["sales"][0]["quantity"] = "9999"
    elif mutation == "sale_price":
        tables["sales"][0]["unit_price"] = "0.01"
    elif mutation == "sale_ingestion":
        tables["sales"][0]["ingested_at"] = "2026-08-31T00:00:00Z"
    elif mutation == "item_qty":
        tables["order_items"][0]["quantity"] = "9999"
    elif mutation == "empty_order":
        tables["orders"].append(copy.deepcopy(candidate["orders"][-1]))
    elif mutation == "order_total":
        tables["orders"][0]["order_total"] = "0.00"
    elif mutation == "duplicate_sale":
        tables["sales"].append(copy.deepcopy(tables["sales"][0]))
    elif mutation == "missing_ref":
        tables["sale_price_references"].pop()
    elif mutation == "latent_in_fact":
        tables["sales"][0]["latent_demand"] = "1"
    elif mutation == "daily_units":
        tables["daily_demand_observations"][0]["observed_units"] = "9999"
    elif mutation == "history_units":
        tables["daily_demand_versions"][0]["observed_units"] = "9999"
    elif mutation == "cohort_units":
        tables["daily_return_cohorts"][0]["observed_units"] = "9999"
    elif mutation == "return_quantity":
        tables["return_events"][0]["quantity"] = "9999"
    elif mutation == "return_disposition":
        broken["return_inventory_decisions"][0]["inventory_disposition"] = (
            "restocked"
            if broken["return_inventory_decisions"][0]["inventory_disposition"] != "restocked"
            else "quality_rejected"
        )
    elif mutation == "return_stock_location":
        broken["return_inventory_decisions"][0]["stock_location_id"] = tables["selling_locations"][
            0
        ]["id"]
    elif mutation == "route_lineage":
        broken["inventory"]["source_route_versions"][0]["source_version"] = 999
    elif mutation == "route_location":
        broken["inventory"]["fulfillment_routes"][0]["stock_location_id"] = tables[
            "selling_locations"
        ][0]["id"]
    elif mutation == "snapshot_balance":
        broken["inventory_snapshots"][0]["on_hand"] += 1
    elif mutation == "snapshot_missing":
        broken["inventory_snapshots"].pop()
    elif mutation == "snapshot_lineage":
        broken["inventory_snapshots"][0]["last_inventory_event_id"] = None
    elif mutation == "legacy_quantity":
        broken["legacy_stock_movements"][0]["quantity"] = "-9999"
    elif mutation == "legacy_opening":
        broken["legacy_stock_movements"][0]["movement_type"] = "replenishment"
    elif mutation == "loss_quantity":
        broken["simulation_truth"]["demand_outcomes"][0]["lost_sales_quantity"] += 1
    elif mutation == "receipt_quantity":
        broken["inventory"]["supply"]["replenishment_receipts"][0]["received_quantity"] += 1
    elif mutation == "history_boundary":
        broken["inventory"]["history_end_at"] = "2026-08-01T01:00:00Z"
    with pytest.raises((ValueError, KeyError)):
        reconcile_source_commerce(
            candidate,
            broken,
            resolve_generation_config(generation),
            normal["effective_configuration"]["scenario"],
        )


@pytest.mark.parametrize(
    "path,value",
    [
        (("stock", "opening_quantity"), True),
        (("stock", "opening_quantity"), -1),
        (("stock", "history_window_days"), 0),
        (("supplier_parameters", "reliability"), "1.01"),
        (("supplier_parameters", "lead_time_mean_days"), "-1"),
        (("fulfillment", "partial_fraction"), "1"),
        (("return_tail_policy",), "extend_inventory_without_demand"),
        (("unexpected",), "yes"),
    ],
)
def test_invalid_configuration_fails(configuration, path, value):
    target = configuration
    for field in path[:-1]:
        target = target[field]
    target[path[-1]] = value
    with pytest.raises(ValueError):
        SourceInventoryConfig.from_payload(configuration)


@pytest.mark.parametrize("field,value", [("seed", 99), ("history_window_days", 9)])
def test_seed_and_observation_window_are_not_silently_changed(
    candidate, generation, configuration, field, value
):
    if field == "seed":
        configuration["fulfillment"][field] = value
    else:
        configuration["stock"][field] = value
    with pytest.raises(ValueError):
        simulate_source_commerce(
            candidate,
            resolve_generation_config(generation),
            SourceInventoryConfig.from_payload(configuration),
        )


def test_configuration_schema_matches_runtime():
    schema = json.loads(
        (ROOT / "data/contracts/source_inventory_config.v1.schema.json").read_text()
    )
    assert schema == source_inventory_schema()


def test_cli_pass_and_failure_are_explicit(tmp_path):
    report = tmp_path / "report.json"
    command = [
        sys.executable,
        "-m",
        "data.inventory.run_source_commerce",
        "--days",
        "4",
        "--products",
        "2",
        "--stores",
        "2",
        "--warehouses",
        "1",
        "--inventory-config",
        str(CONFIG),
        "--output",
        str(report),
    ]
    passed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    assert passed.returncode == 0, passed.stderr + passed.stdout
    result = json.loads(report.read_text())
    assert result["status"] == "passed"
    assert result["inventory_ready"] is result["source_ready"] is result["model_ready"] is False
    assert result["execution_id"].startswith("source-inventory-candidate-sha256-")
    assert (
        "data/contracts/inventory_ledger.v1.schema.json" in result["code_provenance"]["code_files"]
    )
    assert (
        "data/contracts/source_inventory_config.v1.schema.json"
        in result["code_provenance"]["code_files"]
    )
    failed = subprocess.run([*command, "--seed", "99"], cwd=ROOT, text=True, capture_output=True)
    assert failed.returncode == 1
    failure = json.loads(report.read_text())
    assert failure["status"] == "failed" and "seed" in failure["error"]


def test_zero_opening_is_known_zero_and_receipts_enable_sales(candidate, generation, configuration):
    configuration["stock"]["opening_quantity"] = 0
    result = simulate_source_commerce(
        candidate,
        resolve_generation_config(generation),
        SourceInventoryConfig.from_payload(configuration),
    )
    first = result["inventory_snapshots"][:16]
    assert all(r["status"] == "known" and r["on_hand"] == 0 for r in first)
    assert result["reconciliation"]["observed_quantity"] > 0
    assert result["reconciliation"]["lost_sales_quantity"] > 0


def test_late_sales_remain_not_ready_at_source_boundary(candidate, generation, configuration):
    configuration["sale_availability_delay_seconds"] = 86400
    result = simulate_source_commerce(
        candidate,
        resolve_generation_config(generation),
        SourceInventoryConfig.from_payload(configuration),
    )
    assert result["status"] == "not_ready"
    assert result["reconciliation"]["inventory_snapshots"] == 128
    assert (
        len(result["commerce"]["daily_demand_versions"]) > result["reconciliation"]["daily_grains"]
    )
