from __future__ import annotations

from data.generator.feature_admission import admit_feature_tables
from data.generator.source_quality import project_facts
from ml.features.worker import transform

import copy
import json
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from zipfile import ZipFile

import pytest

from data.generator.business_calendar import utc_midnight
from data.generator.configuration import DatasetGenerationConfig, resolve_generation_config
from data.generator.csv_writer import write_tables
from data.generator.main import build_dataset, generate_demo_dataset
from data.generator.manifest_v2 import build_source_manifest_v2, load_source_manifest_v2
from data.generator.price_resolver import PriceResolver
from data.generator.pricing_contract import pricing_contract_schema
from data.generator.pricing_plans import (
    daily_price_observations,
    legacy_pricing_projection,
    plan_key,
)
from data.generator.pricing_quality import build_pricing_report, validate_pricing
from data.generator.pricing_schema import PRICING_COLUMNS
from data.generator.promotion_truth import build_promotion_truth, simulation_promotion_factor
from ml.features.demand_forecast import FEATURE_COLUMNS, build_demand_feature_rows
from ml.features.identity import load_feature_identity_manifest

ROOT = Path(__file__).resolve().parents[3]
CONFIG = DatasetGenerationConfig(profile="ai-smoke")
START = "2026-07-01"
CUTOFF = "2026-07-01T00:00:00+00:00"


def price(
    scope="global",
    location="",
    channel="all",
    amount="100.00",
    version="1",
    available="2026-06-30T00:00:00+00:00",
):
    key = plan_key("p", scope, location, channel)
    return {
        "id": f"price-{scope}-{version}",
        "plan_key": key,
        "version": version,
        "product_id": "p",
        "scope": scope,
        "selling_location_id": location,
        "channel": channel,
        "effective_from": START,
        "effective_to": "2026-08-01",
        "known_at": available,
        "available_at": available,
        "price": amount,
        "currency": "PLN",
        "pricing_policy_version": "retail-pricing-1.0.0",
    }


def promotion(
    kind="percentage",
    scope="global",
    location="",
    channel="all",
    discount="10.00",
    priority="100",
    minimum="1",
    version="1",
    status="active",
    available="2026-06-30T00:00:00+00:00",
):
    key = "campaign:" + plan_key("p", scope, location, channel)
    return {
        "id": f"promo-{scope}-{version}",
        "promotion_key": key,
        "version": version,
        "product_id": "p",
        "scope": scope,
        "selling_location_id": location,
        "channel": channel,
        "effective_from": "2026-07-10",
        "effective_to": "2026-07-15",
        "known_at": available,
        "available_at": available,
        "promotion_type": kind,
        "discount_percent": discount,
        "minimum_quantity": minimum,
        "priority": priority,
        "stacking_policy": "exclusive_highest_priority",
        "status": status,
        "pricing_policy_version": "retail-pricing-1.0.0",
    }


def resolver(prices=None, promotions=None):
    return PriceResolver(
        {
            "price_plans": prices if prices is not None else [price()],
            "promotion_plans": promotions or [],
        }
    )


@pytest.fixture(scope="module")
def priced_dataset():
    return build_dataset(CONFIG)


def test_generated_ai_plans_cover_all_assortment_and_have_controls(priced_dataset):
    report = validate_pricing(priced_dataset, resolve_generation_config(CONFIG))
    assert report["price_coverage_percent"] == 100
    assert report["valid_daily_combinations"] == 1612
    assert len(report["checks"]) == 6
    assert all(c["status"] == "passed" and c["severity"] == "hard" for c in report["checks"])
    assert report["complete_daily_panel"] is False
    assert report["realized_prices_are_outcomes"] is True
    plans = priced_dataset["promotion_plans"]
    assert {r["promotion_type"] for r in plans} == {"percentage", "bundle", "clearance", "seasonal"}
    assert {r["version"] for r in plans} == {"1", "2"}
    assert len({(r["effective_from"], r["effective_to"]) for r in plans}) > 1
    assert {r["scope"] for r in priced_dataset["price_plans"]} == {
        "global",
        "channel",
        "location",
        "location_channel",
    }
    assert {r["id"] for r in priced_dataset["products"]} - {r["product_id"] for r in plans}
    assert all("promotion_uplift" not in r for r in priced_dataset["sales"])


