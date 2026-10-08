"""Execute stock caps as ledger write-offs before actual shared-stock sales."""

from __future__ import annotations

from copy import deepcopy
from datetime import date
from typing import TYPE_CHECKING

from data.anomalies.physical_contract import InventoryInjection, PhysicalAnomalyPlan
from data.generator.common import deterministic_uuid
from data.generator.demand_grid import demand_grid
from data.inventory.contract import require, utc_timestamp
from data.inventory.fulfillment_routes import resolve_route
from data.inventory.simulation_contract import DemandArrival, FulfillmentRoute
from data.inventory.source_commerce import SourceCommerceSimulator

if TYPE_CHECKING:
    from data.generator.configuration import ResolvedGenerationConfig
    from data.inventory.source_contract import SourceInventoryConfig


class PhysicalAnomalySimulator(SourceCommerceSimulator):
    def __init__(
        self,
        inputs: dict,
        tables: dict,
        generation: ResolvedGenerationConfig,
        config: SourceInventoryConfig,
        plan: PhysicalAnomalyPlan,
    ) -> None:
        self.plan = PhysicalAnomalyPlan.from_payload(plan.model_dump())
        require(generation.profile.startswith("ai-"), "Physical scenarios require an AI profile.")
        require(plan.seed == generation.seed, "Physical scenario seed differs from source.")
        grid, _ = demand_grid(tables, generation)
        routes = tuple(
            FulfillmentRoute.model_validate(r) for r in inputs["scenario"]["fulfillment_routes"]
        )
        physical: set[tuple[str, str, str]] = set()
        for window in [*plan.injections, *plan.controls]:
            keys = window.daily_keys()
            require(
                all(k in grid and grid[k]["location_open"] == "true" for k in keys),
                "Physical window must contain active, open, in-range source grains.",
            )
            if isinstance(window, InventoryInjection):
                for key in keys:
                    route = resolve_route(routes, key[2], key[3], key[0] + "T00:00:00+00:00")
                    require(
                        route.stock_location_id == window.stock_location_id,
                        "Stock cap does not match historical physical route.",
                    )
                    position = key[0], key[1], window.stock_location_id
                    require(position not in physical, "Overlapping physical stock caps.")
                    physical.add(position)
        updated = deepcopy(inputs)
        # Reserve an immediately preceding sequence for each intervention. This
        # keeps write-off/sale ordering unambiguous even with simultaneous baskets.
        for row in updated["scenario"]["demand_arrivals"]:
            row["sequence"] = 2 * row["sequence"] + 1
        super().__init__(updated, tables, generation, config, return_factors=plan.return_factors())
        self.applied_caps: list[dict] = []

    def _demand(self, demand: DemandArrival) -> None:
        route = resolve_route(
            self.routes, demand.selling_location_id, demand.channel, demand.occurred_at
        )
        day = utc_timestamp(demand.occurred_at).date()
        for injection in self.plan.injections:
            if (
                isinstance(injection, InventoryInjection)
                and injection.product_id == demand.product_id
                and injection.stock_location_id == route.stock_location_id
                and date.fromisoformat(injection.start_date)
                <= day
                <= date.fromisoformat(injection.end_date)
            ):
                position = demand.product_id, route.stock_location_id
                removed = max(0, self.balances[position] - injection.magnitude)
                if removed:
                    event_id = deterministic_uuid(
                        "anomaly_stock_cap", injection.id + ":" + demand.demand_id
                    )
                    record = self._movement(
                        event_id,
                        position,
                        "write_off",
                        -removed,
                        demand.occurred_at,
                        demand.occurred_at,
                        demand.occurred_at,
                        demand.sequence - 1,
                        event_id,
                    )
                    record["source_process"] = "write_off"
                    movement = self._apply(record)
                    self.applied_caps.append(
                        {
                            "injection_id": injection.id,
                            "inventory_event_id": event_id,
                            "removed_quantity": removed,
                            "available_at": movement.available_at,
                        }
                    )
        super()._demand(demand)
