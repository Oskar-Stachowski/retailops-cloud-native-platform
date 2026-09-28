from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import TYPE_CHECKING

from data.generator.common import deterministic_uuid
from data.generator.price_resolver import PriceQuote, PriceResolver
from data.generator.pricing_schema import PRICING_VERSION
from data.generator.promotion_truth import simulation_promotion_factor

if TYPE_CHECKING:
    from data.generator.dimensions import DimensionIndex


class CommercePricing:
    def __init__(
        self, tables: dict[str, list[dict[str, str]]], dimensions: DimensionIndex | None
    ) -> None:
        if dimensions is None:
            msg = "AI pricing requires canonical dimensions."
            raise ValueError(msg)
        self.tables, self.dimensions, self.resolver = tables, dimensions, PriceResolver(tables)
        self.truth = defaultdict(list)
        for row in tables["promotion_effect_truth"]:
            self.truth[row["promotion_plan_id"]].append(row)

    def location(self, store: dict[str, str], day: str, cutoff: str) -> str:
        assignment = self.dimensions.assignment(store["id"], day, cutoff)
        if assignment is None:
            msg = "No known assignment for pricing."
            raise ValueError(msg)
        return assignment["selling_location_id"]

    def demand_inputs(
        self, product: dict[str, str], store: dict[str, str], day: str, cutoff: str
    ) -> tuple[Decimal, Decimal, Decimal]:
        location = self.location(store, day, cutoff)
        quote = self.resolver.resolve(product["id"], location, store["channel"], day, cutoff)
        base_price = Decimal(product["base_price"])
        elasticity = max(
            Decimal("0.35"),
            Decimal(1)
            - (quote.unit_price - base_price) / base_price * Decimal(product["price_elasticity"]),
        )
        effect = simulation_promotion_factor(
            self.resolver,
            self.truth,
            product["id"],
            location,
            store["channel"],
            day,
            cutoff,
            Decimal(store["promo_sensitivity"]),
        )
        return quote.unit_price, elasticity, effect

    def quote(
        self, product_id: str, store: dict[str, str], day: str, cutoff: str, quantity: int
    ) -> PriceQuote:
        return self.resolver.resolve(
            product_id, self.location(store, day, cutoff), store["channel"], day, cutoff, quantity
        )

    def record(
        self,
        sale_id: str,
        item_id: str,
        product_id: str,
        store: dict[str, str],
        day: str,
        cutoff: str,
        quote: PriceQuote,
    ) -> None:
        self.tables["sale_price_references"].append(
            {
                "id": deterministic_uuid("sale_pricing", sale_id),
                "sale_id": sale_id,
                "order_item_id": item_id,
                "product_id": product_id,
                "selling_location_id": self.location(store, day, cutoff),
                "channel": store["channel"],
                "business_date": day,
                "as_of_time": cutoff,
                "price_plan_id": quote.price_plan_id,
                "promotion_plan_id": quote.promotion_plan_id,
                "pricing_policy_version": PRICING_VERSION,
            }
        )
