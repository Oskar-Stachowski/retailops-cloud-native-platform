"""Select preregistered development scenarios from a complete ordinary Source.

This helper never generates another baseline or looks at detector/model scores.
The caller must charge the Source read and bind producer/runtime provenance in
its campaign journal. The returned private plans do not authorize fits or final.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Annotated, Literal, Self

from pydantic import Field, model_validator

from data.anomalies.contract import CONTRACT_VERSION, GENERATOR_VERSION, GRAIN, AnomalyPlan
from data.anomalies.physical_contract import (
    PHYSICAL_GENERATOR,
    PHYSICAL_VERSION,
    PhysicalAnomalyPlan,
)
from data.anomalies.source_scope import require_source_scenario_scope
from data.generator.common import deterministic_uuid
from data.generator.configuration import resolve_generation_config
from data.generator.identity import canonical_cell, json_sha256
from data.generator.return_events import generate_return_events
from data.generator.simulation import simulation_entities
from data.inventory.contract import require
from data.inventory.replenishment_contract import SupplyRecord
from data.inventory.run_source_dataset import default_inventory_config
from data.inventory.source_dataset_io import read_source_dataset

if TYPE_CHECKING:
    from pathlib import Path

    from data.generator.configuration import DatasetGenerationConfig, ResolvedGenerationConfig

VERSION = "ai09-native-development-scenario-selection-1.0.0"
ROLES = ("tune", "calibration", "development_evaluation")
SHA256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class ScenarioRole(SupplyRecord):
    role: Literal["tune", "calibration", "development_evaluation"]
    start_date: str
    end_date: str

    @model_validator(mode="after")
    def bounds(self) -> Self:
        start, end = date.fromisoformat(self.start_date), date.fromisoformat(self.end_date)
        require(
            start.isoformat() == self.start_date
            and end.isoformat() == self.end_date
            and (end - start).days >= 29,
            "Each scenario role requires at least 30 canonical business dates.",
        )
        return self

    def day(self, offset: int) -> str:
        return (date.fromisoformat(self.start_date) + timedelta(days=offset)).isoformat()


class DevelopmentScenarioRecipe(SupplyRecord):
    version: Literal["ai09-native-development-scenario-selection-1.0.0"] = VERSION
    source_dataset_id: Annotated[str, Field(pattern=r"^source-sha256-[0-9a-f]{64}$")]
    generation_sha256: SHA256
    roles: Annotated[list[ScenarioRole], Field(min_length=3, max_length=3)]
    minimum_history_observations: Literal[28] = 28
    selection: Literal["native_ordinary_source_only_before_model_trials"] = (
        "native_ordinary_source_only_before_model_trials"
    )

    @model_validator(mode="after")
    def role_order(self) -> Self:
        require(tuple(r.role for r in self.roles) == ROLES, "Scenario role inventory differs.")
        require(
            all(
                a.end_date < b.start_date for a, b in zip(self.roles, self.roles[1:], strict=False)
            ),
            "Scenario roles overlap or are unordered.",
        )
        return self


def _grain(row: dict) -> tuple[str, ...]:
    return tuple(row[k] for k in GRAIN[1:])


def _window(family: str, name: str, scope: tuple[str, ...], start: str, end: str) -> dict:
    return {
        "id": deterministic_uuid("ai09_native_scenario", f"{family}:{name}:{scope}:{start}:{end}"),
        **dict(zip(GRAIN[1:], scope, strict=True)),
        "start_date": start,
        "end_date": end,
    }


def _open_grains(tables: dict) -> set[tuple[str, ...]]:
    # Native truth rows carry demand factors, not location-opening flags. The
    # independently verified observation table owns active/open availability.
    return {
        tuple(row[k] for k in GRAIN)
        for row in tables["daily_demand_observations"]
        if canonical_cell("location_open", row["location_open"])
        and canonical_cell("is_active_assortment", row["is_active_assortment"])
    }


def _candidates(tables: dict, roles: list[ScenarioRole]) -> dict:
    open_grains = _open_grains(tables)
    grouped: dict[tuple[str, ...], dict[str, dict]] = defaultdict(dict)
    for row in tables["daily_demand_truth"]:
        grouped[_grain(row)][row["business_date"]] = row
    result = {}
    for role in roles:
        eligible = []
        for grain, days in grouped.items():
            if all(role.day(i) in days and (role.day(i), *grain) in open_grains for i in range(30)):
                volume = sum(
                    int(row["latent_units"])
                    for day, row in days.items()
                    if role.start_date <= day <= role.end_date
                )
                eligible.append((grain, volume))
        result[role.role] = sorted(eligible, key=lambda item: (-item[1], item[0]))
    return result


def _demand(tables: dict, recipe: DevelopmentScenarioRecipe, candidates: dict, seed: int) -> dict:
    open_grains = _open_grains(tables)
    latent = {
        tuple(row[k] for k in GRAIN): int(row["latent_units"])
        for row in tables["daily_demand_truth"]
    }
    injections, controls, products = [], [], set()
    # Changing one product's demand redistributes the whole selling-pair basket.
    # Other products' sale IDs and later returns can therefore change too. A
    # different SKU is not sufficient evidence of an untouched later control.
    # Retain all three seven-day paired reference windows before *any* demand
    # intervention. Ordinary Source supplies the separate later-role negatives;
    # this planner does not qualify their evaluation sample or critical coverage.
    clean = recipe.roles[0]
    for role in recipe.roles:
        # Demand interventions require demand on their own dates. Physical
        # episodes instead require native returns/fulfillment on physical dates;
        # an unrelated zero on the spike date must not exclude a physical case.
        scope = next(
            (
                g
                for g, _ in candidates[role.role]
                if g[0] not in products
                and all((clean.day(i), *g) in open_grains for i in range(7))
                and all(
                    sum(latent[role.day(i), *g] for i in offsets) > 0
                    for offsets in ((8,), range(15, 18), range(22, 26))
                )
            ),
            None,
        )
        require(scope is not None, "Demand roles need three independent active products.")
        products.add(scope[0])
        controls.append(
            {
                **_window(
                    "demand",
                    role.role + "-pre-intervention-clean",
                    scope,
                    clean.day(0),
                    clean.day(6),
                ),
                "control_type": "clean",
            }
        )
        for kind, start, end, magnitude in (
            ("one_day_spike", 8, 8, "3"),
            ("multi_day_spike", 15, 17, "2"),
            ("sustained_drop", 22, 25, "0.2"),
        ):
            injections.append(
                {
                    **_window(
                        "demand", role.role + "-" + kind, scope, role.day(start), role.day(end)
                    ),
                    "injection_type": kind,
                    "shape": "constant_multiplier",
                    "magnitude": magnitude,
                    "affected_fields": ["expected_rate", "latent_units"],
                    "seed": seed,
                    "generator_version": GENERATOR_VERSION,
                }
            )
    first = min(
        (
            row
            for row in tables["daily_demand_truth"]
            if tuple(row[k] for k in GRAIN) in open_grains
        ),
        key=lambda row: tuple(row[k] for k in GRAIN),
    )
    controls.append(
        {
            **_window(
                "demand",
                "cold-start",
                _grain(first),
                first["business_date"],
                first["business_date"],
            ),
            "control_type": "insufficient_history",
        }
    )
    occupied = {(first["business_date"], *_grain(first))}
    for kind, fields in (
        ("promotion", ("promotion_factor",)),
        ("seasonality", ("weekly_factor", "seasonal_factor")),
    ):
        options = (
            row
            for row in tables["daily_demand_truth"]
            if row["product_id"] not in products
            and tuple(row[k] for k in GRAIN) not in occupied
            and any(
                role.start_date <= row["business_date"] <= role.end_date for role in recipe.roles
            )
            and tuple(row[k] for k in GRAIN) in open_grains
            and any(Decimal(row[field]) != 1 for field in fields)
        )
        row = min(options, key=lambda r: tuple(r[k] for k in GRAIN), default=None)
        require(
            row is not None, "Development recipe needs an unchanged native " + kind + " control."
        )
        controls.append(
            {
                **_window("demand", kind, _grain(row), row["business_date"], row["business_date"]),
                "control_type": kind,
            }
        )
        occupied.add(tuple(row[k] for k in GRAIN))
    return AnomalyPlan.from_payload(
        {
            "contract_version": CONTRACT_VERSION,
            "data_class": "simulation_truth",
            "generator_version": GENERATOR_VERSION,
            "seed": seed,
            "business_timezone": "UTC",
            "boundary_policy": "inclusive_business_dates",
            "overlap_policy": "reject",
            "minimum_history_observations": recipe.minimum_history_observations,
            "injections": injections,
            "controls": controls,
        }
    ).model_dump()


def _physical(
    tables: dict,
    recipe: DevelopmentScenarioRecipe,
    candidates: dict,
    effective: ResolvedGenerationConfig,
) -> tuple[dict, list[dict]]:
    # Use the original return generator on real fulfilled purchases. It owns
    # selection draws, purchased-unit caps, policies, pieces and financial tails.
    # The final paired simulator must still verify realized effects and spillover.
    factors = {
        (role.day(i), *grain): "20"
        for role in recipe.roles
        for grain, _ in candidates[role.role]
        for i in range(12, 19)
    }
    # Published Source separates private simulation parameters from products.
    # Restore them through the same helper as SourceCommerceSimulator; keep
    # actual fulfilled purchases and every other input table unchanged.
    potential = generate_return_events(
        {**tables, "products": simulation_entities(tables, "products")},
        effective,
        return_factors=factors,
    )
    extra: Counter[tuple[str, ...]] = Counter()
    for sign, rows in ((1, potential), (-1, tables["return_events"])):
        for row in rows:
            key = (row["returned_at"][:10], *_grain(row))
            if key in factors:
                extra[key] += sign * int(row["quantity"])
    del potential
    injections, controls, evidence, used = [], [], [], set()
    outcomes = sorted(
        tables["inventory_demand_outcomes"], key=lambda row: (row["occurred_at"], row["demand_id"])
    )
    for role in recipe.roles:
        eligible = {g for g, _ in candidates[role.role]}
        options = [
            (sum(extra[role.day(i), *g] for i in range(12, 19)), volume, g)
            for g, volume in candidates[role.role]
            if g[0] not in used
        ]
        options.sort(key=lambda item: (-item[0], -item[1], item[2]))
        require(
            bool(options) and options[0][0] > 0,
            "No native extra purchased-unit returns in frozen role window.",
        )
        additional, _, return_scope = options[0]
        used.add(return_scope[0])
        target = next(
            (
                row
                for row in outcomes
                if _grain(row) in eligible
                and row["product_id"] not in used
                and row["observed_quantity"] > 0
                and role.day(8) <= row["occurred_at"][:10] <= role.day(25)
            ),
            None,
        )
        require(
            target is not None, "No independently scoped fulfilled sale to censor in frozen role."
        )
        stock_scope = _grain(target)
        used.add(stock_scope[0])
        for kind, scope in (
            ("return_spike", return_scope),
            ("inventory_censored_episode", stock_scope),
        ):
            controls.append(
                {
                    **_window(
                        "physical",
                        role.role + "-" + kind + "-clean",
                        scope,
                        role.day(0),
                        role.day(6),
                    ),
                    "control_type": "clean",
                }
            )
        common = {"seed": effective.seed, "generator_version": PHYSICAL_GENERATOR}
        injections.extend(
            (
                {
                    **_window(
                        "physical", role.role + "-return", return_scope, role.day(12), role.day(18)
                    ),
                    **common,
                    "injection_type": "return_spike",
                    "shape": "return_probability_multiplier",
                    "magnitude": "20",
                    "affected_fields": ["return_selection_probability"],
                },
                {
                    **_window(
                        "physical",
                        role.role + "-stock",
                        stock_scope,
                        target["occurred_at"][:10],
                        target["occurred_at"][:10],
                    ),
                    **common,
                    "injection_type": "inventory_censored_episode",
                    "stock_location_id": target["stock_location_id"],
                    "shape": "available_stock_cap",
                    "magnitude": 0,
                    "affected_fields": ["available_qty", "observed_sales_units"],
                },
            )
        )
        evidence.append(
            {
                "role": role.role,
                "potential_additional_return_units": additional,
                "stock_cap_baseline_demand_id": target["demand_id"],
                "stock_cap_baseline_fulfilled_units": target["observed_quantity"],
            }
        )
    return PhysicalAnomalyPlan.from_payload(
        {
            "contract_version": PHYSICAL_VERSION,
            "data_class": "simulation_truth",
            "generator_version": PHYSICAL_GENERATOR,
            "seed": effective.seed,
            "business_timezone": "UTC",
            "boundary_policy": "inclusive_business_dates",
            "overlap_policy": "reject_shared_stock_and_return_spillover",
            "injections": injections,
            "controls": controls,
        }
    ).model_dump(), evidence


def prepare_development_scenarios(
    directory: Path, generation: DatasetGenerationConfig, recipe: DevelopmentScenarioRecipe
) -> dict:
    """Independently read every native table, then resolve both frozen recipes.

    Exact full AI09 development profiles and bounded native controls are allowed.
    Final configurations are rejected before opening the directory. Production
    callers must additionally bind journal costs, clean producer pins and roles.
    """
    recipe = DevelopmentScenarioRecipe.model_validate(recipe.model_dump())
    effective = resolve_generation_config(generation)
    require(effective.profile != "ai-training", "Development planner cannot open final Source.")
    require_source_scenario_scope(generation)
    require(
        date(2025, 8, 1) <= effective.start_date <= effective.end_date <= date(2026, 7, 31),
        "Planner accepts only the already exposed development dates.",
    )
    require(
        effective.forecast_plan_days == 14
        and effective.seed == 42
        and recipe.generation_sha256 == json_sha256(effective.parameters())
        and all(
            effective.start_date + timedelta(days=28)
            <= date.fromisoformat(r.start_date)
            <= date.fromisoformat(r.end_date)
            <= effective.end_date
            for r in recipe.roles
        ),
        "Development recipe history, seed, roles or generation binding differs.",
    )
    tables, manifest = read_source_dataset(directory)
    descriptor = manifest["descriptor"]
    require(
        manifest["schema_version"] == "2.7.0"
        and manifest["facts_ready"]
        and manifest["dataset_id"] == recipe.source_dataset_id
        and descriptor["resolved_parameters"] == effective.parameters()
        and descriptor["inventory_configuration_sha256"]
        == json_sha256(default_inventory_config(generation).model_dump()),
        "Development planning requires the exact ordinary native Source and inventory configuration.",
    )
    candidates = _candidates(tables, recipe.roles)
    demand = _demand(tables, recipe, candidates, effective.seed)
    physical, evidence = _physical(tables, recipe, candidates, effective)
    return {
        "version": VERSION,
        "data_class": "simulation_truth",
        "recipe": recipe.model_dump(),
        "recipe_sha256": json_sha256(recipe.model_dump()),
        "source_dataset_id": manifest["dataset_id"],
        "source_provenance": manifest["provenance"],
        "source_tables": descriptor["tables"],
        "inventory_configuration_sha256": descriptor["inventory_configuration_sha256"],
        "plans": {"demand": demand, "physical": physical},
        "plan_sha256": {"demand": json_sha256(demand), "physical": json_sha256(physical)},
        "selection_evidence": evidence,
        "realized_effects_verified": False,
        "critical_coverage_verified": False,
        "model_fit_authorized": False,
        "final_test_access_authorized": False,
        "stage_ready": False,
    }