@pytest.mark.parametrize(
    "location,channel,expected",
    [
        ("other", "store", "100.00"),
        ("other", "online", "90.00"),
        ("l", "store", "80.00"),
        ("l", "online", "70.00"),
    ],
)
def test_scope_precedence_and_nonmatching_scope(location, channel, expected):
    plans = [
        price(),
        price("channel", channel="online", amount="90.00"),
        price("location", location="l", amount="80.00"),
        price("location_channel", location="l", channel="online", amount="70.00"),
    ]
    assert resolver(plans).resolve("p", location, channel, START, CUTOFF).unit_price == Decimal(
        expected
    )


def test_price_revision_cutoff_does_not_rewrite_earlier_knowledge():
    original = price()
    correction = price(amount="120.00", version="2", available="2026-07-12T12:00:00.000001+00:00")
    before = resolver([original]).resolve(
        "p", "l", "online", "2026-07-13", "2026-07-12T12:00:00+00:00"
    )
    after_append = resolver([original, correction]).resolve(
        "p", "l", "online", "2026-07-13", "2026-07-12T12:00:00+00:00"
    )
    assert before == after_append
    assert resolver([original, correction]).resolve(
        "p", "l", "online", "2026-07-13", "2026-07-12T14:00:00.000001+02:00"
    ).unit_price == Decimal("120.00")
    # A future effective plan is already usable if its version is known at origin.
    assert resolver([original]).resolve(
        "p", "l", "online", "2026-07-30", "2026-06-30T00:00:00+00:00"
    ).unit_price == Decimal("100.00")


def test_plan_end_is_exclusive_missing_is_error_and_naive_cutoff_rejected():
    assert resolver().resolve("p", "l", "online", "2026-07-31", CUTOFF).unit_price == 100
    with pytest.raises(ValueError, match="Missing known"):
        resolver().resolve("p", "l", "online", "2026-08-01", CUTOFF)
    with pytest.raises(ValueError, match="Missing known"):
        resolver().resolve("p", "l", "online", START, "2026-06-29T23:59:59+00:00")
    with pytest.raises(ValueError, match="timezone"):
        resolver().resolve("p", "l", "online", START, "2026-07-01T00:00:00")


@pytest.mark.parametrize(
    "kind,discount,min_quantity",
    [
        ("percentage", "8.00", 1),
        ("bundle", "15.00", 2),
        ("clearance", "25.00", 1),
        ("seasonal", "12.00", 1),
    ],
)
def test_promotion_types_apply_one_discount_to_the_whole_qualified_line(
    kind, discount, min_quantity
):
    promo = promotion(kind=kind, discount=discount, minimum=str(min_quantity))
    quote = resolver(promotions=[promo]).resolve("p", "l", "online", "2026-07-10", CUTOFF, 3)
    expected = Decimal(100) - Decimal(discount)
    assert quote.unit_price == expected and quote.total_amount == expected * 3
    assert quote.promotion_plan_id == promo["id"]
    for day in ("2026-07-09", "2026-07-15"):
        assert (
            resolver(promotions=[promo])
            .resolve("p", "l", "online", day, CUTOFF, 3)
            .promotion_plan_id
            == ""
        )
    if kind == "bundle":
        assert (
            resolver(promotions=[promo])
            .resolve("p", "l", "online", "2026-07-10", CUTOFF, 1)
            .unit_price
            == 100
        )


def test_priority_is_exclusive_and_ties_or_overlapping_prices_fail():
    promos = [
        promotion(discount="10.00"),
        promotion(scope="channel", channel="online", discount="20.00", priority="200"),
    ]
    quote = resolver(promotions=promos).resolve("p", "l", "online", "2026-07-10", CUTOFF, 3)
    assert quote.unit_price == 80 and quote.total_amount == 240
    promos[1]["priority"] = "100"
    with pytest.raises(ValueError, match="priority"):
        resolver(promotions=promos).resolve("p", "l", "online", "2026-07-10", CUTOFF)
    overlapping = dict(price(version="2"), effective_from="2026-07-05")
    with pytest.raises(ValueError, match="overlapping"):
        resolver([price(), overlapping]).resolve("p", "l", "store", "2026-07-10", CUTOFF)
    with pytest.raises(ValueError, match="revision"):
        resolver([price(), price()]).resolve("p", "l", "store", START, CUTOFF)


