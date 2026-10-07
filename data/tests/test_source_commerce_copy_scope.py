"""Differential native parity with the complete-copy implementation; no model fits."""

from copy import deepcopy

import pytest

from data.anomalies.physical_contract import PhysicalAnomalyPlan
from data.anomalies.physical_scenarios import physical_example_plan
from data.generator.configuration import (
    DatasetGenerationConfig,
    resolve_generation_config,
)
from data.generator.main import build_dataset
from data.inventory import source_bridge
from data.inventory.run_source_dataset import default_inventory_config


@pytest.mark.parametrize("seed,plans", [(42, 0), (137, 0), (2026, 0), (42, 14)])
def test_native_commerce_is_identical_to_complete_copy(seed, plans, monkeypatch):
    generation = DatasetGenerationConfig(
        profile="ai-smoke",
        days=30,
        products=2,
        stores=1,
        warehouses=1,
        seed=seed,
        forecast_plan_days=plans,
    )
    candidate = build_dataset(generation)
    original = deepcopy(candidate)
    config = default_inventory_config(generation)
    actual = source_bridge.simulate_source_commerce(
        candidate, resolve_generation_config(generation), config
    )
    assert candidate == original
    monkeypatch.setattr(source_bridge, "_copy_commerce_inputs", deepcopy)
    expected = source_bridge.simulate_source_commerce(
        candidate, resolve_generation_config(generation), config
    )
    assert actual == expected
    assert candidate == original
    # Shared input/output records would allow a later caller to change parents.
    actual["commerce"]["product_catalog"][0]["name"] = "changed output only"
    assert candidate == original


def test_physical_native_commerce_is_identical_to_complete_copy(monkeypatch):
    generation = DatasetGenerationConfig(
        profile="ai-smoke",
        days=30,
        products=8,
        stores=3,
        warehouses=2,
        seed=42,
    )
    candidate = build_dataset(generation)
    original = deepcopy(candidate)
    plan = PhysicalAnomalyPlan.from_payload(physical_example_plan(generation))
    config = default_inventory_config(generation)
    actual = source_bridge.simulate_source_commerce(
        candidate,
        resolve_generation_config(generation),
        config,
        physical_plan=plan,
    )
    assert candidate == original
    monkeypatch.setattr(source_bridge, "_copy_commerce_inputs", deepcopy)
    expected = source_bridge.simulate_source_commerce(
        candidate,
        resolve_generation_config(generation),
        config,
        physical_plan=plan,
    )
    assert actual == expected
    assert candidate == original


def test_unused_candidate_tables_are_not_copied_and_required_inputs_are_detached():
    class Unused:
        def __deepcopy__(self, memo):
            raise AssertionError("Unused candidate output was copied")

    candidate = {
        "product_catalog": [{"id": "one"}],
        "promotion_effect_truth": [{"promotion_plan_id": "one"}],
        "product_simulation_parameters": [{"product_id": "one"}],
        "store_simulation_parameters": [{"legacy_store_id": "one"}],
        "forecasts": Unused(),
        "daily_demand_truth": Unused(),
        "users": Unused(),
    }
    copied = source_bridge._copy_commerce_inputs(candidate)
    assert set(copied) == {
        "product_catalog",
        "promotion_effect_truth",
        "product_simulation_parameters",
        "store_simulation_parameters",
    }
    for name in copied:
        assert copied[name] == candidate[name]
        assert copied[name] is not candidate[name]
        assert copied[name][0] is not candidate[name][0]
