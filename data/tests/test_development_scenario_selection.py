"""Planner bindings and failure boundaries; controlled rows are not native evidence."""

from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path
from uuid import UUID

import pytest

from data.anomalies import development_plan as planner
from data.generator.configuration import DatasetGenerationConfig, resolve_generation_config
from data.generator.identity import json_sha256
from data.generator.simulation import simulation_entities
from data.inventory.run_source_dataset import default_inventory_config


def case():
    generation = DatasetGenerationConfig(profile="ai-smoke", days=128, products=8, stores=2,
                                         warehouses=2, forecast_plan_days=14)
    effective = resolve_generation_config(generation)
    roles = [planner.ScenarioRole(role=role,
             start_date=(effective.start_date + timedelta(days=28 + i * 32)).isoformat(),
             end_date=(effective.start_date + timedelta(days=57 + i * 32)).isoformat())
             for i, role in enumerate(planner.ROLES)]
    recipe = planner.DevelopmentScenarioRecipe(source_dataset_id="source-sha256-" + "a" * 64,
             generation_sha256=json_sha256(effective.parameters()), roles=roles)
    rows = []
    outcomes = []
    for product in range(1, 9):
        grain = {"product_id": str(UUID(int=product)), "selling_location_id": str(UUID(int=100)),
                 "channel": "online"}
        for day in range(128):
            stamp = (effective.start_date + timedelta(days=day)).isoformat()
            rows.append(dict(grain, business_date=stamp, location_open="true", latent_units="10",
                             promotion_factor="1.5", weekly_factor="1.1", seasonal_factor="1"))
            outcomes.append(dict(grain, occurred_at=stamp + "T12:00:00+00:00",
                                 stock_location_id=str(UUID(int=200)), observed_quantity=3,
                                 demand_id=str(UUID(int=1000 + 128 * product + day))))
    observations = [{k: row[k] for k in planner.GRAIN} | {"location_open": row.pop("location_open"), "is_active_assortment": "true"} for row in rows]
    tables = {"daily_demand_truth": rows, "daily_demand_observations": observations,
              "inventory_demand_outcomes": outcomes, "return_events": []}
    tables["products"] = [{"id": str(UUID(int=i)), "sku": f"TEST-{i}"} for i in range(1, 9)]
    tables["product_simulation_parameters"] = [
        {"product_id": p["id"], "demand_class": "long_tail", "demand_weight": "1",
         "price_elasticity": "1", "seasonal_pattern": "weekly_sensitive", "return_rate": "0.02"}
        for p in tables["products"]]
    manifest = {"schema_version": "2.7.0", "facts_ready": True,
                "dataset_id": recipe.source_dataset_id,
                "descriptor": {"resolved_parameters": effective.parameters(), "tables": {},
                    "inventory_configuration_sha256": json_sha256(default_inventory_config(generation).model_dump())},
                "provenance": {"controlled": True}}
    return generation, recipe, tables, manifest


def install(monkeypatch, tables, manifest, *, returns=True):
    calls = []
    def read(directory):
        calls.append(directory)
        return tables, manifest
    def potential(actual, effective, *, return_factors):
        assert actual is not tables
        assert actual["products"] == simulation_entities(tables, "products")
        assert all("return_rate" not in row for row in tables["products"])
        assert all(actual[name] is rows for name, rows in tables.items() if name != "products")
        return [{"returned_at": day + "T12:00:00+00:00", "product_id": product,
                 "selling_location_id": location, "channel": channel, "quantity": "2"}
                for day, product, location, channel in sorted(return_factors)] if returns else []
    monkeypatch.setattr(planner, "read_source_dataset", read)
    monkeypatch.setattr(planner, "generate_return_events", potential)
    return calls


