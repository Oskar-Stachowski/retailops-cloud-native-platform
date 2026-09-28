from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from data.generator.common import money
from data.generator.pricing_schema import PRICING_VERSION, SCOPE_RANK, STACKING_POLICY


def known_at(row: dict[str, str], as_of_time: str) -> bool:
    cutoff = datetime.fromisoformat(as_of_time)
    available = datetime.fromisoformat(row["available_at"])
    if cutoff.tzinfo is None or available.tzinfo is None:
        msg = "Price plan lookup requires timezone-aware timestamps."
        raise ValueError(msg)
    return available.astimezone(UTC) <= cutoff.astimezone(UTC)


def scope_matches(row: dict[str, str], selling_location_id: str, channel: str) -> bool:
    return (
        not row["selling_location_id"] or row["selling_location_id"] == selling_location_id
    ) and (row["channel"] == "all" or row["channel"] == channel)


def latest_versions(rows: list[dict[str, str]], key: str) -> list[dict[str, str]]:
    groups = defaultdict(list)
    for row in rows:
        groups[row[key]].append(row)
    selected = []
    for revisions in groups.values():
        if len({(r["effective_from"], r["effective_to"]) for r in revisions}) != 1:
            msg = "Ambiguous overlapping plan periods."
            raise ValueError(msg)
        highest = max(int(r["version"]) for r in revisions)
        matches = [r for r in revisions if int(r["version"]) == highest]
        if len(matches) != 1:
            msg = "Ambiguous plan revision."
            raise ValueError(msg)
        selected.append(matches[0])
    return selected


@dataclass(frozen=True)
class PriceQuote:
    regular_price: Decimal
    unit_price: Decimal
    total_amount: Decimal
    price_plan_id: str
    promotion_plan_id: str
    discount_percent: Decimal
    currency: str


class PriceResolver:
    """Resolve observable plans only; simulation effects are a separate generator input."""

    def __init__(self, tables: dict[str, list[dict[str, Any]]]) -> None:
        self.prices = defaultdict(list)
        self.promotions = defaultdict(list)
        for row in tables["price_plans"]:
            self.prices[row["product_id"]].append(row)
        for row in tables["promotion_plans"]:
            self.promotions[row["product_id"]].append(row)

    def campaigns(
        self, product_id: str, location: str, channel: str, as_of_time: str
    ) -> list[dict[str, str]]:
        # Campaign revisions keep their period; selecting a cancellation never revives an older version.
        rows = [
            r
            for r in self.promotions[product_id]
            if scope_matches(r, location, channel) and known_at(r, as_of_time)
        ]
        return [r for r in latest_versions(rows, "promotion_key") if r["status"] == "active"]

    def resolve(
        self,
        product_id: str,
        location: str,
        channel: str,
        day: str,
        as_of_time: str,
        quantity: int = 1,
    ) -> PriceQuote:
        date.fromisoformat(day)
        if channel not in {"store", "online", "marketplace", "wholesale"} or not location:
            msg = "Price lookup requires a selling location and supported channel."
            raise ValueError(msg)
        if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 0:
            msg = "Price quantity must be a nonnegative integer."
            raise ValueError(msg)
        matches = [
            r
            for r in self.prices[product_id]
            if scope_matches(r, location, channel)
            and r["effective_from"] <= day < r["effective_to"]
            and known_at(r, as_of_time)
        ]
        versions = latest_versions(matches, "plan_key")
        if not versions:
            msg = "Missing known price plan; no fallback is permitted."
            raise ValueError(msg)
        rank = max(SCOPE_RANK[r["scope"]] for r in versions)
        prices = [r for r in versions if SCOPE_RANK[r["scope"]] == rank]
        if len(prices) != 1:
            msg = "Ambiguous price scope."
            raise ValueError(msg)
        price = prices[0]
        if price["pricing_policy_version"] != PRICING_VERSION:
            msg = "Unsupported pricing policy."
            raise ValueError(msg)
        candidates = [
            r
            for r in self.campaigns(product_id, location, channel, as_of_time)
            if r["effective_from"] <= day < r["effective_to"]
            and quantity >= int(r["minimum_quantity"])
        ]
        promotion = None
        if candidates:
            priority = max(int(r["priority"]) for r in candidates)
            promotions = [r for r in candidates if int(r["priority"]) == priority]
            if len(promotions) != 1:
                msg = "Ambiguous promotion priority."
                raise ValueError(msg)
            promotion = promotions[0]
            if (
                promotion["stacking_policy"] != STACKING_POLICY
                or promotion["pricing_policy_version"] != PRICING_VERSION
            ):
                msg = "Unsupported promotion stacking policy."
                raise ValueError(msg)
        regular = Decimal(price["price"])
        discount = Decimal(promotion["discount_percent"]) if promotion else Decimal(0)
        unit = Decimal(money(regular * (Decimal(1) - discount / 100)))
        return PriceQuote(
            regular,
            unit,
            Decimal(money(unit * quantity)),
            price["id"],
            promotion["id"] if promotion else "",
            discount,
            price["currency"],
        )
