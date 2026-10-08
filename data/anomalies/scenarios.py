"""Apply injections before baskets and inventory; compare against a paired control run."""

from __future__ import annotations

from collections import Counter
from decimal import Decimal
from typing import TYPE_CHECKING

from data.anomalies.contract import GENERATOR_VERSION, GRAIN, AnomalyPlan
from data.generator.configuration import requested_parameters, resolve_generation_config
from data.generator.demand_model import expected_demand
from data.generator.demand_quality import validate_demand
from data.generator.identity import json_sha256
from data.generator.main import build_dataset
from data.inventory.contract import require
from data.inventory.run_source_dataset import default_inventory_config
from data.inventory.source_bridge import simulate_source_commerce

if TYPE_CHECKING:
    from data.generator.configuration import DatasetGenerationConfig
    from data.inventory.source_contract import SourceInventoryConfig


def row_key(row: dict) -> tuple[str, ...]:
    return tuple(row[field] for field in GRAIN)


def evaluate_effects(normal: dict, injected: dict, plan: AnomalyPlan) -> dict:
    """Validate process effects without turning a detector's output into truth."""
    before = {row_key(r): r for r in normal["daily_demand_truth"]}
    after = {row_key(r): r for r in injected["daily_demand_truth"]}
    require(before.keys() == after.keys(), "Injection changed lifecycle/open demand coverage.")
    factors = {key: i.magnitude for i in plan.injections for key in i.daily_keys()}
    for key, row in before.items():
        changed = after[key]
        expected = {"anomaly_factor", "expected_rate", "latent_units"} if key in factors else set()
        require(
            all(row[field] == changed[field] for field in row if field not in expected),
            "Injection changed unrelated process factors or random draws.",
        )
        require(
            changed["anomaly_factor"] == factors.get(key, "1")
            and Decimal(changed["expected_rate"])
            == expected_demand({**row, "anomaly_factor": factors.get(key, "1")}),
            "Injection labels do not agree with the applied demand process.",
        )
    episodes = []
    for injection in plan.injections:
        keys = injection.daily_keys()
        baseline = sum(int(before[k]["latent_units"]) for k in keys)
        actual = sum(int(after[k]["latent_units"]) for k in keys)
        require(baseline != actual, "Injection has no sampled demand effect; it is not an episode.")
        episodes.append(
            {
                **injection.model_dump(),
                "data_class": "simulation_truth",
                "baseline_latent_units": baseline,
                "injected_latent_units": actual,
                "affected_daily_grains": len(keys),
            }
        )
    controls = []
    for control in plan.controls:
        keys = control.daily_keys()
        require(
            all(before[k] == after[k] for k in keys), "Injection touched a control process window."
        )
        if control.control_type == "promotion":
            require(
                any(Decimal(before[k]["promotion_factor"]) != 1 for k in keys),
                "Promotion control has no actual promotion process effect.",
            )
        elif control.control_type == "seasonality":
            require(
                any(
                    Decimal(before[k]["weekly_factor"]) != 1
                    or Decimal(before[k]["seasonal_factor"]) != 1
                    for k in keys
                ),
                "Seasonality control has no actual calendar process effect.",
            )
        elif control.control_type == "insufficient_history":
            require(
                all(
                    sum(k[1:] == key[1:] and k[0] < key[0] for k in before)
                    < plan.minimum_history_observations
                    for key in keys
                ),
                "Insufficient-history control already has sufficient prior open observations.",
            )
        controls.append({**control.model_dump(), "unchanged_daily_grains": len(keys)})
    return {"episodes": episodes, "controls": controls, "status": "passed"}


def physical_effects(source: dict, keys: tuple[tuple[str, ...], ...]) -> dict:
    outcomes = source["simulation_truth"]["demand_outcomes"]
    arrivals = {
        r["demand_id"]: r for r in source["effective_configuration"]["scenario"]["demand_arrivals"]
    }
    counts: Counter[str] = Counter()
    for outcome in outcomes:
        arrival = arrivals[outcome["demand_id"]]
        key = (
            arrival["occurred_at"][:10],
            arrival["product_id"],
            arrival["selling_location_id"],
            arrival["channel"],
        )
        if key in keys:
            for field in ("latent_quantity", "observed_quantity", "lost_sales_quantity"):
                counts[field] += outcome[field]
    require(
        counts["latent_quantity"] == counts["observed_quantity"] + counts["lost_sales_quantity"],
        "Injected window violates shared inventory conservation.",
    )
    return {
        field: counts[field]
        for field in ("latent_quantity", "observed_quantity", "lost_sales_quantity")
    }


def build_scenario(
    generation: DatasetGenerationConfig,
    payload: dict,
    inventory_config: SourceInventoryConfig | None = None,
) -> dict:
    effective = resolve_generation_config(generation)
    require(
        effective.profile.startswith("ai-")
        and effective.days * effective.products * effective.stores <= 5000,
        "This candidate runner is bounded to AI profiles with at most 5000 daily grains.",
    )
    plan = AnomalyPlan.from_payload(payload)
    normal = build_dataset(generation)
    injected = build_dataset(generation, anomaly_plan=plan)
    validate_demand(normal, effective)
    validate_demand(injected, effective, anomaly_plan=plan)
    effects = evaluate_effects(normal, injected, plan)
    config = inventory_config or default_inventory_config(generation)
    normal_source = simulate_source_commerce(normal, effective, config)
    source = simulate_source_commerce(injected, effective, config, anomaly_plan=plan)
    for episode, injection in zip(effects["episodes"], plan.injections, strict=True):
        episode["normal_inventory_outcome"] = physical_effects(
            normal_source, injection.daily_keys()
        )
        episode["injected_inventory_outcome"] = physical_effects(source, injection.daily_keys())
        require(
            episode["injected_inventory_outcome"]["latent_quantity"]
            == episode["injected_latent_units"],
            "Injection was not consumed by the actual chronological process.",
        )
    for control, window in zip(effects["controls"], plan.controls, strict=True):
        control["normal_inventory_outcome"] = physical_effects(normal_source, window.daily_keys())
        control["injected_inventory_outcome"] = physical_effects(source, window.daily_keys())
        control["inventory_outcome_unchanged"] = (
            control["normal_inventory_outcome"] == control["injected_inventory_outcome"]
        )
        if window.control_type == "clean":
            require(
                control["inventory_outcome_unchanged"],
                "Clean control was affected by inventory spillover.",
            )
    return {
        "scope": "AI 07.1a demand scenarios only",
        "generator_version": GENERATOR_VERSION,
        "generation": effective.parameters(),
        "requested_generation": requested_parameters(generation),
        "plan": plan.model_dump(),
        "inventory_configuration": config.model_dump(),
        "normal_candidate_sha256": json_sha256(normal),
        "normal_commerce_sha256": json_sha256(normal_source["commerce"]),
        "commerce": source["commerce"],
        "inventory": source["inventory"],
        "simulation_truth": {
            "process": source["simulation_truth"],
            "daily_demand_truth": injected["daily_demand_truth"],
            "product_simulation_parameters": injected["product_simulation_parameters"],
            "store_simulation_parameters": injected["store_simulation_parameters"],
            "promotion_effect_truth": injected["promotion_effect_truth"],
        },
        "effects": effects,
        "reconciliation": source["reconciliation"],
        "facts_status": source["status"],
        "source_ready": False,
        "anomaly_ready": False,
        "model_ready": False,
        "publication_status": "candidate_only_awaiting_versioned_ai03_handoff",
    }