def test_native_plan_shapes_cover_every_role_and_retain_original_complete_input(monkeypatch):
    generation, recipe, tables, manifest = case()
    before = deepcopy(tables)
    calls = install(monkeypatch, tables, manifest)
    result = planner.prepare_development_scenarios(Path("/controlled"), generation, recipe)
    assert calls == [Path("/controlled")] and tables == before
    for family, count in (("demand", 9), ("physical", 6)):
        plan = result["plans"][family]
        assert len(plan["injections"]) == count
        assert json_sha256(plan) == result["plan_sha256"][family]
        assert len({w["product_id"] for w in plan["injections"]}) == (3 if family == "demand" else 6)
        for role in recipe.roles:
            types = {w["injection_type"] for w in plan["injections"]
                     if role.start_date <= w["start_date"] <= w["end_date"] <= role.end_date}
            assert types == ({"one_day_spike", "multi_day_spike", "sustained_drop"} if family == "demand"
                             else {"return_spike", "inventory_censored_episode"})
    assert not result["realized_effects_verified"] and not result["model_fit_authorized"]
    assert not result["critical_coverage_verified"] and not result["final_test_access_authorized"]


def test_demand_clean_references_precede_all_interventions_despite_different_products(monkeypatch):
    generation, recipe, tables, manifest = case()
    install(monkeypatch, tables, manifest)
    result = planner.prepare_development_scenarios(Path("/controlled"), generation, recipe)
    plan = result["plans"]["demand"]
    controls = [control for control in plan["controls"] if control["control_type"] == "clean"]
    assert len(controls) == 3
    assert {control["product_id"] for control in controls} == {i["product_id"] for i in plan["injections"]}
    for control in controls:
        assert control["start_date"] == recipe.roles[0].day(0)
        assert control["end_date"] == recipe.roles[0].day(6)
        assert control["end_date"] < min(i["start_date"] for i in plan["injections"])
    # Paired references are not a claim of clean sample coverage in later roles.
    assert not result["critical_coverage_verified"]


def test_selection_is_independent_of_native_row_order(monkeypatch):
    generation, recipe, tables, manifest = case()
    install(monkeypatch, tables, manifest)
    first = planner.prepare_development_scenarios(Path("/controlled"), generation, recipe)
    for rows in tables.values(): rows.reverse()
    second = planner.prepare_development_scenarios(Path("/controlled"), generation, recipe)
    assert first == second


@pytest.mark.parametrize("change", ["final", "changed_config", "early_role", "outside_history", "unreviewed_size"])
def test_unauthorized_or_unbound_recipe_is_rejected_before_source_io(monkeypatch, change):
    generation, recipe, tables, manifest = case()
    calls = install(monkeypatch, tables, manifest)
    if change == "final": generation = DatasetGenerationConfig(profile="ai-training", forecast_plan_days=14)
    elif change == "changed_config": recipe = recipe.model_copy(update={"generation_sha256": "b" * 64})
    elif change == "early_role":
        roles = list(recipe.roles)
        roles[0] = roles[0].model_copy(update={"start_date": resolve_generation_config(generation).start_date.isoformat()})
        recipe = recipe.model_copy(update={"roles": roles})
    elif change == "outside_history":
        roles = list(recipe.roles); roles[-1] = roles[-1].model_copy(update={"end_date": "2099-01-01"})
        recipe = recipe.model_copy(update={"roles": roles})
    else: generation = DatasetGenerationConfig(profile="ai-dev", products=26, forecast_plan_days=14)
    with pytest.raises(ValueError): planner.prepare_development_scenarios(Path("/controlled"), generation, recipe)
    assert calls == []


@pytest.mark.parametrize("change", ["planned_source", "not_ready", "source_id", "configuration", "inventory"])
def test_independently_read_source_must_match_the_declared_ordinary_parent(monkeypatch, change):
    generation, recipe, tables, manifest = case()
    if change == "planned_source": manifest["schema_version"] = "2.8.0"
    elif change == "not_ready": manifest["facts_ready"] = False
    elif change == "source_id": manifest["dataset_id"] = "source-sha256-" + "b" * 64
    elif change == "configuration": manifest["descriptor"]["resolved_parameters"]["products"] = 7
    else: manifest["descriptor"]["inventory_configuration_sha256"] = "b" * 64
    calls = install(monkeypatch, tables, manifest)
    with pytest.raises(ValueError, match="exact ordinary native Source"):
        planner.prepare_development_scenarios(Path("/controlled"), generation, recipe)
    assert calls == [Path("/controlled")]