def test_unavailable_scope_and_promotion_cancellation_respect_origin():
    unavailable = price(
        "location_channel",
        location="l",
        channel="online",
        amount="50.00",
        available="2026-07-12T00:00:00+00:00",
    )
    assert (
        resolver([price(), unavailable])
        .resolve("p", "l", "online", "2026-07-13", CUTOFF)
        .unit_price
        == 100
    )
    initial = promotion()
    cancelled = promotion(version="2", status="cancelled", available="2026-07-12T00:00:00+00:00")
    plans = resolver(promotions=[initial, cancelled])
    assert (
        plans.resolve("p", "l", "online", "2026-07-13", CUTOFF).promotion_plan_id == initial["id"]
    )
    assert (
        plans.resolve(
            "p", "l", "online", "2026-07-13", "2026-07-12T00:00:00+00:00"
        ).promotion_plan_id
        == ""
    )
    scoped = promotion(scope="location_channel", location="l", channel="store")
    assert (
        resolver(promotions=[scoped])
        .resolve("p", "other", "store", "2026-07-10", CUTOFF)
        .promotion_plan_id
        == ""
    )
    assert (
        resolver(promotions=[scoped])
        .resolve("p", "l", "online", "2026-07-10", CUTOFF)
        .promotion_plan_id
        == ""
    )


@pytest.mark.parametrize("quantity", [-1, True, 1.5])
def test_invalid_quantity_is_rejected(quantity):
    with pytest.raises(ValueError, match="quantity"):
        resolver().resolve("p", "l", "store", START, CUTOFF, quantity)


@pytest.mark.parametrize(
    "location,channel,day",
    [("", "store", START), ("l", "all", START), ("l", "store", "2026-07-99")],
)
def test_invalid_lookup_scope_or_day_is_rejected(location, channel, day):
    with pytest.raises(ValueError):
        resolver().resolve("p", location, channel, day, CUTOFF)


def test_zero_quantity_and_decimal_half_up_rounding():
    promo = promotion(discount="10.00")
    quote = resolver([price(amount="0.05")], [promo]).resolve(
        "p", "l", "store", "2026-07-10", CUTOFF, 3
    )
    assert quote.unit_price == Decimal("0.05") and quote.total_amount == Decimal("0.15")
    assert (
        resolver(promotions=[promo])
        .resolve("p", "l", "store", "2026-07-10", CUTOFF, 0)
        .total_amount
        == 0
    )


def test_pre_and_post_effects_are_chronological_and_only_in_truth():
    promo = promotion()
    truth = {promo["id"]: build_promotion_truth([promo])}
    resolved = resolver(promotions=[promo])
    for day, expected in [
        ("2026-07-06", "1"),
        ("2026-07-07", "0.92"),
        ("2026-07-09", "0.92"),
        ("2026-07-10", "1.2"),
        ("2026-07-14", "1.2"),
        ("2026-07-15", "0.86"),
        ("2026-07-18", "0.86"),
        ("2026-07-19", "1"),
    ]:
        assert simulation_promotion_factor(
            resolved, truth, "p", "l", "store", day, CUTOFF, Decimal(1)
        ) == Decimal(expected)
    # A resolver needs no truth table, including while a promotion is active.
    assert resolved.resolve("p", "l", "store", "2026-07-10", CUTOFF).unit_price == 90


