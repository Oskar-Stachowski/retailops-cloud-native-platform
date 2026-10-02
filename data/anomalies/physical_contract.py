"""Private, separately versioned return and physical stock interventions."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import Field, ValidationError

from data.anomalies.contract import ControlWindow, Magnitude, Window
from data.inventory.contract import Identifier, require
from data.inventory.replenishment_contract import SupplyRecord

PHYSICAL_VERSION = "business-physical-anomaly-plan-1.0.0"
PHYSICAL_GENERATOR = "business-physical-anomaly-generator-1.0.0"


class ReturnInjection(Window):
    injection_type: Literal["return_spike"]
    shape: Literal["return_probability_multiplier"]
    magnitude: Magnitude
    affected_fields: list[Literal["return_selection_probability"]]
    seed: int
    generator_version: Literal["business-physical-anomaly-generator-1.0.0"]


class InventoryInjection(Window):
    injection_type: Literal["inventory_censored_episode"]
    stock_location_id: Identifier
    shape: Literal["available_stock_cap"]
    magnitude: Annotated[int, Field(strict=True, ge=0, le=1000000)]
    affected_fields: list[Literal["available_qty", "observed_sales_units"]]
    seed: int
    generator_version: Literal["business-physical-anomaly-generator-1.0.0"]


Injection = Annotated[ReturnInjection | InventoryInjection, Field(discriminator="injection_type")]


class PhysicalAnomalyPlan(SupplyRecord):
    contract_version: Literal["business-physical-anomaly-plan-1.0.0"]
    data_class: Literal["simulation_truth"]
    generator_version: Literal["business-physical-anomaly-generator-1.0.0"]
    seed: int
    business_timezone: Literal["UTC"]
    boundary_policy: Literal["inclusive_business_dates"]
    overlap_policy: Literal["reject_shared_stock_and_return_spillover"]
    injections: Annotated[list[Injection], Field(min_length=1, max_length=100)]
    controls: Annotated[list[ControlWindow], Field(min_length=1, max_length=100)]

    @classmethod
    def from_payload(cls, payload: dict) -> PhysicalAnomalyPlan:
        try:
            plan = cls.model_validate(payload)
        except ValidationError as error:
            msg = "Invalid physical anomaly plan contract."
            raise ValueError(msg) from error
        windows = [*plan.injections, *plan.controls]
        require(len({w.id for w in windows}) == len(windows), "Duplicate anomaly/control ID.")
        occupied: set[tuple[str, ...]] = set()
        for window in windows:
            if isinstance(window, ControlWindow):
                require(
                    window.control_type == "clean", "Physical plan supports clean controls only."
                )
            keys = set(window.daily_keys())
            require(not occupied.intersection(keys), "Overlapping injection/control windows.")
            occupied.update(keys)
        for injection in plan.injections:
            require(injection.seed == plan.seed, "Injection seed differs from plan seed.")
            if isinstance(injection, ReturnInjection):
                require(1 < Decimal(injection.magnitude) <= 20, "Invalid return multiplier.")
                require(
                    injection.affected_fields == ["return_selection_probability"],
                    "Return injection must change selection of purchased units.",
                )
            else:
                require(
                    injection.affected_fields == ["available_qty", "observed_sales_units"],
                    "Inventory injection must change physical fulfillment.",
                )
            require(
                any(
                    c.control_type == "clean"
                    and (c.product_id, c.selling_location_id, c.channel)
                    == (injection.product_id, injection.selling_location_id, injection.channel)
                    and len(c.daily_keys()) >= len(injection.daily_keys())
                    and c.end_date < injection.start_date
                    for c in plan.controls
                ),
                "Physical injection needs a preceding clean control of sufficient duration.",
            )
        # Return restocks and physical caps can affect other channels of the same SKU.
        # Do not claim these interventions are independent at the selling grain.
        require(
            len({i.product_id for i in plan.injections}) == len(plan.injections),
            "Physical interventions on one product can have shared-stock spillover.",
        )
        return plan.model_copy(
            update={
                "injections": sorted(plan.injections, key=lambda w: w.id),
                "controls": sorted(plan.controls, key=lambda w: w.id),
            }
        )

    def return_factors(self) -> dict[tuple[str, ...], str]:
        return {
            key: injection.magnitude
            for injection in self.injections
            if isinstance(injection, ReturnInjection)
            for key in injection.daily_keys()
        }


def physical_plan_schema() -> dict:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        **PhysicalAnomalyPlan.model_json_schema(),
    }
