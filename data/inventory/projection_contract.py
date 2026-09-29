from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import Field, ValidationError

from data.inventory.contract import Identifier, Timestamp, Unit, require, utc_timestamp
from data.inventory.replenishment_contract import Date, SupplyRecord

PROJECTION_VERSION = "inventory-projection-1.0.0"
Count = Annotated[int, Field(ge=0)]


class ProjectionConfig(SupplyRecord):
    contract_version: Literal["inventory-projection-config-1.0.0"]
    process_version: Literal["inventory-projection-1.0.0"]
    business_timezone: Literal["UTC"]
    start_at: Timestamp
    end_at: Timestamp
    snapshot_policy: Literal["utc_day_last_microsecond"]
    reservation_policy: Literal["none"]
    stock_measure: Literal["available_qty"]
    episode_policy: Literal["zero_after_event_including_instantaneous"]
    diagnostic_horizon_days: Literal[7]
    truth_delay_seconds: Count

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> ProjectionConfig:
        try:
            parsed = cls.model_validate(payload)
        except ValidationError as error:
            msg = "Invalid inventory projection configuration."
            raise ValueError(msg) from error
        require(
            utc_timestamp(parsed.start_at) < utc_timestamp(parsed.end_at),
            "Invalid projection window.",
        )
        return parsed.model_copy(
            update={
                "start_at": utc_timestamp(parsed.start_at).isoformat(),
                "end_at": utc_timestamp(parsed.end_at).isoformat(),
            }
        )


class InventorySnapshot(SupplyRecord):
    snapshot_id: Identifier
    product_id: Identifier
    stock_location_id: Identifier
    business_date: Date
    period_from_at: Timestamp
    period_to_at: Timestamp
    is_full_business_day: bool
    snapshot_at: Timestamp
    as_of_time: Timestamp
    unit_of_measure: Unit
    on_hand: Count | None
    reserved_qty: Count | None
    available_qty: Count | None
    status: Literal["known", "not_available"]
    source_available_at: Timestamp | None
    last_inventory_event_id: Identifier | None
    movement_count: Count


class PhysicalDailyBalance(SupplyRecord):
    product_id: Identifier
    stock_location_id: Identifier
    business_date: Date
    snapshot_at: Timestamp
    balance_before_period: Count
    opening_quantity: Count
    movement_delta: int
    closing_quantity: Count
    reserved_qty: Count
    available_qty: Count


class StockoutEpisode(SupplyRecord):
    episode_id: Identifier
    product_id: Identifier
    stock_location_id: Identifier
    unit_of_measure: Unit
    start_at: Timestamp
    start_sequence: Count
    start_event_id: Identifier
    start_available_at: Timestamp
    onset_kind: Literal["opening_zero", "depleted_by_movement"]
    end_at: Timestamp | None
    end_sequence: Count | None
    end_event_id: Identifier | None
    end_available_at: Timestamp | None
    observed_through_exclusive_at: Timestamp
    duration_microseconds: Count
    left_censored: bool
    right_censored: bool
    diagnostic_available_at: Timestamp
    lost_sales_quantity: Count
    affected_demand_count: Count


class LostSalesImpact(SupplyRecord):
    episode_id: Identifier
    demand_id: Identifier
    product_id: Identifier
    stock_location_id: Identifier
    selling_location_id: Identifier
    channel: Literal["store", "online", "marketplace", "wholesale"]
    occurred_at: Timestamp
    sequence: Count
    lost_sales_quantity: Annotated[int, Field(gt=0)]


class WindowDiagnostic(SupplyRecord):
    product_id: Identifier
    stock_location_id: Identifier
    origin: Timestamp
    window_end_at: Timestamp
    evaluated_at: Timestamp
    status: Literal["evaluable", "already_stockout", "not_evaluable"]
    reason: (
        Literal[
            "inventory_unknown",
            "origin_state_unavailable",
            "incomplete_window",
            "outcomes_not_available",
        ]
        | None
    )
    incident_stockout: Annotated[int, Field(ge=0, le=1)] | None
    label_available_at: Timestamp | None


class ProjectionTruth(SupplyRecord):
    data_class: Literal["simulation_truth"]
    physical_daily_balances: list[PhysicalDailyBalance]
    stockout_episodes: list[StockoutEpisode]
    lost_sales_impacts: list[LostSalesImpact]
    window_diagnostics: list[WindowDiagnostic]


class ProjectionOutput(SupplyRecord):
    contract_version: Literal["inventory-projection-1.0.0"]
    configuration: ProjectionConfig
    operational: list[InventorySnapshot]
    simulation_truth: ProjectionTruth


def projection_config_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        **ProjectionConfig.model_json_schema(),
    }


def projection_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        **ProjectionOutput.model_json_schema(),
    }
