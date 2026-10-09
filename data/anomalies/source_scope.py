"""Explicit complete Source profiles for independent paired anomaly replay.

The standalone AI07 candidate builders retain their 5000-grain budget. Native
Source publication additionally supports the preregistered AI09 profiles; it
does not sample their history, locations, demand or physical outcomes.
"""

from data.generator.configuration import DatasetGenerationConfig, resolve_generation_config
from data.inventory.contract import require


def require_source_scenario_scope(generation: DatasetGenerationConfig) -> None:
    effective = resolve_generation_config(generation)
    grains = effective.days * effective.products * effective.stores
    legacy = effective.profile.startswith("ai-") and grains <= 5000
    development = (
        effective.profile == "ai-dev"
        and effective.days == 365
        and effective.products in {25, 50, 100}
        and (effective.stores, effective.warehouses, effective.seed) == (5, 3, 42)
    )
    final = (
        effective.profile == "ai-training"
        and (effective.days, effective.products, effective.stores, effective.warehouses)
        == (730, 200, 10, 4)
        and effective.seed in {42, 137, 2026}
    )
    require(
        legacy or ((development or final) and effective.forecast_plan_days == 14),
        "Source anomaly replay requires an original bounded candidate or a complete AI09 profile.",
    )