@pytest.mark.parametrize(
    "table,field,value,check",
    [
        ("price_plans", "price", "0.00", "pricing_schema_versions_scope"),
        ("price_plans", "currency", "EUR", "pricing_schema_versions_scope"),
        ("price_plans", "product_id", "unknown", "pricing_schema_versions_scope"),
        ("price_plans", "selling_location_id", "unknown", "pricing_schema_versions_scope"),
        (
            "price_plans",
            "available_at",
            "2026-08-01T00:00:00+00:00",
            "known_price_coverage_and_priority",
        ),
        ("promotion_plans", "discount_percent", "100.00", "pricing_schema_versions_scope"),
        (
            "promotion_plans",
            "available_at",
            "2026-06-01T00:00:00+00:00",
            "pricing_schema_versions_scope",
        ),
        ("promotion_plans", "stacking_policy", "multiply", "pricing_schema_versions_scope"),
        ("sales", "unit_price", "0.01", "transaction_price_reconciliation"),
        ("sales", "promotion_applied", "true", "transaction_price_reconciliation"),
        ("sales", "promotion_uplift", "0.9200", "transaction_price_reconciliation"),
        ("sales", "ingested_at", "2026-07-31T08:00:00", "realized_price_aggregates"),
        ("sales", "ingested_at", "2026-07-31T10:00:00+02:00", "realized_price_aggregates"),
        ("order_items", "unit_price", "0.01", "transaction_price_reconciliation"),
        ("orders", "order_total", "0.01", "transaction_price_reconciliation"),
        ("sale_price_references", "price_plan_id", "unknown", "transaction_price_reconciliation"),
        ("sale_price_references", "channel", "wholesale", "transaction_price_reconciliation"),
        ("sale_price_references", "as_of_time", CUTOFF, "transaction_price_reconciliation"),
        ("daily_price_observations", "gross_revenue", "0.01", "realized_price_aggregates"),
        ("daily_price_observations", "realized_unit_price", "0.01", "realized_price_aggregates"),
        ("daily_price_observations", "available_at", CUTOFF, "realized_price_aggregates"),
        ("price_history", "price", "0.01", "legacy_pricing_adapter"),
        ("promotion_effect_truth", "phase", "post", "promotion_truth_direction"),
        ("promotion_effect_truth", "demand_multiplier", "0.8600", "promotion_truth_direction"),
    ],
)
def test_negative_pricing_gates(priced_dataset, table, field, value, check):
    broken = copy.deepcopy(priced_dataset)
    broken[table][0][field] = value
    report = build_pricing_report(broken, resolve_generation_config(CONFIG))
    assert report["status"] == "failed"
    assert next(c for c in report["checks"] if c["check_id"] == check)["status"] == "failed"
    with pytest.raises(ValueError, match="hard gate"):
        validate_pricing(broken, resolve_generation_config(CONFIG))


@pytest.mark.parametrize(
    "failure",
    [
        "missing_price",
        "overlap",
        "duplicate_version",
        "inactive_promotion",
        "wrong_discount",
        "missing_reference",
        "missing_aggregate",
        "duplicate_truth",
    ],
)
def test_relational_price_failures_cannot_pass_or_reach_features(priced_dataset, failure):
    broken = copy.deepcopy(priced_dataset)
    if failure == "missing_price":
        broken["price_plans"].pop(0)
    elif failure == "overlap":
        broken["price_plans"][1]["effective_from"] = broken["price_plans"][0]["effective_from"]
    elif failure == "duplicate_version":
        broken["price_plans"][1]["version"] = broken["price_plans"][0]["version"]
    elif failure in {"inactive_promotion", "wrong_discount"}:
        used = next(
            r["promotion_plan_id"]
            for r in broken["sale_price_references"]
            if r["promotion_plan_id"]
        )
        plan = next(r for r in broken["promotion_plans"] if r["id"] == used)
        plan["status" if failure == "inactive_promotion" else "discount_percent"] = (
            "cancelled" if failure == "inactive_promotion" else "1.00"
        )
    elif failure == "missing_reference":
        broken["sale_price_references"].pop()
    elif failure == "missing_aggregate":
        broken["daily_price_observations"].pop()
    else:
        broken["promotion_effect_truth"].append(dict(broken["promotion_effect_truth"][0]))
    assert build_pricing_report(broken, resolve_generation_config(CONFIG))["status"] == "failed"
    with pytest.raises(ValueError, match="hard gate"):
        admit_feature_tables(broken, CONFIG)


