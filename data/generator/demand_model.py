from __future__ import annotations

import random
from datetime import date
from decimal import Decimal
from functools import reduce
from operator import mul
from typing import TYPE_CHECKING

from data.generator.common import deterministic_uuid
from data.generator.demand_schema import DEMAND_VERSION

if TYPE_CHECKING:
    from data.generator.commerce_pricing import CommercePricing
    from data.generator.configuration import ResolvedGenerationConfig

BASE_RATES = {
    "hero_product": "8",
    "core_product": "5.6",
    "seasonal": "3.2",
    "new_product": "1.8",
    "declining_product": "1.5",
    "clearance_product": "1.2",
    "long_tail": "0.6",
}
FACTOR_FIELDS = [
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
]


def expected_demand(factors: dict[str, str]) -> Decimal:
    values = [Decimal(factors[name]) for name in FACTOR_FIELDS]
    if any(not value.is_finite() or value < 0 for value in values):
        msg = "Demand factors must be finite and nonnegative."
        raise ValueError(msg)
    return reduce(mul, values, Decimal(1))


def sample_units(rate: Decimal, draw: Decimal) -> int:
    if not rate.is_finite() or rate < 0 or not 0 <= draw < 1:
        msg = "Invalid stochastic demand rounding inputs."
        raise ValueError(msg)
    floor = int(rate)
    return floor + int(draw < rate - floor)


def daily_demand(
    product: dict[str, str],
    store: dict[str, str],
    key: tuple[str, ...],
    pricing: CommercePricing,
    config: ResolvedGenerationConfig,
) -> dict[str, str]:
    day = date.fromisoformat(key[0])
    rng = random.Random(f"demand:{config.seed}:{':'.join(key)}")  # noqa: S311 - deterministic simulation
    baselines = [
        r
        for r in pricing.tables["price_plans"]
        if r["product_id"] == product["id"]
        and r["scope"] == "global"
        and r["version"] == "1"
        and r["effective_from"] == config.start_date.isoformat()
    ]
    if len(baselines) != 1:
        msg = "Demand requires one canonical initial global reference price."
        raise ValueError(msg)
    _, price_factor, promotion_factor = pricing.demand_inputs(
        dict(product, base_price=baselines[0]["price"]), store, key[0], key[0] + "T00:00:00+00:00"
    )
    progress = Decimal((day - config.start_date).days + 1) / config.days
    lifecycle = (
        Decimal("0.45") + progress * Decimal("1.25")
        if product["demand_class"] == "new_product"
        else Decimal("1.30") - progress * Decimal("0.65")
        if product["demand_class"] == "declining_product"
        else Decimal("0.75") + progress * Decimal("0.55")
        if product["demand_class"] == "clearance_product"
        else Decimal(1)
    )
    weekly = Decimal("1.2") if day.weekday() >= 5 else Decimal(1)
    seasonal = (
        Decimal("1.4")
        if product["seasonal_pattern"] == "holiday_peak" and day.month >= 11
        else Decimal("1.2")
        if product["seasonal_pattern"] == "spring_summer_peak" and 4 <= day.month <= 8
        else Decimal(1)
    )
    factors = {
        "base_rate": BASE_RATES[product["demand_class"]],
        "product_factor": product["demand_weight"],
        "location_factor": store["traffic_multiplier"],
        "weekly_factor": str(weekly),
        "seasonal_factor": str(seasonal),
        "lifecycle_factor": str(lifecycle),
        "price_factor": str(price_factor),
        "promotion_factor": str(promotion_factor),
        "anomaly_factor": "1",
        "noise": str(Decimal(str(rng.uniform(0.78, 1.24)))),
    }
    rate, draw = expected_demand(factors), Decimal(str(rng.random()))
    return {
        "id": deterministic_uuid("demand_truth", ":".join(key)),
        **dict(
            zip(("business_date", "product_id", "selling_location_id", "channel"), key, strict=True)
        ),
        **factors,
        "expected_rate": str(rate),
        "rounding_draw": str(draw),
        "latent_units": str(sample_units(rate, draw)),
        "demand_policy_version": DEMAND_VERSION,
    }
