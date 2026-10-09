"""Complete native planning and paired outcomes on a previously exposed tiny scope.

These controls do not qualify Project 25/50/100 capacity, coverage or quality.
"""

from datetime import timedelta

import pytest

from data.anomalies.development_plan import DevelopmentScenarioRecipe, ScenarioRole, prepare_development_scenarios
from data.anomalies.source_contract import SCENARIO_PATH
from data.anomalies.source_process import build_tables
from data.generator.configuration import DatasetGenerationConfig, resolve_generation_config
from data.generator.identity import json_sha256
from data.inventory.run_source_dataset import build_source_dataset, default_inventory_config
from data.inventory.source_dataset_io import load_json, read_source_dataset, write_source_dataset
from data.inventory.source_dataset_contract import MANIFEST_FILENAME


@pytest.fixture(scope="module")
def native_preparation(tmp_path_factory):
    # The first two native selling pairs are Sunday-closed stores. The third
    # adds online intake, also present in the full five-pair AI09 profile.
    # Seven-day physical episodes and clean controls cannot fit store calendars;
    # keep their duration and the real calendar instead of weakening either.
    generation = DatasetGenerationConfig(profile="ai-smoke", days=128, products=8, stores=3,
                                         warehouses=2, forecast_plan_days=14)
    effective = resolve_generation_config(generation)
    configuration = default_inventory_config(generation)
    tables, context = build_source_dataset(generation, configuration)
    observations = tables["daily_demand_observations"]
    assert {row["channel"] for row in observations} == {"store", "online"}
    assert any(row["location_open"] == "false" for row in observations if row["channel"] == "store")
    assert all(row["location_open"] == "true" for row in observations if row["channel"] == "online")
    del observations
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
def test_native_selected_grains_produce_every_real_role_effect_and_clean_control(native_preparation, family, tmp_path):
    generation, result = native_preparation
    plan = result["plans"][family]
    configuration = default_inventory_config(generation)
    tables, context = build_tables(generation, plan, configuration)
    parent = write_source_dataset(tables, context, generation, configuration, tmp_path,
                                  scenario_plan=plan)
    del tables
    restored, manifest = read_source_dataset(parent)
    assert len(restored) == 58
    assert manifest["schema_version"] == "2.8.0" and manifest["facts_ready"]
    assert manifest["descriptor"]["scenario_plan_sha256"] == result["plan_sha256"][family]
    # Both original writer and reader replay the paired process, all Source
    # tables, episode effects and spillover. Inspect that verified document.
    scenario = load_json(parent / SCENARIO_PATH)
    assert scenario["plan"] == plan
    effects = scenario["effects"]
    assert effects["status"] == "passed"
    assert len(effects["episodes"]) == (9 if family == "demand" else 6)
    assert all(e["affected_daily_grains"] > 0 for e in effects["episodes"])
    assert all(c["inventory_outcome_unchanged"] for c in effects["controls"]
               if c["control_type"] == "clean")
    assert len(result["source_tables"]) == 58
    assert all(e["potential_additional_return_units"] > 0 for e in result["selection_evidence"])
    assert all(e["stock_cap_baseline_fulfilled_units"] > 0 for e in result["selection_evidence"])
    assert not result["stage_ready"]
