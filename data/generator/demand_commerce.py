from __future__ import annotations

import random
from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

from data.generator.commerce_pricing import CommercePricing
from data.generator.common import deterministic_uuid, money
from data.generator.demand_grid import demand_grid
from data.generator.demand_model import daily_demand
from data.generator.dimensions import DimensionIndex

if TYPE_CHECKING:
    from data.anomalies.contract import AnomalyPlan
    from data.generator.configuration import ResolvedGenerationConfig

COMPLEMENTARY = {
    "Grocery": "Pet Care",
    "Pet Care": "Grocery",
    "Fashion": "Beauty",
    "Beauty": "Fashion",
}


def allocate_baskets(
    budgets: dict[str, int], categories: dict[str, str], channel: str, rng: random.Random
) -> list[list[tuple[str, int]]]:
    if (
        any(type(quantity) is not int or quantity < 0 for quantity in budgets.values())
        or not budgets.keys() <= categories.keys()
    ):
        msg = "Basket budgets must be known, nonnegative integer quantities."
        raise ValueError(msg)
    remaining = dict(sorted(budgets.items()))
    baskets = []
    while any(remaining.values()):
        active = [product for product, quantity in remaining.items() if quantity]
        anchor = rng.choices(active, weights=[remaining[product] for product in active], k=1)[0]
        wanted = rng.randint(2, 4) if channel == "wholesale" else rng.randint(1, 3)
        complementary = [
            product
            for product in active
            if product != anchor
            and categories[product] == COMPLEMENTARY.get(categories[anchor], categories[anchor])
        ]
        companions = rng.sample(complementary, min(len(complementary), wanted - 1))
        rest = [product for product in active if product != anchor and product not in companions]
        companions += rng.sample(rest, min(len(rest), wanted - 1 - len(companions)))
        basket = []
        for product in [anchor, *companions]:
            quantity = rng.randint(1, min(remaining[product], 6 if channel == "wholesale" else 3))
            remaining[product] -= quantity
            basket.append((product, quantity))
        baskets.append(basket)
    return baskets


def _order_lines(
    basket: list[tuple[str, int]],
    reference: str,
    store: dict[str, str],
    day: str,
    ordered: str,
    sold: str,
    pricing: CommercePricing,
) -> tuple[list, list]:
    items, sales = [], []
    for product, quantity in basket:
        quote = pricing.quote(product, store, day, ordered, quantity)
        key = f"{reference}:{product}"
        item_id, sale_id = deterministic_uuid("order_item", key), deterministic_uuid("sale", key)
        pricing.record(sale_id, item_id, product, store, day, ordered, quote)
        common = {
            "product_id": product,
            "quantity": str(quantity),
            "unit_price": money(quote.unit_price),
            "total_amount": money(quote.total_amount),
            "currency": quote.currency,
        }
        items.append({"id": item_id, "order_id": deterministic_uuid("order", reference), **common})
        sales.append(
            {
                "id": sale_id,
                **common,
                "channel": store["channel"],
                "region": store["region"],
                "sold_at": sold,
                "order_reference": reference,
                "latent_demand": "",
                "observed_sales": str(quantity),
                "stockout_flag": "",
                "promotion_applied": str(bool(quote.promotion_plan_id)).lower(),
                "promotion_uplift": "",
                "price_elasticity_effect": "",
                "demand_noise": "",
                "data_quality_status": "ok",
                "ingested_at": sold,
            }
        )
    return items, sales


def generate_demand_commerce(
    products: list[dict[str, str]],
    stores: list[dict[str, str]],
    dimensions: dict[str, list[dict[str, str]]],
    plans: dict[str, list[dict[str, str]]],
    config: ResolvedGenerationConfig,
    *,
    anomaly_plan: AnomalyPlan | None = None,
) -> tuple[list, list, list, list, list]:
    grid, exclusions = demand_grid(dimensions, config)
    factors = anomaly_plan.factors(dimensions, config) if anomaly_plan is not None else {}
    pricing = CommercePricing(plans, DimensionIndex(dimensions))
    catalog, adapters = {r["id"]: r for r in products}, {r["id"]: r for r in stores}
    budgets, truth = defaultdict(dict), []
    for key, flags in sorted(grid.items()):
        if flags["location_open"] == "false":
            continue
        store = adapters[flags["legacy_store_id"]]
        row = daily_demand(
            catalog[key[1]], store, key, pricing, config, anomaly_factor=factors.get(key, "1")
        )
        truth.append(row)
        budgets[key[0], flags["legacy_store_id"]][key[1]] = int(row["latent_units"])
    orders, items, sales = [], [], []
    categories = {key: row["category"] for key, row in catalog.items()}
    for (day, adapter), quantities in sorted(budgets.items()):
        store = adapters[adapter]
        rng = random.Random(f"basket:{config.seed}:{day}:{adapter}")  # noqa: S311 - deterministic simulation
        baskets = allocate_baskets(quantities, categories, store["channel"], rng)
        for sequence, basket in enumerate(baskets):
            reference = f"ORD-{day}-{adapter}-{sequence:06d}"
            ordered_at = datetime.combine(date.fromisoformat(day), time(9), tzinfo=UTC) + timedelta(
                seconds=sequence % 36000
            )
            ordered, sold = ordered_at.isoformat(), (ordered_at + timedelta(minutes=1)).isoformat()
            order_items, order_sales = _order_lines(
                basket, reference, store, day, ordered, sold, pricing
            )
            orders.append(
                {
                    "id": deterministic_uuid("order", reference),
                    "order_reference": reference,
                    "store_id": adapter,
                    "channel": store["channel"],
                    "region": store["region"],
                    "status": "completed",
                    "order_total": money(
                        sum((Decimal(r["total_amount"]) for r in order_items), Decimal(0))
                    ),
                    "currency": "PLN",
                    "ordered_at": ordered,
                    "created_at": ordered,
                }
            )
            items.extend(order_items)
            sales.extend(order_sales)
    return sales, orders, items, truth, exclusions
