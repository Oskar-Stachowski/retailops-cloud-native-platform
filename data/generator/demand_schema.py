from __future__ import annotations

DEMAND_VERSION = "daily-demand-1.0.0"
DEMAND_GRAIN = ["business_date", "product_id", "selling_location_id", "channel"]
DEMAND_COLUMNS = {
    "daily_demand_observations": [
        "id",
        *DEMAND_GRAIN,
        "observed_units",
        "observed_orders",
        "gross_revenue",
        "net_revenue",
        "return_units",
        "return_data_complete",
        "currency",
        "realized_unit_price",
        "promotion_plan_ids",
        "available_at",
        "is_active_assortment",
        "location_open",
        "source_data_complete",
        "observation_status",
        "quality_status",
        "demand_policy_version",
    ],
    "daily_demand_exclusions": [
        "id",
        *DEMAND_GRAIN,
        "observation_status",
        "exclusion_reason",
        "demand_policy_version",
    ],
    "daily_demand_truth": [
        "id",
        *DEMAND_GRAIN,
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
        "expected_rate",
        "rounding_draw",
        "latent_units",
        "demand_policy_version",
    ],
}
DEMAND_CLASSES = {
    "daily_demand_observations": "source_observation",
    "daily_demand_exclusions": "source_observation",
    "daily_demand_truth": "simulation_truth",
}
DEMAND_GRAINS = dict.fromkeys(DEMAND_COLUMNS, DEMAND_GRAIN)


def uses_demand(profile: str, schema_version: str = "2.3.0") -> bool:
    return profile.startswith("ai-") and schema_version == "2.3.0"
