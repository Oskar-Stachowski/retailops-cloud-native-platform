from __future__ import annotations

PRICING_VERSION = "retail-pricing-1.0.0"
STACKING_POLICY = "exclusive_highest_priority"
TRUTH_VERSION = "promotion-effects-1.0.0"
SCOPE_RANK = {"global": 0, "channel": 1, "location": 2, "location_channel": 3}
PROMOTION_POLICIES = {
    "percentage": ("8.00", 1, "1.2000"),
    "bundle": ("15.00", 2, "1.1500"),
    "clearance": ("25.00", 1, "1.3000"),
    "seasonal": ("12.00", 1, "1.2500"),
}
PRICING_COLUMNS = {
    "price_plans": [
        "id",
        "plan_key",
        "version",
        "product_id",
        "scope",
        "selling_location_id",
        "channel",
        "effective_from",
        "effective_to",
        "known_at",
        "available_at",
        "price",
        "currency",
        "pricing_policy_version",
    ],
    "promotion_plans": [
        "id",
        "promotion_key",
        "version",
        "product_id",
        "scope",
        "selling_location_id",
        "channel",
        "effective_from",
        "effective_to",
        "known_at",
        "available_at",
        "promotion_type",
        "discount_percent",
        "minimum_quantity",
        "priority",
        "stacking_policy",
        "status",
        "pricing_policy_version",
    ],
    "promotion_effect_truth": [
        "id",
        "promotion_plan_id",
        "phase",
        "effective_from",
        "effective_to",
        "demand_multiplier",
        "truth_policy_version",
    ],
    "sale_price_references": [
        "id",
        "sale_id",
        "order_item_id",
        "product_id",
        "selling_location_id",
        "channel",
        "business_date",
        "as_of_time",
        "price_plan_id",
        "promotion_plan_id",
        "pricing_policy_version",
    ],
    "daily_price_observations": [
        "id",
        "business_date",
        "product_id",
        "selling_location_id",
        "channel",
        "quantity",
        "gross_revenue",
        "realized_unit_price",
        "available_at",
        "currency",
        "price_plan_ids",
        "promotion_plan_ids",
        "pricing_policy_version",
    ],
}
PRICING_CLASSES = {
    name: "source_plan"
    if name in {"price_plans", "promotion_plans"}
    else "simulation_truth"
    if name == "promotion_effect_truth"
    else "source_observation"
    for name in PRICING_COLUMNS
}
PRICING_GRAINS = {
    "sale_price_references": ["sale_id"],
    "daily_price_observations": ["business_date", "product_id", "selling_location_id", "channel"],
}


def uses_pricing(profile: str, schema_version: str = "2.6.0") -> bool:
    return profile.startswith("ai-") and schema_version in {
        "2.2.0",
        "2.3.0",
        "2.4.0",
        "2.5.0",
        "2.6.0",
    }
