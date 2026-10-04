from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from data.generator.business_calendar import utc_midnight
from data.generator.common import deterministic_uuid, money
from data.generator.dimension_quality import timestamp
from data.generator.dimensions import dated_versions
from data.generator.pricing_schema import PRICING_VERSION, PROMOTION_POLICIES, STACKING_POLICY
from data.generator.promotion_truth import build_promotion_truth

if TYPE_CHECKING:
    from data.generator.configuration import ResolvedGenerationConfig


def plan_key(product_id: str, scope: str, location: str, channel: str) -> str:
    return f"{product_id}:{scope}:{location}:{channel}"


def build_pricing_plans(
    products: list[dict[str, str]],
    dimensions: dict[str, list[dict[str, str]]],
    config: ResolvedGenerationConfig,
) -> dict[str, list[dict[str, str]]]:
    prices, promotions = [], []
    locations = dimensions["selling_locations"]
    pairs = list(
        dict.fromkeys(
            (r["selling_location_id"], r["channel"]) for r in dimensions["channel_assignments"]
        )
    )
    known = utc_midnight(config.start_date - timedelta(days=1))
    for index, product in enumerate(products):
        scopes = [("global", "", "all", Decimal(1))]
        variant = index % 4
        if variant == 1:
            scopes.append(("channel", "", pairs[-1][1], Decimal("0.97")))
        elif variant == 2:
            scopes.append(("location", locations[-1]["id"], "all", Decimal("1.02")))
        elif variant == 3:
            scopes.append(("location_channel", *pairs[-1], Decimal("0.95")))
        for scope, location, channel, multiplier in scopes:
            key = plan_key(product["id"], scope, location, channel)
            periods = dated_versions(config.start_date, config.end_date + timedelta(days=1))
            if scope == "global":
                periods.append(
                    (
                        len(periods) + 1,
                        (config.end_date + timedelta(days=1)).isoformat(),
                        (config.end_date + timedelta(days=15)).isoformat(),
                    )
                )
            for version, first, last in periods:
                prices.append(
                    {
                        "id": deterministic_uuid("price_plan", f"{key}:{version}:{first}:{last}"),
                        "plan_key": key,
                        "version": str(version),
                        "product_id": product["id"],
                        "scope": scope,
                        "selling_location_id": location,
                        "channel": channel,
                        "effective_from": first,
                        "effective_to": last,
                        "known_at": known,
                        "available_at": known,
                        "price": money(
                            Decimal(product["base_price"])
                            * multiplier
                            * (Decimal(1) if version == 1 else Decimal("1.03"))
                        ),
                        "currency": "PLN",
                        "pricing_policy_version": PRICING_VERSION,
                    }
                )
        if index % 5 == 4:
            continue
        promotion_type = list(PROMOTION_POLICIES)[index % 4]
        discount, minimum, _ = PROMOTION_POLICIES[promotion_type]
        scope, location, channel, _ = scopes[-1]
        offset = config.days // 3 + index % 4
        if config.profile == "ai-07-portfolio-v1":
            offset = (42, 72, 104)[index % 3]
        start = config.start_date + timedelta(days=min(config.days - 1, offset))
        end = min(
            config.end_date + timedelta(days=1),
            start + timedelta(days=max(1, min(7, config.days // 4))),
        )
        key = "campaign:" + plan_key(product["id"], scope, location, channel)
        for version in (1, 2):
            published = utc_midnight(config.start_date - timedelta(days=4 - version))
            promotions.append(
                {
                    "id": deterministic_uuid("promotion_plan", f"{key}:{version}"),
                    "promotion_key": key,
                    "version": str(version),
                    "product_id": product["id"],
                    "scope": scope,
                    "selling_location_id": location,
                    "channel": channel,
                    "effective_from": start.isoformat(),
                    "effective_to": end.isoformat(),
                    "known_at": published,
                    "available_at": published,
                    "promotion_type": promotion_type,
                    "discount_percent": money(Decimal(discount) - (2 if version == 1 else 0)),
                    "minimum_quantity": str(minimum),
                    "priority": str(100 + index % 4),
                    "stacking_policy": STACKING_POLICY,
                    "status": "active",
                    "pricing_policy_version": PRICING_VERSION,
                }
            )
    return {
        "price_plans": prices,
        "promotion_plans": promotions,
        "promotion_effect_truth": build_promotion_truth(promotions),
        "sale_price_references": [],
        "daily_price_observations": [],
    }


def legacy_pricing_projection(
    tables: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    products = {r["id"]: r for r in tables["products"]}
    prices = [
        {
            "id": r["id"],
            "product_id": r["product_id"],
            "price": r["price"],
            "currency": r["currency"],
            "valid_from": r["effective_from"],
            "valid_to": (date.fromisoformat(r["effective_to"]) - timedelta(days=1)).isoformat(),
            "price_type": "planned" if int(r["version"]) > 2 else "regular",
            "source": "canonical_price_plan_adapter",
            "created_at": r["known_at"],
        }
        for r in tables["price_plans"]
    ]
    promotions = [
        {
            "id": r["id"],
            "promotion_code": "PROMO-" + products[r["product_id"]]["sku"] + "-V" + r["version"],
            "product_id": r["product_id"],
            "name": "Synthetic " + r["promotion_type"] + " campaign",
            "promotion_type": r["promotion_type"],
            "discount_percent": r["discount_percent"],
            "starts_at": r["effective_from"],
            "ends_at": (date.fromisoformat(r["effective_to"]) - timedelta(days=1)).isoformat(),
            "channel": r["channel"],
            "status": "active" if r["status"] == "active" else "inactive",
        }
        for r in tables["promotion_plans"]
    ]
    return prices, promotions


def daily_price_observations(
    sales: list[dict[str, str]], references: list[dict[str, str]]
) -> list[dict[str, str]]:
    refs = {r["sale_id"]: r for r in references}
    groups = defaultdict(list)
    for sale in sales:
        ref = refs[sale["id"]]
        groups[
            (ref["business_date"], sale["product_id"], ref["selling_location_id"], ref["channel"])
        ].append(sale)
    rows = []
    for key, observations in sorted(groups.items()):
        day, product, location, channel = key
        quantity = sum(int(r["quantity"]) for r in observations)
        revenue = sum((Decimal(r["total_amount"]) for r in observations), Decimal(0))
        available = max(
            timestamp(value)
            for row in observations
            for value in (row.get("ingested_at") or row["sold_at"], refs[row["id"]]["as_of_time"])
        )
        rows.append(
            {
                "id": deterministic_uuid("daily_price", ":".join(key)),
                "business_date": day,
                "product_id": product,
                "selling_location_id": location,
                "channel": channel,
                "quantity": str(quantity),
                "gross_revenue": money(revenue),
                "realized_unit_price": money(revenue / quantity) if quantity else "",
                "available_at": available.isoformat(),
                "currency": "PLN",
                "price_plan_ids": "|".join(
                    sorted({refs[r["id"]]["price_plan_id"] for r in observations})
                ),
                "promotion_plan_ids": "|".join(
                    sorted({refs[r["id"]]["promotion_plan_id"] for r in observations} - {""})
                ),
                "pricing_policy_version": PRICING_VERSION,
            }
        )
    return rows
