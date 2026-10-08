"""A paired rare-sales scenario with no forecast calendar or outcome dependency."""

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

from data.generator.configuration import DatasetGenerationConfig, resolve_generation_config
from data.generator.demand_model import daily_demand, expected_demand, sample_units
from data.generator.profile_engine import _rng, generate_profile_products, generate_profile_stores


class Pricing:
    def __init__(self, product, start):
        self.tables = {
            "price_plans": [
                {
                    "product_id": product["id"],
                    "scope": "global",
                    "version": "1",
                    "effective_from": start,
                    "price": "10",
                }
            ]
        }

    def demand_inputs(self, *args):
        return None, Decimal(1), Decimal(1)


def test_intermittent_profile_preserves_catalog_locations_and_non_tail_demand():
    config = resolve_generation_config(
        DatasetGenerationConfig(
            profile="ai-dev",
            days=162,
            products=100,
            stores=2,
            warehouses=2,
            end_date=date(2026, 9, 30),
        )
    )
    rare = replace(config, profile="ai-intermittent-v1")
    original_rng, rare_rng = _rng(config.seed, config.profile), _rng(rare.seed, rare.profile)
    products = generate_profile_products(100, original_rng)
    assert generate_profile_products(100, rare_rng) == products
    stores = generate_profile_stores(2, original_rng)
    assert generate_profile_stores(2, rare_rng) == stores
    for product in products:
        key = (config.start_date.isoformat(), product["id"], "location", "online")
        pricing = Pricing(product, config.start_date.isoformat())
        a = daily_demand(product, stores[0], key, pricing, config)
        b = daily_demand(product, stores[0], key, pricing, rare)
        if product["demand_class"] != "long_tail":
            assert a == b
        else:
            assert Decimal(b["expected_rate"]) == Decimal(a["expected_rate"]) / 10
            assert b["rounding_draw"] == a["rounding_draw"]
            assert int(b["latent_units"]) == sample_units(
                expected_demand(b), Decimal(b["rounding_draw"])
            )


def test_rare_sales_have_real_positive_events_and_long_zero_runs_without_window_rules():
    config = resolve_generation_config(
        DatasetGenerationConfig(
            profile="ai-intermittent-v1",
            days=365,
            end_date=date(2026, 9, 30),
        )
    )
    rng = _rng(config.seed, config.profile)
    products = generate_profile_products(config.products, rng)
    store = generate_profile_stores(1, rng)[0]
    lengths, positive = [], 0
    for product in products:
        if product["demand_class"] != "long_tail":
            continue
        pricing = Pricing(product, config.start_date.isoformat())
        run = 0
        for offset in range(config.days):
            day = (config.start_date + timedelta(days=offset)).isoformat()
            row = daily_demand(
                product, store, (day, product["id"], "location", "online"), pricing, config
            )
            units = int(row["latent_units"])
            positive += units
            run = 0 if units else run + 1
            lengths.append(run)
    assert positive > 0
    assert max(lengths) > 28
