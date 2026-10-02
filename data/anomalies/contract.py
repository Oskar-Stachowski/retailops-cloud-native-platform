"""Versioned demand injections, with explicit scopes and rejected overlaps."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Annotated, Literal

from pydantic import Field, ValidationError

from data.generator.demand_grid import demand_grid
from data.inventory.contract import Identifier, require
from data.inventory.replenishment_contract import Date, SupplyRecord
from data.inventory.simulation_contract import Channel  # noqa: TC001 - Pydantic schema

if TYPE_CHECKING:
    from data.generator.configuration import ResolvedGenerationConfig

CONTRACT_VERSION = "business-anomaly-plan-1.0.0"
GENERATOR_VERSION = "business-anomaly-generator-1.0.0"
GRAIN = ("business_date", "product_id", "selling_location_id", "channel")
Magnitude = Annotated[str, Field(pattern=r"^(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$")]


class Window(SupplyRecord):
    id: Identifier
    product_id: Identifier
    selling_location_id: Identifier
    channel: Channel
    start_date: Date
    end_date: Date

    def daily_keys(self) -> tuple[tuple[str, ...], ...]:
        start, end = date.fromisoformat(self.start_date), date.fromisoformat(self.end_date)
        require(start <= end, "Anomaly window has reversed dates.")
        # Bound expansion before allocating rows, including untrusted input.
        require((end - start).days < 730, "Anomaly window exceeds 730 days.")
        return tuple(
            (
                (start + timedelta(days=offset)).isoformat(),
                self.product_id,
                self.selling_location_id,
                self.channel,
            )
            for offset in range((end - start).days + 1)
        )


class DemandInjection(Window):
    injection_type: Literal["one_day_spike", "multi_day_spike", "sustained_drop"]
    shape: Literal["constant_multiplier"]
    magnitude: Magnitude
    affected_fields: list[Literal["expected_rate", "latent_units"]]
    seed: int
    generator_version: Literal["business-anomaly-generator-1.0.0"]


class ControlWindow(Window):
    control_type: Literal["clean", "promotion", "seasonality", "insufficient_history"]


class AnomalyPlan(SupplyRecord):
    contract_version: Literal["business-anomaly-plan-1.0.0"]
    data_class: Literal["simulation_truth"]
    generator_version: Literal["business-anomaly-generator-1.0.0"]
    seed: int
    business_timezone: Literal["UTC"]
    boundary_policy: Literal["inclusive_business_dates"]
    overlap_policy: Literal["reject"]
    minimum_history_observations: Annotated[int, Field(ge=1, le=365)]
    injections: Annotated[list[DemandInjection], Field(min_length=1, max_length=100)]
    controls: Annotated[list[ControlWindow], Field(min_length=1, max_length=100)]

    @classmethod
    def from_payload(cls, payload: dict) -> AnomalyPlan:
        try:
            plan = cls.model_validate(payload)
        except ValidationError as error:
            msg = "Invalid business anomaly plan contract."
            raise ValueError(msg) from error
        windows = [*plan.injections, *plan.controls]
        require(len({w.id for w in windows}) == len(windows), "Duplicate anomaly/control ID.")
        occupied: set[tuple[str, ...]] = set()
        for window in windows:
            keys = set(window.daily_keys())
            require(not occupied.intersection(keys), "Overlapping injection/control windows.")
            occupied.update(keys)
        for injection in plan.injections:
            days, magnitude = len(injection.daily_keys()), Decimal(injection.magnitude)
            require(injection.seed == plan.seed, "Injection seed differs from plan seed.")
            require(
                injection.affected_fields == ["expected_rate", "latent_units"],
                "Demand injection must change the process before sampling/baskets.",
            )
            if injection.injection_type == "one_day_spike":
                require(days == 1, "One-day spike must last exactly one day.")
            elif injection.injection_type == "multi_day_spike":
                require(days >= 2, "Multi-day spike needs at least two days.")
            else:
                require(days >= 3, "Sustained drop needs at least three days.")
            require(
                0 <= magnitude < 1
                if injection.injection_type == "sustained_drop"
                else 1 < magnitude <= 20,
                "Invalid magnitude for demand injection type.",
            )
            require(
                any(
                    c.control_type == "clean"
                    and (c.product_id, c.selling_location_id, c.channel)
                    == (injection.product_id, injection.selling_location_id, injection.channel)
                    and len(c.daily_keys()) >= days
                    for c in plan.controls
                ),
                "Each injection needs a clean control of the same grain and sufficient duration.",
            )
        return plan.model_copy(
            update={
                "injections": sorted(plan.injections, key=lambda w: w.id),
                "controls": sorted(plan.controls, key=lambda w: w.id),
            }
        )

    def factors(self, tables: dict, config: ResolvedGenerationConfig) -> dict[tuple[str, ...], str]:
        self.from_payload(self.model_dump())
        require(config.profile.startswith("ai-"), "Anomaly scenarios require an AI profile.")
        require(self.seed == config.seed, "Anomaly plan seed differs from generator seed.")
        grid, _ = demand_grid(tables, config)
        for window in [*self.injections, *self.controls]:
            require(
                all(
                    key in grid and grid[key]["location_open"] == "true"
                    for key in window.daily_keys()
                ),
                "Anomaly/control window must contain only active, open, in-range source grains.",
            )
        return {
            key: injection.magnitude
            for injection in self.injections
            for key in injection.daily_keys()
        }


def plan_schema() -> dict:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        **AnomalyPlan.model_json_schema(),
    }
