"""Complete native planning and paired outcomes on a previously exposed tiny scope.

These controls do not qualify Project 25/50/100 capacity, coverage or quality.
"""

from datetime import timedelta

import pytest

from data.anomalies.development_plan import DevelopmentScenarioRecipe, ScenarioRole, prepare_development_scenarios
from data.anomalies.physical_scenarios import build_physical_scenario
from data.anomalies.scenarios import build_scenario
from data.generator.configuration import DatasetGenerationConfig, resolve_generation_config
from data.generator.identity import json_sha256
from data.inventory.run_source_dataset import build_source_dataset, default_inventory_config
from data.inventory.source_dataset_io import load_json, write_source_dataset
from data.inventory.source_dataset_contract import MANIFEST_FILENAME


@pytest.fixture(scope="module")
def native_preparation(tmp_path_factory):
    generation = DatasetGenerationConfig(profile="ai-smoke", days=128, products=8, stores=2,
                                         warehouses=2, forecast_plan_days=14)
    effective = resolve_generation_config(generation)
    configuration = default_inventory_config(generation)
    tables, context = build_source_dataset(generation, configuration)
    parent = write_source_dataset(tables, context, generation, configuration,
                                  tmp_path_factory.mktemp("native-planning"))
    del tables
    manifest = load_json(parent / MANIFEST_FILENAME)
    recipe = DevelopmentScenarioRecipe(source_dataset_id=manifest["dataset_id"],
        generation_sha256=json_sha256(effective.parameters()), roles=[
            ScenarioRole(role=role, start_date=(effective.start_date + timedelta(days=28 + i * 32)).isoformat(),
                         end_date=(effective.start_date + timedelta(days=57 + i * 32)).isoformat())
            for i, role in enumerate(("tune", "calibration", "development_evaluation"))])
    result = prepare_development_scenarios(parent, generation, recipe)
    return generation, result


@pytest.mark.parametrize("family", ["demand", "physical"])
def test_native_selected_grains_produce_every_real_role_effect_and_clean_control(native_preparation, family):
    generation, result = native_preparation
    plan = result["plans"][family]
    candidate = (build_scenario if family == "demand" else build_physical_scenario)(generation, plan)
    assert candidate["effects"]["status"] == "passed"
    assert len(candidate["effects"]["episodes"]) == (9 if family == "demand" else 6)
    assert all(e["affected_daily_grains"] > 0 for e in candidate["effects"]["episodes"])
    assert all(c["inventory_outcome_unchanged"] for c in candidate["effects"]["controls"]
               if c["control_type"] == "clean")
    assert len(result["source_tables"]) == 58
    assert all(e["potential_additional_return_units"] > 0 for e in result["selection_evidence"])
    assert all(e["stock_cap_baseline_fulfilled_units"] > 0 for e in result["selection_evidence"])
    assert not result["stage_ready"]