@pytest.mark.parametrize("change", ["closed", "zero", "missing_day", "no_returns", "no_fulfillment", "too_few_products"])
def test_unrealizable_selection_fails_without_weaker_or_shorter_fallback(monkeypatch, change):
    generation, recipe, tables, manifest = case()
    if change == "closed":
        for row in tables["daily_demand_observations"]: row["location_open"] = "false"
    elif change == "zero":
        for row in tables["daily_demand_truth"]: row["latent_units"] = "0"
    elif change == "missing_day":
        tables["daily_demand_truth"] = [r for r in tables["daily_demand_truth"] if r["business_date"] != recipe.roles[0].day(3)]
    elif change == "no_fulfillment":
        for row in tables["inventory_demand_outcomes"]: row["observed_quantity"] = 0
    elif change == "too_few_products":
        tables["daily_demand_truth"] = [r for r in tables["daily_demand_truth"] if r["product_id"] in {str(UUID(int=i)) for i in range(1, 5)}]
    calls = install(monkeypatch, tables, manifest, returns=change != "no_returns")
    with pytest.raises(ValueError): planner.prepare_development_scenarios(Path("/controlled"), generation, recipe)
    assert len(calls) == 1


def test_original_reader_failure_is_not_replaced_with_unverified_tables(monkeypatch):
    generation, recipe, _, _ = case()
    def reject(*args): raise ValueError("native independent report replay rejected")
    monkeypatch.setattr(planner, "read_source_dataset", reject)
    with pytest.raises(ValueError, match="native independent report"):
        planner.prepare_development_scenarios(Path("/controlled"), generation, recipe)


def test_weekly_closures_cannot_be_filled_or_shortened_into_continuous_scenario_windows(monkeypatch):
    generation, recipe, tables, manifest = case()
    closed = set()
    for row in tables["daily_demand_observations"]:
        if date.fromisoformat(row["business_date"]).weekday() == 6:
            row["location_open"] = "false"
            closed.add(tuple(row[key] for key in planner.GRAIN))
    # Native demand truth omits closed dates; observations retain their calendar.
    tables["daily_demand_truth"] = [row for row in tables["daily_demand_truth"]
                                   if tuple(row[key] for key in planner.GRAIN) not in closed]
    before = deepcopy(tables)
    install(monkeypatch, tables, manifest)
    with pytest.raises(ValueError, match="Demand roles"):
        planner.prepare_development_scenarios(Path("/controlled"), generation, recipe)
    assert tables == before


def test_resealed_ai_dev_with_future_dates_cannot_bypass_final_access_guard(monkeypatch):
    _, recipe, tables, manifest = case()
    generation = DatasetGenerationConfig(profile="ai-dev", start_date=date(2026, 8, 1),
                                         end_date=date(2027, 7, 31), forecast_plan_days=14)
    effective = resolve_generation_config(generation)
    roles = [r.model_copy(update={"start_date": (effective.start_date + timedelta(days=28 + i * 32)).isoformat(),
                                  "end_date": (effective.start_date + timedelta(days=57 + i * 32)).isoformat()})
             for i, r in enumerate(recipe.roles)]
    recipe = recipe.model_copy(update={"generation_sha256": json_sha256(effective.parameters()), "roles": roles})
    calls = install(monkeypatch, tables, manifest)
    with pytest.raises(ValueError, match="already exposed development"):
        planner.prepare_development_scenarios(Path("/controlled"), generation, recipe)
    assert calls == []


def test_physical_eligibility_does_not_require_demand_on_an_unrelated_spike_date(monkeypatch):
    generation, recipe, tables, manifest = case()
    dates = {r.day(8) for r in recipe.roles}
    for row in tables["daily_demand_truth"]:
        if row["business_date"] in dates: row["latent_units"] = "0"
    for row in tables["inventory_demand_outcomes"]:
        if row["occurred_at"][:10] in dates: row["observed_quantity"] = 0
    install(monkeypatch, tables, manifest)
    candidates = planner._candidates(tables, recipe.roles)
    physical, evidence = planner._physical(tables, recipe, candidates, resolve_generation_config(generation))
    assert len(physical["injections"]) == 6 and all(e["stock_cap_baseline_fulfilled_units"] > 0 for e in evidence)
    with pytest.raises(ValueError, match="Demand roles"):
        planner._demand(tables, recipe, candidates, 42)
