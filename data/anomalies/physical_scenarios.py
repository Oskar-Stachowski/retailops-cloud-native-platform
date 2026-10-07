"""Paired physical scenarios: real eligible returns and conserved stock reductions."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import timedelta
from typing import TYPE_CHECKING

from data.anomalies.contract import GRAIN
from data.anomalies.physical_contract import (
    PHYSICAL_GENERATOR,
    PHYSICAL_VERSION,
    PhysicalAnomalyPlan,
    ReturnInjection,
)
from data.anomalies.scenarios import physical_effects
from data.generator.common import deterministic_uuid
from data.generator.configuration import requested_parameters, resolve_generation_config
from data.generator.identity import json_sha256
from data.generator.main import build_dataset
from data.inventory.contract import require
from data.inventory.run_source_dataset import default_inventory_config
from data.inventory.source_bridge import simulate_source_commerce

if TYPE_CHECKING:
    from data.generator.configuration import DatasetGenerationConfig
    from data.inventory.source_contract import SourceInventoryConfig


def return_effects(source: dict, keys: tuple[tuple[str, ...], ...]) -> dict:
    counts: Counter[str] = Counter()
    for row in source["commerce"]["return_events"]:
        if (
            row["returned_at"][:10],
            row["product_id"],
            row["selling_location_id"],
            row["channel"],
        ) in keys:
            counts["events"] += 1
            counts["returned_units"] += int(row["quantity"])
            if row["status"] == "refunded":
                counts["refunded_units"] += int(row["quantity"])
    return {key: counts[key] for key in ("events", "returned_units", "refunded_units")}


def build_physical_scenario(
    generation: DatasetGenerationConfig,
    payload: dict,
    inventory_config: SourceInventoryConfig | None = None,
) -> dict:
    effective = resolve_generation_config(generation)
    require(
        effective.profile.startswith("ai-")
        and effective.days * effective.products * effective.stores <= 5000,
        "Physical candidate is bounded to AI profiles with at most 5000 daily grains.",
    )
    plan = PhysicalAnomalyPlan.from_payload(payload)
    original = build_dataset(generation)
    config = inventory_config or default_inventory_config(generation)
    normal = simulate_source_commerce(original, effective, config)
    source = simulate_source_commerce(original, effective, config, physical_plan=plan)
    require(
        {
            r["demand_id"]: r["latent_quantity"]
            for r in normal["simulation_truth"]["demand_outcomes"]
        }
        == {
            r["demand_id"]: r["latent_quantity"]
            for r in source["simulation_truth"]["demand_outcomes"]
        },
        "Physical anomaly changed latent demand.",
    )
    episodes = []
    for injection in plan.injections:
        keys = injection.daily_keys()
        before, after = physical_effects(normal, keys), physical_effects(source, keys)
        entry = {
            **injection.model_dump(),
            "data_class": "simulation_truth",
            "affected_daily_grains": len(keys),
            "normal_inventory_outcome": before,
            "injected_inventory_outcome": after,
        }
        if isinstance(injection, ReturnInjection):
            a, b = return_effects(normal, keys), return_effects(source, keys)
            require(
                b["returned_units"] > a["returned_units"],
                "Return injection has no actual returned-unit increase.",
            )
            entry.update(normal_returns=a, injected_returns=b)
        else:
            require(
                before["latent_quantity"] == after["latent_quantity"] > 0,
                "Stock cap changed or has no demand.",
            )
            require(
                after["observed_quantity"] < before["observed_quantity"]
                and after["lost_sales_quantity"] > before["lost_sales_quantity"],
                "Stock cap has no actual censoring effect.",
            )
            ids = {
                r["inventory_event_id"]
                for r in source["simulation_truth"]["physical_interventions"]
                if r["injection_id"] == injection.id
            }
            actions = [
                m
                for m in source["inventory"]["ledger"]["movements"]
                if m["inventory_event_id"] in ids
            ]
            require(bool(actions), "Stock episode lacks physical ledger movements.")
            entry.update(
                write_off_event_ids=[m["inventory_event_id"] for m in actions],
                removed_quantity=-sum(m["quantity_delta"] for m in actions),
            )
        episodes.append(entry)
    controls = []
    for control in plan.controls:
        a, b = (
            physical_effects(normal, control.daily_keys()),
            physical_effects(source, control.daily_keys()),
        )
        ar, br = (
            return_effects(normal, control.daily_keys()),
            return_effects(source, control.daily_keys()),
        )
        require(
            control.control_type == "clean", "Physical plan currently supports clean controls only."
        )
        require(a == b and ar == br, "Clean control was affected by physical/return spillover.")
        controls.append(
            {
                **control.model_dump(),
                "normal_inventory_outcome": a,
                "injected_inventory_outcome": b,
                "normal_returns": ar,
                "injected_returns": br,
                "inventory_outcome_unchanged": True,
            }
        )
    # Account for effects at every selling grain, including channels sharing stock
    # and later dates affected by replenishment or restocks. Do not hide spillover.
    daily: dict[tuple[str, ...], list[int]] = defaultdict(lambda: [0, 0])
    for index, run in enumerate((normal, source)):
        for row in run["simulation_truth"]["demand_outcomes"]:
            key = (
                row["occurred_at"][:10],
                row["product_id"],
                row["selling_location_id"],
                row["channel"],
            )
            daily[key][index] += row["observed_quantity"]
    spillover = [
        dict(
            zip(GRAIN, key, strict=True),
            normal_observed_units=values[0],
            injected_observed_units=values[1],
        )
        for key, values in sorted(daily.items())
        if values[0] != values[1]
    ]
    return {
        "scope": "AI 07.1b physical business scenario preparation only",
        "generator_version": PHYSICAL_GENERATOR,
        "generation": effective.parameters(),
        "requested_generation": requested_parameters(generation),
        "plan": plan.model_dump(),
        "inventory_configuration": config.model_dump(),
        "normal_candidate_sha256": json_sha256(original),
        "normal_commerce_sha256": json_sha256(normal["commerce"]),
        "commerce": source["commerce"],
        "inventory": source["inventory"],
        "simulation_truth": {
            "process": source["simulation_truth"],
            "daily_demand_truth": original["daily_demand_truth"],
            "product_simulation_parameters": original["product_simulation_parameters"],
            "store_simulation_parameters": original["store_simulation_parameters"],
            "promotion_effect_truth": original["promotion_effect_truth"],
        },
        "effects": {
            "status": "passed",
            "episodes": episodes,
            "controls": controls,
            "observed_sales_changes": spillover,
        },
        "reconciliation": source["reconciliation"],
        "facts_status": source["status"],
        "source_ready": False,
        "anomaly_ready": False,
        "model_ready": False,
        "publication_status": "candidate_only_awaiting_versioned_ai03_handoff",
    }


def physical_example_plan(
    generation: DatasetGenerationConfig, inventory_config: SourceInventoryConfig | None = None
) -> dict:
    effective = resolve_generation_config(generation)
    require(
        effective.days >= 30 and effective.days * effective.products * effective.stores <= 5000,
        "Physical example needs bounded 30-day history.",
    )
    config = inventory_config or default_inventory_config(generation)
    normal = build_dataset(generation)
    source = simulate_source_commerce(normal, effective, config)
    grouped: dict[tuple[str, ...], set[str]] = defaultdict(set)
    for row in normal["daily_demand_truth"]:
        grouped[tuple(row[k] for k in GRAIN[1:])].add(row["business_date"])
    dates = [(effective.start_date + timedelta(days=i)).isoformat() for i in range(effective.days)]
    eligible = sorted(g for g, days in grouped.items() if all(d in days for d in dates[:30]))
    require(
        len({g[0] for g in eligible}) >= 2,
        "Physical example needs two independently scoped products.",
    )
    # Recipe is selected from source only, before any detector/evaluation exists.
    return_scope = max(
        eligible,
        key=lambda g: (
            sum(
                int(r["quantity"])
                for r in source["inventory"]["sales"]
                if (r["product_id"], r["selling_location_id"], r["channel"]) == g
            ),
            g,
        ),
    )
    outcomes = sorted(
        (
            r
            for r in source["simulation_truth"]["demand_outcomes"]
            if r["product_id"] != return_scope[0]
            and r["observed_quantity"] > 0
            and dates[8] <= r["occurred_at"][:10] <= dates[25]
            and (r["product_id"], r["selling_location_id"], r["channel"]) in eligible
        ),
        key=lambda r: (r["occurred_at"], r["product_id"], r["channel"]),
    )
    require(bool(outcomes), "Physical example needs a positive late fulfilled sale for stock cap.")
    target = outcomes[0]
    stock_scope = target["product_id"], target["selling_location_id"], target["channel"]

    def window(name: str, scope: tuple[str, ...], start: str, end: str) -> dict:
        return {
            "id": deterministic_uuid("physical_anomaly_window", name + ":" + ":".join(scope)),
            **dict(zip(GRAIN[1:], scope, strict=True)),
            "start_date": start,
            "end_date": end,
        }

    common = {"seed": effective.seed, "generator_version": PHYSICAL_GENERATOR}
    return PhysicalAnomalyPlan.from_payload(
        {
            "contract_version": PHYSICAL_VERSION,
            "data_class": "simulation_truth",
            "generator_version": PHYSICAL_GENERATOR,
            "seed": effective.seed,
            "business_timezone": "UTC",
            "boundary_policy": "inclusive_business_dates",
            "overlap_policy": "reject_shared_stock_and_return_spillover",
            "injections": [
                {
                    **window("return_spike", return_scope, dates[12], dates[18]),
                    **common,
                    "injection_type": "return_spike",
                    "shape": "return_probability_multiplier",
                    "magnitude": "20",
                    "affected_fields": ["return_selection_probability"],
                },
                {
                    **window(
                        "inventory_censored_episode",
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
            ],
            "controls": [
                {**window("clean", scope, dates[0], dates[6]), "control_type": "clean"}
                for scope in (return_scope, stock_scope)
            ],
        }
    ).model_dump()
