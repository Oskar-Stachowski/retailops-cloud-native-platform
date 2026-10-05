"""The named portfolio does not silently inherit smoke sizes or change final splits."""

import pytest

from data.anomalies.portfolio import PROFILE, SEEDS, SPLITS, portfolio_plan
from data.generator.configuration import DatasetGenerationConfig, resolve_generation_config


def test_declared_dimensions_and_reserved_windows():
    config = resolve_generation_config(DatasetGenerationConfig(profile=PROFILE, seed=42))
    assert (config.days, config.products, config.stores, config.warehouses) == (128, 8, 3, 2)
    assert config.end_date.isoformat() == "2026-07-31"
    assert SEEDS == (42, 137, 2026)
    assert SPLITS == {"training": (28, 59), "validation": (64, 95), "final_test": (100, 127)}


@pytest.mark.parametrize("options", [{"days": 30}, {"seed": 99}, {"products": 20}])
def test_unfrozen_source_options_fail_before_generation(options):
    with pytest.raises(ValueError, match="frozen"):
        portfolio_plan(DatasetGenerationConfig(profile=PROFILE, **options), "demand")
