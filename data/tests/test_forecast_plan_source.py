"""Known future plans extend forecast support without creating future observations."""

from copy import deepcopy
from dataclasses import replace
from datetime import date, timedelta
import json

import pytest

from data.generator.configuration import (
    DatasetGenerationConfig,
    FORECAST_PLAN_VERSION,
    requested_parameters,
    resolve_generation_config,
)
from data.generator.dimension_quality import validate_dimensions
from data.generator.manifest_v2 import config_from_parameters
from data.generator.pricing_quality import validate_pricing
from data.inventory.run_source_dataset import build_source_dataset, default_inventory_config
from data.inventory.source_dataset_io import read_source_dataset, write_source_dataset


@pytest.fixture(scope="module")
def planned():
    generation = DatasetGenerationConfig(
        profile="ai-smoke", days=35, products=4, stores=3, warehouses=2,
        end_date=date(2026, 10, 1), seed=720051, forecast_plan_days=14,
    )
    config = default_inventory_config(generation)
    tables, context = build_source_dataset(generation, config)
    return generation, config, tables, context


def test_explicit_plan_mode_is_bounded_and_preserves_legacy_parameter_shapes():
    legacy = DatasetGenerationConfig(profile="ai-smoke", days=35)
    assert "forecast_plan_days" not in requested_parameters(legacy)
    assert "forecast_plan_version" not in resolve_generation_config(legacy).parameters()
    planned = replace(legacy, forecast_plan_days=14)
    raw = requested_parameters(planned)
    assert raw["forecast_plan_version"] == FORECAST_PLAN_VERSION
    assert config_from_parameters(raw) == planned
    for value in (-1, 15, True, None):
        with pytest.raises(ValueError, match="Forecast plans"):
            resolve_generation_config(replace(legacy, forecast_plan_days=value))
    with pytest.raises(ValueError, match="Forecast plans"):
        resolve_generation_config(DatasetGenerationConfig(profile="small", forecast_plan_days=14))
    for mutation in ({"forecast_plan_version": "unknown"}, {"forecast_plan_days": 0}):
        with pytest.raises(ValueError, match="Forecast plan parameters"):
            config_from_parameters({**raw, **mutation})


def test_future_calendar_and_periods_are_known_but_observations_end_at_cutoff(planned):
    generation, _, tables, context = planned
    effective = resolve_generation_config(generation)
    last = effective.planning_end_date.isoformat()
    assert max(r["business_date"] for r in tables["business_calendar"]) == last
    assert max(r["business_date"] for r in tables["category_calendar"]) == last
    assert len(tables["business_calendar"]) == effective.planning_days * effective.stores
    origin = generation.end_date.isoformat() + "T23:59:59+00:00"
    for name in ("business_calendar", "category_calendar", "channel_assignments", "fulfillment_routes", "assortment"):
        assert all(r["available_at"] < origin for r in tables[name])
    for name in ("daily_demand_observations", "daily_demand_versions", "daily_demand_truth"):
        assert max(r["business_date"] for r in tables[name]) == generation.end_date.isoformat()
    assert context.projection.end_at == (generation.end_date + timedelta(days=1)).isoformat() + "T00:00:00+00:00"


def test_adding_known_future_plans_preserves_generated_historical_observations(planned):
    generation, _, tables, _ = planned
    legacy = replace(generation, forecast_plan_days=0)
    previous, _ = build_source_dataset(legacy, default_inventory_config(legacy))
    for name in ("sales", "orders", "order_items", "daily_demand_observations", "daily_demand_versions", "daily_demand_truth", "inventory_sales", "inventory_ledger"):
        assert tables[name] == previous[name], name


@pytest.mark.parametrize("fault", ["missing_calendar", "extra_calendar", "period_exceeds_plan"])
def test_future_support_cannot_escape_declared_plans_or_hide_missing_days(planned, fault):
    generation, _, tables, _ = planned
    changed = deepcopy(tables)
    if fault == "missing_calendar":
        changed["business_calendar"].pop()
    elif fault == "extra_calendar":
        extra = dict(changed["business_calendar"][-1])
        extra["business_date"] = "2026-10-16"
        changed["business_calendar"].append(extra)
    else:
        changed["channel_assignments"][-1]["effective_to"] = "2026-10-17"
    with pytest.raises(ValueError):
        validate_dimensions(changed, resolve_generation_config(generation))


@pytest.mark.parametrize("fault", ["missing", "available_after_origin"])
def test_future_price_must_be_complete_and_known_by_observation_origin(planned, fault):
    generation, _, tables, _ = planned
    changed = deepcopy(tables)
    future = [r for r in changed["price_plans"] if r["effective_from"] > generation.end_date.isoformat()]
    assert future
    if fault == "missing":
        changed["price_plans"] = [r for r in changed["price_plans"] if r not in future]
    else:
        for row in future:
            row["known_at"] = row["available_at"] = "2026-10-03T00:00:00+00:00"
    with pytest.raises(ValueError):
        validate_pricing(changed, resolve_generation_config(generation))


def test_source_roundtrip_binds_plan_horizon_and_recomputes_all_hard_gates(planned, tmp_path):
    generation, config, tables, context = planned
    path = write_source_dataset(tables, context, generation, config, tmp_path)
    restored, manifest = read_source_dataset(path)
    assert restored.keys() == tables.keys()
    assert manifest["descriptor"]["generator_version"] == "0.9.1"
    assert manifest["requested_parameters"]["forecast_plan_days"] == 14
    assert manifest["descriptor"]["resolved_parameters"]["end_date"] == "2026-10-01"
    assert manifest["descriptor"]["resolved_parameters"]["forecast_plan_version"] == FORECAST_PLAN_VERSION
    report = json.loads((path / "source_report.json").read_text())
    assert len(report["checks"]) == 36
    assert all(r["status"] == "passed" for r in report["checks"])
    assert manifest["facts_ready"] and not manifest["source_ready"] and not manifest["model_ready"]