def test_recomputed_checksums_cannot_hide_price_gap_or_false_report(tmp_path, priced_dataset):
    generate_demo_dataset(tmp_path, CONFIG)
    broken = copy.deepcopy(priced_dataset)
    broken["price_plans"].pop(0)
    write_tables(tmp_path, broken)
    with pytest.raises(ValueError, match="pricing hard gate"):
        build_source_manifest_v2(CONFIG, broken, tmp_path)


def test_realized_aggregate_is_quantity_weighted_and_not_a_model_feature():
    sales = [
        {"id": "a", "product_id": "p", "quantity": "2", "total_amount": "20.00"},
        {"id": "b", "product_id": "p", "quantity": "1", "total_amount": "20.00"},
    ]
    for sale in sales:
        sale["sold_at"] = CUTOFF
    sales[1]["ingested_at"] = "2026-07-01T12:00:00+00:00"
    references = [
        {
            "sale_id": r["id"],
            "business_date": START,
            "selling_location_id": "l",
            "channel": "store",
            "price_plan_id": "price",
            "promotion_plan_id": "",
            "as_of_time": CUTOFF,
        }
        for r in sales
    ]
    aggregate = daily_price_observations(sales, references)[0]
    assert aggregate["quantity"] == "3" and aggregate["gross_revenue"] == "40.00"
    assert aggregate["realized_unit_price"] == "13.33"
    assert aggregate["available_at"] == "2026-07-01T12:00:00+00:00"
    assert not {
        "realized_unit_price",
        "gross_revenue",
        "demand_multiplier",
        "promotion_uplift",
    } & set(FEATURE_COLUMNS)
    sales[0]["quantity"], sales[0]["total_amount"] = "0", "0.00"
    aggregate = daily_price_observations(sales[:1], references[:1])[0]
    assert aggregate["realized_unit_price"] == ""


def test_historical_2_1_source_and_features_keep_identity(tmp_path):
    with ZipFile(Path(__file__).parent / "fixtures/source_manifest_v2_1.zip") as fixture:
        for name in fixture.namelist():
            assert Path(name).name == name
            (tmp_path / name).write_bytes(fixture.read(name))
    source = load_source_manifest_v2(tmp_path)
    features = load_feature_identity_manifest(tmp_path)
    assert source["schema_version"] == "2.1.0" and len(source["artifacts"]) == 26
    assert (
        source["dataset_id"]
        == "source-sha256-ae37e69c364eb75d0db8d994c3096313d216046d3dc413b77d9896528823da50"
    )
    assert (
        features["dataset_id"]
        == "features-sha256-a6de899cb7a6940f93941a1ef0ce67824aa765c9ba9fa78ff9921a99843130ed"
    )
    assert features["descriptor"]["parent_ids"] == [source["dataset_id"]]


def test_new_source_classifies_truth_and_reports_both_json_and_md(tmp_path):
    generate_demo_dataset(tmp_path, CONFIG)
    source = load_source_manifest_v2(tmp_path)
    assert source["schema_version"] == "2.6.0" and len(source["artifacts"]) == 40
    assert source["descriptor"]["versions"]["pricing"] == "retail-pricing-1.0.0"
    truth = next(a for a in source["artifacts"] if a["table"] == "promotion_effect_truth")
    assert truth["data_class"] == truth["temporal_role"] == "simulation_truth"
    assert {"pricing_report.json", "pricing_report.md"} <= {r["path"] for r in source["reports"]}
    # Even a freshly checksummed fake report must disagree with a semantic recomputation.
    (tmp_path / "pricing_report.md").write_text("# passed\n")
    with pytest.raises(ValueError, match="Pricing report"):
        build_source_manifest_v2(CONFIG, build_dataset(CONFIG), tmp_path)


def test_pricing_contract_matches_executable_rules_and_minimal_profile():
    assert (
        json.loads((ROOT / "data/contracts/retail_pricing.v1.schema.json").read_text())
        == pricing_contract_schema()
    )
    config = replace(CONFIG, days=1, products=1, stores=1, warehouses=1, end_date=date(2026, 7, 5))
    tables = build_dataset(config)
    assert not tables["sales"]
    assert validate_pricing(tables, resolve_generation_config(config))["status"] == "passed"
    assert not set(PRICING_COLUMNS) & set(build_dataset(DatasetGenerationConfig()))
