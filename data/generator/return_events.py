from __future__ import annotations

import random
from datetime import timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

from data.generator.business_calendar import utc_midnight
from data.generator.common import deterministic_uuid, money
from data.generator.dimension_quality import timestamp
from data.generator.return_schema import (
    CATEGORY_WINDOWS,
    CHANNEL_WINDOW_OFFSETS,
    MAX_INGESTION_DELAY_DAYS,
    RETURNS_VERSION,
)

if TYPE_CHECKING:
    from data.generator.configuration import ResolvedGenerationConfig


def build_return_policies(tables: dict, config: ResolvedGenerationConfig) -> list[dict[str, str]]:
    return [
        {
            "id": deterministic_uuid("return_policy", category["id"] + ":" + channel),
            "category_id": category["id"],
            "channel": channel,
            "window_days": str(CATEGORY_WINDOWS[category["name"]] + offset),
            "max_ingestion_delay_days": str(MAX_INGESTION_DELAY_DAYS),
            "known_at": utc_midnight(config.start_date - timedelta(days=1)),
            "returns_policy_version": RETURNS_VERSION,
        }
        for category in sorted(tables["catalog_categories"], key=lambda r: r["id"])
        for channel, offset in sorted(CHANNEL_WINDOW_OFFSETS.items())
    ]


def generate_return_events(
    tables: dict,
    config: ResolvedGenerationConfig,
    *,
    return_factors: dict[tuple[str, ...], str] | None = None,
) -> list[dict[str, str]]:
    products = {r["id"]: r for r in tables["products"]}
    catalog = {r["id"]: r for r in tables["product_catalog"]}
    items = {r["id"]: r for r in tables["order_items"]}
    sales = {r["id"]: r for r in tables["sales"]}
    policies = {(r["category_id"], r["channel"]): r for r in tables["return_policies"]}
    events = []
    reasons = ("wrong_size", "damaged", "changed_mind", "not_as_described", "defective")
    multipliers = {"online": 1.55, "store": 1, "marketplace": 1.8, "wholesale": 0.65}
    for ref in sorted(tables["sale_price_references"], key=lambda r: r["sale_id"]):
        item, sale = items[ref["order_item_id"]], sales[ref["sale_id"]]
        rng = random.Random(f"returns:{RETURNS_VERSION}:{config.seed}:{sale['id']}")  # noqa: S311 - synthetic data
        rate = float(products[item["product_id"]]["return_rate"]) * multipliers[ref["channel"]]
        selection_draw = rng.random()
        if not return_factors and selection_draw >= min(rate, 0.75):
            continue
        policy = policies[catalog[item["product_id"]]["category_id"], ref["channel"]]
        quantity = rng.randint(1, int(item["quantity"]))
        pieces = [quantity]
        if quantity > 1 and rng.random() < 0.4:
            first = rng.randint(1, quantity - 1)
            pieces = [first, quantity - first]
        for sequence, units in enumerate(pieces):
            returned = timestamp(sale["sold_at"]) + timedelta(
                days=rng.randint(1, int(policy["window_days"]))
            )
            ingested = returned + timedelta(hours=rng.randint(0, MAX_INGESTION_DELAY_DAYS * 24))
            status = "rejected" if rng.random() < 0.08 else "refunded"
            event = {
                "id": deterministic_uuid("return_event", sale["id"] + ":" + str(sequence)),
                "sale_id": sale["id"],
                "order_id": item["order_id"],
                "order_item_id": item["id"],
                "product_id": item["product_id"],
                "selling_location_id": ref["selling_location_id"],
                "channel": ref["channel"],
                "policy_id": policy["id"],
                "quantity": str(units),
                "refund_amount": money(Decimal(item["unit_price"]) * units)
                if status == "refunded"
                else "0.00",
                "currency": item["currency"],
                "reason": rng.choice(reasons),
                "status": status,
                "returned_at": returned.isoformat(),
                "ingested_at": ingested.isoformat(),
                "available_at": ingested.isoformat(),
                "returns_policy_version": RETURNS_VERSION,
            }
            # Generate the same potential pieces/random draws for an original sale.
            # The private scenario changes selection only for the return-date grain.
            # Pieces partition the purchased quantity; they never add a second refund.
            key = (
                returned.date().isoformat(),
                event["product_id"],
                event["selling_location_id"],
                event["channel"],
            )
            factor = float((return_factors or {}).get(key, "1"))
            if selection_draw < min(rate * factor, 0.75):
                events.append(event)
    return sorted(events, key=lambda r: r["id"])
