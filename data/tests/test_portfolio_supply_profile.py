"""The supply-adequate benchmark is explicit and keeps legacy profile policies intact."""

from datetime import date, timedelta

from data.generator.configuration import DatasetGenerationConfig, resolve_generation_config
from data.inventory.run_source_dataset import default_inventory_config
from data.generator.main import build_dataset


def test_versioned_supply_profile_keeps_the_full_census_within_original_capture_budget():
    old = DatasetGenerationConfig(profile="ai-07-portfolio-v1")
    new = DatasetGenerationConfig(profile="ai-07-portfolio-v2")
    legacy = default_inventory_config(old)
    adequate = default_inventory_config(new)
    assert legacy.stock.opening_quantity == 12
    assert legacy.stock.reorder_point == 8
    assert adequate.stock.opening_quantity == 256
    assert adequate.stock.reorder_point == 128
    resolved = resolve_generation_config(new)
    assert (resolved.days, resolved.products, resolved.stores, resolved.warehouses) == (128, 8, 2, 2)
    # No sampling: reduced declared geography funds a larger native stock budget.
    assert resolved.max_daily_rows == 2048
    assert adequate.fulfillment == legacy.fulfillment
    assert adequate.sale_availability_delay_seconds == legacy.sale_availability_delay_seconds


def test_supply_profile_has_native_online_history_for_all_physical_scenario_products():
    generation = DatasetGenerationConfig(profile="ai-07-portfolio-v2")
    tables = build_dataset(generation)
    assert len(tables["selling_locations"]) == 1
    assert {a["channel"] for a in tables["channel_assignments"]} == {"store", "online"}
    grouped = {}
    start = resolve_generation_config(generation).start_date
    required = {(start + timedelta(days=i)).isoformat() for i in range(28, 128)}
    for r in tables["daily_demand_truth"]:
        if r["channel"] == "online":
            grouped.setdefault(r["product_id"], set()).add(r["business_date"])
    assert sum(required <= days for days in grouped.values()) >= 4


def test_confirmatory_profile_declares_distinct_calendar_and_larger_control_cohort():
    generation = DatasetGenerationConfig(profile="ai-07-portfolio-v3")
    resolved = resolve_generation_config(generation)
    assert (resolved.start_date, resolved.end_date) == (date(2026, 1, 1), date(2026, 5, 8))
    assert (resolved.days, resolved.products, resolved.stores, resolved.warehouses) == (128, 12, 2, 2)
    assert resolved.max_daily_rows == 3072
    tables = build_dataset(generation)
    assert len(tables["selling_locations"]) == 1
    assert len(tables["product_catalog"]) == 12
    assert {a["channel"] for a in tables["channel_assignments"]} == {"store", "online"}
    assert default_inventory_config(generation).stock.opening_quantity == 256
    # The new recipe acts on every native demand row before sampling, never on
    # selected outcomes or final labels.
    for row in tables["daily_demand_truth"]:
        assert float(row["base_rate"]) <= 4
