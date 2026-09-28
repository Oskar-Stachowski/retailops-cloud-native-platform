from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

from data.generator.common import deterministic_uuid
from data.generator.pricing_schema import PROMOTION_POLICIES, TRUTH_VERSION

if TYPE_CHECKING:
    from data.generator.price_resolver import PriceResolver


def build_promotion_truth(promotions: list[dict[str, str]]) -> list[dict[str, str]]:
    rows = []
    for promotion in promotions:
        start, end = map(
            date.fromisoformat, (promotion["effective_from"], promotion["effective_to"])
        )
        for phase, first, last, multiplier in (
            ("pre", start - timedelta(days=3), start, "0.9200"),
            ("during", start, end, PROMOTION_POLICIES[promotion["promotion_type"]][2]),
            ("post", end, end + timedelta(days=4), "0.8600"),
        ):
            rows.append(
                {
                    "id": deterministic_uuid("promotion_truth", promotion["id"] + ":" + phase),
                    "promotion_plan_id": promotion["id"],
                    "phase": phase,
                    "effective_from": first.isoformat(),
                    "effective_to": last.isoformat(),
                    "demand_multiplier": multiplier,
                    "truth_policy_version": TRUTH_VERSION,
                }
            )
    return rows


def simulation_promotion_factor(
    resolver: PriceResolver,
    truth: dict[str, list[dict[str, str]]],
    product_id: str,
    location: str,
    channel: str,
    day: str,
    as_of_time: str,
    sensitivity: Decimal,
) -> Decimal:
    campaigns = {r["id"]: r for r in resolver.campaigns(product_id, location, channel, as_of_time)}
    matching = [
        r
        for plan in campaigns
        for r in truth.get(plan, [])
        if r["effective_from"] <= day < r["effective_to"]
    ]
    if not matching:
        return Decimal(1)
    # Pre/during/post are generator truth; active campaigns take precedence over neighbouring tails.
    selected = max(
        matching,
        key=lambda r: (
            r["phase"] == "during",
            int(campaigns[r["promotion_plan_id"]]["priority"]),
            r["promotion_plan_id"],
        ),
    )
    multiplier = Decimal(selected["demand_multiplier"])
    return (
        Decimal(1) + (multiplier - 1) * sensitivity if selected["phase"] == "during" else multiplier
    )
