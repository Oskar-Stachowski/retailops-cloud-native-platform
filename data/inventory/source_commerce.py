"""Fulfill source baskets and schedule refunds against actual purchased lines."""

from __future__ import annotations

import heapq
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

from data.generator.commerce_pricing import CommercePricing
from data.generator.common import money
from data.generator.dimensions import DimensionIndex
from data.generator.return_events import generate_return_events
from data.generator.simulation import simulation_entities
from data.inventory.contract import utc_timestamp
from data.inventory.simulation_contract import ReturnEvent
from data.inventory.simulator import ChronologicalSimulator

if TYPE_CHECKING:
    from data.generator.configuration import ResolvedGenerationConfig
    from data.inventory.simulation_contract import DemandArrival
    from data.inventory.source_contract import SourceInventoryConfig

RESTOCKABLE_REASONS = frozenset({"wrong_size", "changed_mind"})


class SourceCommerceSimulator(ChronologicalSimulator):
    def __init__(
        self,
        inputs: dict,
        tables: dict,
        generation: ResolvedGenerationConfig,
        config: SourceInventoryConfig,
    ) -> None:
        super().__init__(
            inputs["inventory"],
            inputs["supply"],
            inputs["scenario"],
            inputs["policy"],
            inputs["fulfillment"],
            inputs["truth"],
        )
        self.generation = generation
        self.config = config
        self.tables = tables
        self.requested_sales = {r["id"]: r for r in tables["sales"]}
        self.requested_refs = {r["sale_id"]: r for r in tables["sale_price_references"]}
        self.requested_items = {r["id"]: r for r in tables["order_items"]}
        self.requested_orders = {r["id"]: r for r in tables["orders"]}
        self.stores = {r["id"]: r for r in tables["stores"]}
        self.tables["sale_price_references"] = []
        self.pricing = CommercePricing(tables, DimensionIndex(tables))
        self.actual_sales: list[dict[str, str]] = []
        self.actual_items: list[dict[str, str]] = []
        self.financial_returns: list[dict[str, str]] = []
        self.return_decisions: list[dict] = []
        self.return_base = {
            "products": simulation_entities(tables, "products"),
            "product_catalog": tables["product_catalog"],
            "return_policies": tables["return_policies"],
        }

    def _sale(
        self, demand: DemandArrival, route_id: str, position: tuple[str, str], quantity: int
    ) -> None:
        ref = self.requested_refs[demand.demand_id]
        requested_item = self.requested_items[ref["order_item_id"]]
        order = self.requested_orders[requested_item["order_id"]]
        store = self.stores[order["store_id"]]
        quote = self.pricing.quote(
            demand.product_id, store, ref["business_date"], order["ordered_at"], quantity
        )
        priced = demand.model_copy(
            update={"unit_price": money(quote.unit_price), "currency": quote.currency}
        )
        super()._sale(priced, route_id, position, quantity)
        executed = self.sales[demand.demand_id]
        executed.update(order_id=order["id"], ordered_at=order["ordered_at"])
        common = {
            "quantity": str(quantity),
            "unit_price": executed["unit_price"],
            "total_amount": executed["gross_revenue"],
            "currency": executed["currency"],
        }
        item = {**requested_item, **common}
        sale = {
            **self.requested_sales[demand.demand_id],
            **common,
            "id": executed["sale_id"],
            "observed_sales": str(quantity),
            "promotion_applied": str(bool(quote.promotion_plan_id)).lower(),
            "ingested_at": executed["ingested_at"],
        }
        self.actual_items.append(item)
        self.actual_sales.append(sale)
        self.pricing.record(
            sale["id"],
            item["id"],
            demand.product_id,
            store,
            ref["business_date"],
            order["ordered_at"],
            quote,
        )
        events = generate_return_events(
            {
                **self.return_base,
                "sales": [sale],
                "order_items": [item],
                "sale_price_references": [self.tables["sale_price_references"][-1]],
            },
            self.generation,
        )
        for event in events:
            self._schedule_financial_return(event, demand.demand_id, position)

    def _schedule_financial_return(
        self, event: dict[str, str], demand_id: str, position: tuple[str, str]
    ) -> None:
        event["available_at"] = max(
            utc_timestamp(event["available_at"]),
            utc_timestamp(self.sales[demand_id]["available_at"]),
        ).isoformat()
        self.financial_returns.append(event)
        stamp = utc_timestamp(event["returned_at"])
        quality = "accepted" if event["reason"] in RESTOCKABLE_REASONS else "rejected"
        disposition = (
            "not_refunded"
            if event["status"] != "refunded"
            else "outside_inventory_window"
            if stamp >= self.end
            else "restocked"
            if quality == "accepted"
            else "quality_rejected"
        )
        self.return_decisions.append(
            {
                "return_id": event["id"],
                "sale_id": event["sale_id"],
                "product_id": event["product_id"],
                "stock_location_id": position[1],
                "quantity": int(event["quantity"]),
                "quality_status": quality,
                "inventory_disposition": disposition,
                "returned_at": event["returned_at"],
                "financial_available_at": event["available_at"],
                "inventory_available_at": None,
            }
        )
        if disposition in {"not_refunded", "outside_inventory_window"}:
            return
        sequence = self.reserved_sequences.get(stamp, -1) + 1
        self.reserved_sequences[stamp] = sequence
        ingested = stamp + timedelta(seconds=self.config.return_inventory_ingestion_delay_seconds)
        available = ingested + timedelta(
            seconds=self.config.return_inventory_availability_delay_seconds
        )
        scheduled = ReturnEvent.model_validate(
            {
                "return_id": event["id"],
                "demand_id": demand_id,
                "product_id": event["product_id"],
                "stock_location_id": position[1],
                "unit_of_measure": self.units[position[0]],
                "returned_quantity": int(event["quantity"]),
                "quality_status": quality,
                "returned_at": event["returned_at"],
                "ingested_at": ingested.isoformat(),
                "available_at": available.isoformat(),
                "sequence": sequence,
                "source_reference": event["id"],
            }
        )
        heapq.heappush(self.queue, (stamp, 0, sequence, "return", scheduled))

    def _return(self, event: ReturnEvent) -> None:
        super()._return(event)
        processed = self.returns[-1]
        decision = next(r for r in self.return_decisions if r["return_id"] == event.return_id)
        decision["inventory_available_at"] = processed["available_at"]

    def actual_orders(self) -> list[dict[str, str]]:
        grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
        for item in self.actual_items:
            grouped[item["order_id"]].append(item)
        return [
            {
                **self.requested_orders[order_id],
                "order_total": money(
                    sum((Decimal(item["total_amount"]) for item in items), Decimal(0))
                ),
            }
            for order_id, items in sorted(grouped.items())
        ]
