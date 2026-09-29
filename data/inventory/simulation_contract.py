from __future__ import annotations

from datetime import date
from typing import Annotated, Any, Literal

from pydantic import Field, ValidationError

# Pydantic resolves these annotations while generating the schema.
from data.inventory.contract import (
    Identifier,
    MovementRecord,
    Reference,
    Timestamp,
    Unit,
    require,
    utc_timestamp,
)
from data.inventory.replenishment_contract import Date, Money, Positive, SupplyRecord

SIMULATION_VERSION = "chronological-shared-stock-1.0.0"
Channel = Literal["store", "online", "marketplace", "wholesale"]


class SellingLocation(SupplyRecord):
    id: Identifier
    location_code: Reference


class FulfillmentRoute(SupplyRecord):
    id: Identifier
    version: Positive
    selling_location_id: Identifier
    channel: Channel
    stock_location_id: Identifier
    effective_from: Date
    effective_to: Date
    available_at: Timestamp


class DemandArrival(SupplyRecord):
    demand_id: Identifier
    product_id: Identifier
    selling_location_id: Identifier
    channel: Channel
    latent_quantity: Annotated[int, Field(ge=0)]
    unit_price: Money
    currency: Literal["PLN", "EUR"]
    occurred_at: Timestamp
    sequence: Annotated[int, Field(ge=0)]
    source_reference: Reference


class ReturnEvent(SupplyRecord):
    return_id: Identifier
    demand_id: Identifier
    product_id: Identifier
    stock_location_id: Identifier
    unit_of_measure: Unit
    returned_quantity: Positive
    quality_status: Literal["accepted", "rejected"]
    returned_at: Timestamp
    ingested_at: Timestamp
    available_at: Timestamp
    sequence: Annotated[int, Field(ge=0)]
    source_reference: Reference


class SimulationSettings(SupplyRecord):
    process_version: Literal["chronological-shared-stock-1.0.0"]
    business_timezone: Literal["UTC"]
    start_at: Timestamp
    end_at: Timestamp
    event_order: Literal["occurred_at_sequence_then_review"]
    reservation_policy: Literal["none"]
    fulfillment_policy: Literal["instant_partial_fulfillment"]
    sale_ingestion_delay_seconds: Annotated[int, Field(ge=0)]
    sale_availability_delay_seconds: Annotated[int, Field(ge=0)]


class ChronologicalScenario(SupplyRecord):
    contract_version: Literal["chronological-scenario-1.0.0"]
    settings: SimulationSettings
    selling_locations: Annotated[list[SellingLocation], Field(min_length=1)]
    fulfillment_routes: list[FulfillmentRoute]
    demand_class: Literal["simulation_truth"]
    demand_arrivals: list[DemandArrival]
    return_events: list[ReturnEvent]
    inventory_actions: list[MovementRecord]

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> ChronologicalScenario:
        try:
            parsed = cls.model_validate(payload)
        except ValidationError as error:
            msg = "Invalid chronological scenario contract."
            raise ValueError(msg) from error
        start, end = utc_timestamp(parsed.settings.start_at), utc_timestamp(parsed.settings.end_at)
        require(start < end, "Simulation window must be nonempty and half-open.")
        for rows, primary_key in (
            (parsed.selling_locations, "id"),
            (parsed.fulfillment_routes, "id"),
            (parsed.demand_arrivals, "demand_id"),
            (parsed.return_events, "return_id"),
            (parsed.inventory_actions, "inventory_event_id"),
        ):
            require(
                len({getattr(r, primary_key) for r in rows}) == len(rows),
                "Duplicate scenario primary key: " + primary_key,
            )
        require(
            len({s.location_code for s in parsed.selling_locations})
            == len(parsed.selling_locations),
            "Duplicate selling location code.",
        )
        selling = {s.id for s in parsed.selling_locations}
        for route in parsed.fulfillment_routes:
            require(
                route.selling_location_id in selling, "Route references unknown selling location."
            )
            require(
                date.fromisoformat(route.effective_from) < date.fromisoformat(route.effective_to),
                "Invalid route effective period.",
            )
            utc_timestamp(route.available_at)
        keys = []
        for rows, time_field in (
            (parsed.demand_arrivals, "occurred_at"),
            (parsed.return_events, "returned_at"),
            (parsed.inventory_actions, "occurred_at"),
        ):
            for row in rows:
                happened = utc_timestamp(getattr(row, time_field))
                require(
                    start <= happened < end, "Scenario physical event is outside simulation window."
                )
                keys.append((happened, row.sequence))
        require(len(set(keys)) == len(keys), "Duplicate scenario timestamp/sequence.")
        for event in parsed.return_events:
            require(
                utc_timestamp(event.returned_at)
                <= utc_timestamp(event.ingested_at)
                <= utc_timestamp(event.available_at),
                "Invalid return chronology.",
            )
        return parsed


def scenario_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        **ChronologicalScenario.model_json_schema(),
    }


def fulfillment_routes_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "array",
        "items": FulfillmentRoute.model_json_schema(),
    }


class ExecutedSale(SupplyRecord):
    sale_id: Identifier
    order_id: Identifier
    product_id: Identifier
    selling_location_id: Identifier
    channel: Channel
    stock_location_id: Identifier
    fulfillment_route_id: Identifier
    quantity: Positive
    unit_of_measure: Unit
    unit_price: Money
    currency: Literal["PLN", "EUR"]
    gross_revenue: Money
    ordered_at: Timestamp
    sold_at: Timestamp
    ingested_at: Timestamp
    available_at: Timestamp
    sequence: Annotated[int, Field(ge=0)]
    source_reference: Identifier


class ProcessedReturn(SupplyRecord):
    return_id: Identifier
    sale_id: Identifier
    product_id: Identifier
    stock_location_id: Identifier
    unit_of_measure: Unit
    quantity: Positive
    quality_status: Literal["accepted", "rejected"]
    refund_amount: Money
    currency: Literal["PLN", "EUR"]
    returned_at: Timestamp
    ingested_at: Timestamp
    available_at: Timestamp
    sequence: Annotated[int, Field(ge=0)]
    source_reference: Reference


class CommerceOutput(SupplyRecord):
    sales: list[ExecutedSale]
    returns: list[ProcessedReturn]


def commerce_output_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        **CommerceOutput.model_json_schema(),
    }
