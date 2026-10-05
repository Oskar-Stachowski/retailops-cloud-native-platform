"""Declared bounded portfolio profile and recipes, selected before detector results."""

from collections import defaultdict
from datetime import timedelta

from data.anomalies.contract import GENERATOR_VERSION, GRAIN, AnomalyPlan
from data.anomalies.physical_contract import PHYSICAL_GENERATOR, PhysicalAnomalyPlan
from data.generator.common import deterministic_uuid
from data.generator.configuration import DatasetGenerationConfig, resolve_generation_config
from data.generator.main import build_dataset
from data.inventory.contract import require
from data.inventory.run_source_dataset import default_inventory_config
from data.inventory.source_bridge import simulate_source_commerce

PROFILE = "ai-07-portfolio-v1"
SUPPLY_ADEQUATE_PROFILE = "ai-07-portfolio-v2"
CONFIRMATORY_PROFILE = "ai-07-portfolio-v3"
SEEDS = (42, 137, 2026)
SPLITS = {"training": (28, 59), "validation": (64, 95), "final_test": (100, 127)}


def portfolio_plan(generation: DatasetGenerationConfig, family: str) -> dict:
    effective = resolve_generation_config(generation)
    require(
        effective.profile in (PROFILE, SUPPLY_ADEQUATE_PROFILE, CONFIRMATORY_PROFILE)
        and (effective.days, effective.products, effective.stores, effective.warehouses)
        == (
            128,
            12 if effective.profile == CONFIRMATORY_PROFILE else 8,
            3 if effective.profile == PROFILE else 2,
            2,
        ),
        "Portfolio profile dimensions are frozen.",
    )
    require(effective.seed in SEEDS, "Portfolio source seed is not frozen.")
    require(family in {"demand", "physical"}, "Unknown portfolio scenario family.")
    normal = build_dataset(generation)
    grouped = defaultdict(dict)
    for row in normal["daily_demand_truth"]:
        grouped[tuple(row[k] for k in GRAIN[1:])][row["business_date"]] = row
    days = [(effective.start_date + timedelta(days=i)).isoformat() for i in range(effective.days)]
    eligible = [scope for scope, rows in grouped.items() if all(day in rows for day in days[28:])]
    eligible.sort(
        key=lambda scope: (-sum(int(r["latent_units"]) for r in grouped[scope].values()), scope)
    )
    require(bool(eligible), "Portfolio has no continuous source series.")

    def window(name: str, scope: tuple, start: int, end: int) -> dict:
        return {
            "id": deterministic_uuid("ai07_portfolio", f"{effective.seed}:{family}:{name}:{scope}"),
            **dict(zip(GRAIN[1:], scope, strict=True)),
            "start_date": days[start],
            "end_date": days[end],
        }

    if family == "demand":
        injections = []
        controls = []
        for index, scope in enumerate(eligible[:3]):
            controls.append({**window(f"clean-{index}", scope, 35, 41), "control_type": "clean"})
            for split, base in (("validation", 68), ("final_test", 100)):
                for kind, offset, length, magnitude in (
                    ("one_day_spike", 0, 1, "4"),
                    ("multi_day_spike", 7, 3, "3"),
                    ("sustained_drop", 17, 5, "0.1"),
                ):
                    start = base + offset
                    injections.append(
                        {
                            **window(f"{split}-{kind}-{index}", scope, start, start + length - 1),
                            "injection_type": kind,
                            "shape": "constant_multiplier",
                            "magnitude": magnitude,
                            "affected_fields": ["expected_rate", "latent_units"],
                            "seed": effective.seed,
                            "generator_version": GENERATOR_VERSION,
                        }
                    )
        # Neutral controls come from the existing calendar process; their choice
        # never consults a detector. The first day is an explicit cold start.
        first = min(normal["daily_demand_truth"], key=lambda r: tuple(r[k] for k in GRAIN))
        controls.append(
            {
                **window("cold-start", tuple(first[k] for k in GRAIN[1:]), 0, 0),
                "control_type": "insufficient_history",
            }
        )
        occupied = {
            key
            for w in [*injections, *controls]
            for key in tuple(
                (day, w["product_id"], w["selling_location_id"], w["channel"])
                for day in days
                if w["start_date"] <= day <= w["end_date"]
            )
        }
        for kind, fields in (
            ("promotion", ("promotion_factor",)),
            ("seasonality", ("weekly_factor", "seasonal_factor")),
        ):
            row = next(
                (
                    r
                    for r in normal["daily_demand_truth"]
                    if days[28] <= r["business_date"] <= days[63]
                    and tuple(r[k] for k in GRAIN) not in occupied
                    and any(float(r[f]) != 1 for f in fields)
                ),
                None,
            )
            require(row is not None, "Portfolio needs a neutral calendar/promotion control.")
            start = days.index(row["business_date"])
            controls.append(
                {
                    **window(kind, tuple(row[k] for k in GRAIN[1:]), start, start),
                    "control_type": kind,
                }
            )
            occupied.add(tuple(row[k] for k in GRAIN))
        return AnomalyPlan.from_payload(
            {
                "contract_version": "business-anomaly-plan-1.0.0",
                "data_class": "simulation_truth",
                "generator_version": GENERATOR_VERSION,
                "seed": effective.seed,
                "business_timezone": "UTC",
                "boundary_policy": "inclusive_business_dates",
                "overlap_policy": "reject",
                "minimum_history_observations": 7,
                "injections": injections,
                "controls": controls,
            }
        ).model_dump()

    source = simulate_source_commerce(normal, effective, default_inventory_config(generation))
    products = []
    chosen = []
    for scope in eligible:
        if scope[0] not in products:
            chosen.append(scope)
            products.append(scope[0])
    require(len(chosen) >= 4, "Physical portfolio needs four independent products.")
    injections = []
    controls = []
    for index, scope in enumerate(chosen[:4]):
        split = "validation" if index < 2 else "final_test"
        base = 68 if split == "validation" else 100
        kind = "return_spike" if index % 2 == 0 else "inventory_censored_episode"
        controls.append({**window(f"clean-{index}", scope, 35, 44), "control_type": "clean"})
        fields = {
            "seed": effective.seed,
            "generator_version": PHYSICAL_GENERATOR,
            "injection_type": kind,
        }
        if kind == "return_spike":
            injections.append(
                {
                    **window(f"{split}-{kind}", scope, base, base + 9),
                    **fields,
                    "shape": "return_probability_multiplier",
                    "magnitude": "20",
                    "affected_fields": ["return_selection_probability"],
                }
            )
        else:
            target = next(
                (
                    r
                    for r in sorted(
                        source["simulation_truth"]["demand_outcomes"],
                        key=lambda r: r["occurred_at"],
                    )
                    if (r["product_id"], r["selling_location_id"], r["channel"]) == scope
                    and r["observed_quantity"] > 0
                    and days[base] <= r["occurred_at"][:10] <= days[base + 9]
                ),
                None,
            )
            require(target is not None, "Physical portfolio needs a fulfilled sale to censor.")
            start = days.index(target["occurred_at"][:10])
            injections.append(
                {
                    **window(f"{split}-{kind}", scope, start, start + 2),
                    **fields,
                    "stock_location_id": target["stock_location_id"],
                    "shape": "available_stock_cap",
                    "magnitude": 0,
                    "affected_fields": ["available_qty", "observed_sales_units"],
                }
            )
    return PhysicalAnomalyPlan.from_payload(
        {
            "contract_version": "business-physical-anomaly-plan-1.0.0",
            "data_class": "simulation_truth",
            "generator_version": PHYSICAL_GENERATOR,
            "seed": effective.seed,
            "business_timezone": "UTC",
            "boundary_policy": "inclusive_business_dates",
            "overlap_policy": "reject_shared_stock_and_return_spillover",
            "injections": injections,
            "controls": controls,
        }
    ).model_dump()
