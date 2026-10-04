"""The supply-adequate benchmark is explicit and keeps legacy profile policies intact."""

from data.generator.configuration import DatasetGenerationConfig, resolve_generation_config
from data.inventory.run_source_dataset import default_inventory_config


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
