"""Actual causal generator stress, without touching any portfolio holdout."""

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

import pytest

from data.generator.configuration import DatasetGenerationConfig, resolve_generation_config
from data.generator.demand_model import expected_demand, sample_units
from data.generator.profile_engine import _rng
from data.generator.stockout_stress import (
    PROFILE,
    SHOCK_DAYS,
    SHOCK_START_DAY,
    anomaly_factor,
    selected_product,
)
from data.inventory.run_source_dataset import build_source_dataset, default_inventory_config
from data.inventory.source_dataset_quality import build_source_report

START = date(2026, 6, 9)
END = date(2026, 9, 18)


@pytest.fixture
def config():
    return resolve_generation_config(
        DatasetGenerationConfig(
            profile=PROFILE,
            start_date=START,
            end_date=END,
        )
    )


def identities(wanted):
    return next(f"product-{i}" for i in range(100) if selected_product(f"product-{i}") is wanted)


def test_profile_has_real_matching_dimensions_and_explicit_prospective_dates(config):
    assert (config.days, config.products, config.stores, config.warehouses) == (102, 30, 3, 2)
    assert (config.start_date, config.end_date) == (START, END)
    assert config.max_daily_rows == 9180
    assert config.profile != "ai-load"


@pytest.mark.parametrize(
    "changes", [dict(end_date=None), dict(end_date=START + timedelta(days=82))]
)
def test_missing_dates_or_incomplete_stress_control_tail_is_refused(changes):
    raw = dict(profile=PROFILE, start_date=START, end_date=END)
    raw.update(changes)
    with pytest.raises(ValueError):
        resolve_generation_config(DatasetGenerationConfig(**raw))


def test_bound_end_and_days_reconstruct_the_same_start_without_implicit_today(config):
    assert (
        resolve_generation_config(DatasetGenerationConfig(profile=PROFILE, days=102, end_date=END))
        == config
    )


@pytest.mark.parametrize("offset,factor", [(0, 1), (48, 1), (49, 2), (55, 2), (56, 1), (101, 1)])
def test_shock_boundaries_are_exact_and_control_periods_are_unchanged(config, offset, factor):
    product = identities(True)
    assert anomaly_factor(config, product, START + timedelta(days=offset)) == Decimal(factor)


def test_product_controls_and_other_profiles_never_receive_the_stress_factor(config):
    day = START + timedelta(days=SHOCK_START_DAY)
    assert anomaly_factor(config, identities(False), day) == Decimal(1)
    for profile in ("ai-load", "ai-dev", "ai-training", "ai-temporal-smoke", "ai-intermittent-v1"):
        assert anomaly_factor(replace(config, profile=profile), identities(True), day) == Decimal(1)


@pytest.mark.parametrize("seed", [42, 137, 2026])
def test_catalog_random_draws_stay_paired_with_the_baseline(seed):
    stress, baseline = _rng(seed, PROFILE), _rng(seed, "ai-load")
    assert [stress.random() for _ in range(3)] == [baseline.random() for _ in range(3)]


def test_factor_changes_latent_rate_before_rounding_and_is_not_a_label_override(config):
    fields = (
        "base_rate",
        "product_factor",
        "location_factor",
        "weekly_factor",
        "seasonal_factor",
        "lifecycle_factor",
        "price_factor",
        "promotion_factor",
        "anomaly_factor",
        "noise",
    )
    base = dict.fromkeys(fields, "1")
    base["base_rate"] = "4.25"
    stressed = {
        **base,
        "anomaly_factor": str(anomaly_factor(config, identities(True), START + timedelta(days=49))),
    }
    assert expected_demand(stressed) == 2 * expected_demand(base)
    assert sample_units(expected_demand(stressed), Decimal("0.25")) == 9
    assert sample_units(expected_demand(base), Decimal("0.25")) == 4
    assert SHOCK_DAYS == 7


@pytest.fixture(scope="module")
def miniature():
    """Six products verify generator physics, not the 30-product final cohort."""
    end = START + timedelta(days=83)
    generation = DatasetGenerationConfig(
        profile=PROFILE,
        products=6,
        days=84,
        stores=3,
        warehouses=2,
        start_date=START,
        end_date=end,
        max_daily_rows=1512,
    )
    stock = default_inventory_config(generation)
    stressed, context = build_source_dataset(generation, stock)
    baseline_generation = replace(generation, profile="ai-load")
    baseline, _ = build_source_dataset(baseline_generation, stock)
    return generation, stock, stressed, baseline, context


def test_actual_chronological_source_replays_every_source_gate(miniature):
    generation, stock, tables, _, context = miniature
    report = build_source_report(tables, context, resolve_generation_config(generation), stock)
    assert all(c["status"] == "passed" for c in report["checks"])
    assert len(report["checks"]) == 36


def test_real_stress_changes_arrivals_and_inventory_only_after_its_start(miniature):
    _, _, stressed, baseline, _ = miniature
    cutoff = (START + timedelta(days=SHOCK_START_DAY)).isoformat() + "T00:00:00+00:00"
    before = lambda tables, name, field: [r for r in tables[name] if r[field] < cutoff]
    assert before(stressed, "inventory_demand_arrivals", "occurred_at") == before(
        baseline, "inventory_demand_arrivals", "occurred_at"
    )
    assert before(stressed, "inventory_ledger", "occurred_at") == before(
        baseline, "inventory_ledger", "occurred_at"
    )
    actual = {
        (r["business_date"], r["product_id"], r["selling_location_id"], r["channel"]): r
        for r in stressed["daily_demand_truth"]
    }
    ordinary = {
        (r["business_date"], r["product_id"], r["selling_location_id"], r["channel"]): r
        for r in baseline["daily_demand_truth"]
    }
    changed = [k for k in actual if Decimal(actual[k]["anomaly_factor"]) == 2]
    assert changed and set(actual) == set(ordinary)
    for k in changed:
        # Decimal's existing 28-digit intermediate rounding is unchanged.
        assert abs(
            Decimal(actual[k]["expected_rate"]) - 2 * Decimal(ordinary[k]["expected_rate"])
        ) <= Decimal("1e-24")
    assert stressed["inventory_demand_arrivals"] != baseline["inventory_demand_arrivals"]
    assert stressed["inventory_ledger"] != baseline["inventory_ledger"]
