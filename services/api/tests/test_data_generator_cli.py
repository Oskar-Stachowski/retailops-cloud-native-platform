from __future__ import annotations

import pytest

from data.generator.main import (
    DatasetGenerationConfig,
    build_dataset,
    config_from_args,
    validate_generation_config,
)


class Args:
    profile = "demo"
    days = 14
    products = 20
    stores = 4
    warehouses = 4
    seed = 42


def test_config_from_args_maps_cli_options() -> None:
    config = config_from_args(Args)

    assert config == DatasetGenerationConfig(
        profile="demo",
        days=14,
        products=20,
        stores=4,
        warehouses=4,
        seed=42,
    )


def test_demo_profile_accepts_positive_scaling_options() -> None:
    config = DatasetGenerationConfig(
        profile="demo",
        days=14,
        products=20,
        stores=4,
        warehouses=4,
        seed=42,
    )

    validate_generation_config(config)


def test_demo_profile_keeps_current_dataset_shape() -> None:
    tables = build_dataset(DatasetGenerationConfig(profile="demo"))

    assert len(tables["products"]) == 8
    assert len(tables["users"]) == 4
    assert len(tables["sales"]) == 16
    assert len(tables["inventory_snapshots"]) == 8
    assert len(tables["forecasts"]) == 6
    assert len(tables["anomalies"]) == 4
    assert len(tables["alerts"]) == 4
    assert len(tables["recommendations"]) == 4
    assert len(tables["workflow_actions"]) == 4


@pytest.mark.parametrize(
    "config",
    [
        DatasetGenerationConfig(days=0),
        DatasetGenerationConfig(products=-1),
        DatasetGenerationConfig(stores=0),
        DatasetGenerationConfig(warehouses=-2),
        DatasetGenerationConfig(seed=0),
    ],
)
def test_generation_config_rejects_non_positive_numeric_options(
    config: DatasetGenerationConfig,
) -> None:
    with pytest.raises(ValueError, match="positive integers"):
        validate_generation_config(config)


@pytest.mark.parametrize("profile", ["small", "medium", "large"])
def test_non_demo_profiles_are_reserved_for_future_commits(
    profile: str,
) -> None:
    with pytest.raises(NotImplementedError, match="Only the 'demo'"):
        validate_generation_config(DatasetGenerationConfig(profile=profile))
