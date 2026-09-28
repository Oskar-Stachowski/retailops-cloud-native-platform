from __future__ import annotations

SIMULATION_VERSION = "retail-simulation-parameters-1.0.0"
PRODUCT_PARAMETERS = [
    "demand_class",
    "demand_weight",
    "price_elasticity",
    "seasonal_pattern",
    "return_rate",
]
STORE_PARAMETERS = ["traffic_multiplier", "promo_sensitivity"]
SALE_TRUTH_FIELDS = [
    "latent_demand",
    "stockout_flag",
    "promotion_uplift",
    "price_elasticity_effect",
    "demand_noise",
]
SIMULATION_COLUMNS = {
    "product_simulation_parameters": [
        "id",
        "product_id",
        *PRODUCT_PARAMETERS,
        "simulation_policy_version",
    ],
    "store_simulation_parameters": [
        "id",
        "legacy_store_id",
        *STORE_PARAMETERS,
        "simulation_policy_version",
    ],
}
SIMULATION_GRAINS = {
    "product_simulation_parameters": ["product_id"],
    "store_simulation_parameters": ["legacy_store_id"],
}


def uses_separation(profile: str, schema_version: str = "2.5.0") -> bool:
    return profile.startswith("ai-") and schema_version == "2.5.0"


def fact_columns(name: str, columns: list[str]) -> list[str]:
    removed = {
        "products": PRODUCT_PARAMETERS,
        "stores": STORE_PARAMETERS,
        "sales": SALE_TRUTH_FIELDS,
    }.get(name, ())
    return [field for field in columns if field not in removed]
