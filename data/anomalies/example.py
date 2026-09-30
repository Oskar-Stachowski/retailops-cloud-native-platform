"""Deterministically select example windows from source grain, before any detector exists."""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

from data.anomalies.contract import CONTRACT_VERSION, GENERATOR_VERSION, GRAIN, AnomalyPlan
from data.generator.common import deterministic_uuid
from data.generator.configuration import resolve_generation_config
from data.generator.main import build_dataset
from data.inventory.contract import require

if TYPE_CHECKING:
    from data.generator.configuration import DatasetGenerationConfig


def example_plan(generation: DatasetGenerationConfig) -> dict:
    effective = resolve_generation_config(generation)
    require(effective.days >= 30, "The example recipe needs at least 30 source days.")
    require(
        effective.days * effective.products * effective.stores <= 5000,
        "Example exceeds candidate budget.",
    )
    normal = build_dataset(generation)
    rows = normal["daily_demand_truth"]
    grouped: dict[tuple[str, ...], dict[str, dict[str, str]]] = defaultdict(dict)
    for row in rows:
        grouped[tuple(row[f] for f in GRAIN[1:])][row["business_date"]] = row
    dates = [(effective.start_date + timedelta(days=i)).isoformat() for i in range(30)]
    eligible = [grain for grain, days in grouped.items() if all(d in days for d in dates)]
    require(bool(eligible), "Example needs an active, open series across its 30-day recipe.")
    scope = min(
        eligible,
        key=lambda grain: (-sum(int(r["latent_units"]) for r in grouped[grain].values()), grain),
    )

    def window(name: str, grain: tuple, start: str, end: str) -> dict:
        return {
            "id": deterministic_uuid("anomaly_window", name + ":" + ":".join(grain)),
            **dict(zip(GRAIN[1:], grain, strict=True)),
            "start_date": start,
            "end_date": end,
        }

    injections = [
        {
            **window(kind, scope, dates[start], dates[end]),
            "injection_type": kind,
            "shape": "constant_multiplier",
            "magnitude": magnitude,
            "affected_fields": ["expected_rate", "latent_units"],
            "seed": effective.seed,
            "generator_version": GENERATOR_VERSION,
        }
        for kind, start, end, magnitude in (
            ("one_day_spike", 8, 8, "3"),
            ("multi_day_spike", 15, 17, "2"),
            ("sustained_drop", 22, 25, "0.2"),
        )
    ]
    controls = [
        {**window("clean", scope, dates[3], dates[6]), "control_type": "clean"},
        {
            **window("insufficient_history", scope, dates[0], dates[0]),
            "control_type": "insufficient_history",
        },
    ]
    occupied = {
        (key, scope)
        for i in injections
        for key in [d for d in dates if i["start_date"] <= d <= i["end_date"]]
    }
    occupied.update((d, scope) for d in dates if dates[3] <= d <= dates[6] or d == dates[0])
    for kind, fields in (
        ("promotion", ("promotion_factor",)),
        ("seasonality", ("weekly_factor", "seasonal_factor")),
    ):
        matches = sorted(
            (
                r
                for r in rows
                if (r["business_date"], tuple(r[f] for f in GRAIN[1:])) not in occupied
                and any(Decimal(r[f]) != 1 for f in fields)
            ),
            key=lambda r: tuple(r[f] for f in GRAIN),
        )
        require(bool(matches), "Example needs a real " + kind + " control.")
        row = matches[0]
        grain = tuple(row[f] for f in GRAIN[1:])
        controls.append(
            {
                **window(kind, grain, row["business_date"], row["business_date"]),
                "control_type": kind,
            }
        )
        occupied.add((row["business_date"], grain))
    return AnomalyPlan.from_payload(
        {
            "contract_version": CONTRACT_VERSION,
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
