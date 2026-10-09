"""Complete-profile admission and native replay lifetime; no full-scale fit claimed."""

from copy import deepcopy
import gc
import weakref
from types import SimpleNamespace

import pytest

from data.anomalies import physical_scenarios, scenarios, source_process
from data.anomalies.example import example_plan
from data.anomalies.physical_scenarios import physical_example_plan
from data.anomalies.source_scope import require_source_scenario_scope
from data.generator.configuration import DatasetGenerationConfig
from data.inventory.run_source_dataset import default_inventory_config
from data.inventory.source_dataset_contract import SOURCE_TABLES


@pytest.mark.parametrize("products", [25, 50, 100])
def test_complete_development_is_explicitly_supported_but_old_candidate_remains_bounded(products):
    generation = DatasetGenerationConfig(profile="ai-dev", products=products, forecast_plan_days=14)
    require_source_scenario_scope(generation)
    for builder in (scenarios.build_scenario, physical_scenarios.build_physical_scenario):
        with pytest.raises(ValueError, match="5000 daily grains"):
            builder(generation, {})


@pytest.mark.parametrize("seed", [42, 137, 2026])
def test_exact_complete_final_profiles_are_admitted_without_opening_data(seed):
    require_source_scenario_scope(DatasetGenerationConfig(
        profile="ai-training", seed=seed, forecast_plan_days=14,
    ))


@pytest.mark.parametrize("changes", [
    {"days": 364}, {"products": 24}, {"products": 51}, {"stores": 4},
    {"warehouses": 2}, {"seed": 137}, {"forecast_plan_days": 0},
    {"profile": "ai-intermittent-v1"},
])
def test_reduced_or_unreviewed_large_scope_is_rejected_before_any_generation(changes, monkeypatch):
    generation = DatasetGenerationConfig(**({"profile": "ai-dev", "forecast_plan_days": 14} | changes))
    def forbidden(*args, **kwargs):
        raise AssertionError("unreviewed source scope reached generation")
    monkeypatch.setattr(source_process, "build_source_dataset", forbidden)
    with pytest.raises(ValueError, match="complete AI09 profile"):
        source_process.build_tables(generation, {}, None)


@pytest.fixture(scope="module", params=["demand", "physical"])
def native_case(request):
    generation = DatasetGenerationConfig(profile="ai-smoke", days=30, products=8, stores=3, warehouses=2,
                                         forecast_plan_days=14)
    plan = (example_plan if request.param == "demand" else physical_example_plan)(generation)
    return request.param, generation, plan


class OwnedWorld(dict):
    """Weak-referenceable owner used only to prove release of complete native results."""


def test_complete_control_world_is_released_before_injected_native_simulation(native_case, monkeypatch):
    kind, generation, plan = native_case
    module = scenarios if kind == "demand" else physical_scenarios
    builder = module.build_scenario if kind == "demand" else module.build_physical_scenario
    original = module.simulate_source_commerce
    seen = []
    def simulate(*args, **kwargs):
        if seen:
            gc.collect()
            assert seen[0]() is None, "the full normal world must not overlap the injected world"
        result = OwnedWorld(original(*args, **kwargs))
        seen.append(weakref.ref(result))
        return result
    monkeypatch.setattr(module, "simulate_source_commerce", simulate)
    result = builder(generation, plan)
    assert len(seen) == 2 and result["effects"]["status"] == "passed"
    assert all(e["affected_daily_grains"] > 0 for e in result["effects"]["episodes"])
    assert all(c["inventory_outcome_unchanged"] for c in result["effects"]["controls"]
               if c["control_type"] == "clean")


def test_source_document_discards_full_candidate_before_all_table_replay(native_case, monkeypatch):
    kind, generation, plan = native_case
    # Routing/lifetime control only. Existing publication tests exercise actual
    # 58-table Source reconstruction, writer/reader and snapshot qualification.
    owner = []
    tables = {name: [] for name in SOURCE_TABLES}
    context = SimpleNamespace(evaluated_at="2026-07-31T23:59:59.999999+00:00")
    effects = {"status": "controlled-value-not-native-evidence"}
    def candidate(*args):
        value = OwnedWorld(effects=deepcopy(effects), unrelated_full_payload=[1, 2, 3])
        owner.append(weakref.ref(value))
        return value
    def rebuild(*args, **kwargs):
        gc.collect()
        assert owner[-1]() is None
        return deepcopy(tables), context
    monkeypatch.setattr(source_process, "_build_scenario" if kind == "demand" else "_build_physical_scenario", candidate)
    monkeypatch.setattr(source_process, "build_tables", rebuild)
    result = source_process.scenario_document(tables, context, generation, default_inventory_config(generation), plan)
    assert result["effects"] == effects
    # Changing even one replayed source table still fails the existing comparison.
    forged = deepcopy(tables)
    forged["product_catalog"].append({"extra": "changed"})
    with pytest.raises(ValueError, match="independent process replay"):
        source_process.scenario_document(forged, context, generation, default_inventory_config(generation), plan)
