"""Generator-only chronological execution, with observable reviews isolated from truth."""

from __future__ import annotations

import heapq
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from data.generator.common import deterministic_uuid
from data.inventory.contract import require, utc_timestamp
from data.inventory.fulfillment_routes import resolve_route, validate_routes
from data.inventory.ledger import (
    InventoryLedger,
    InventoryMovement,
    transfer_pairs,
    validate_movement,
)
from data.inventory.reorder import review_reorder
from data.inventory.reorder_contract import ReorderConfig, parse_history_coverage
from data.inventory.replenishment import ReplenishmentBook
from data.inventory.simulation_contract import SIMULATION_VERSION, ChronologicalScenario
from data.inventory.supplier_fulfillment import FulfillmentConfig, simulate_fulfillment
from data.inventory.supplier_truth import validate_supplier_truth

if TYPE_CHECKING:
    from datetime import datetime

    from data.inventory.replenishment_contract import ReplenishmentReceipt
    from data.inventory.simulation_contract import DemandArrival, ReturnEvent


def money_amount(unit_price: str, quantity: int) -> str:
    cents = int(unit_price.replace(".", "")) * quantity
    return f"{cents // 100}.{cents % 100:02d}"


class ChronologicalSimulator:
    def __init__(
        self,
        inventory: dict,
        supply: dict,
        scenario: dict,
        policy: dict,
        fulfillment: dict,
        truth: dict,
    ) -> None:
        self.scenario = ChronologicalScenario.from_payload(scenario)
        self.policy = ReorderConfig.from_payload(policy)
        self.fulfillment = FulfillmentConfig.from_payload(fulfillment)
        initial = InventoryLedger.from_payload(inventory)
        book = ReplenishmentBook.from_payload(supply)
        self.start = utc_timestamp(self.scenario.settings.start_at)
        self.end = utc_timestamp(self.scenario.settings.end_at)
        self._validate_foundation(initial, book)
        self.units = {p.id: p.unit_of_measure for p in book.products}
        self.scope = set(initial.scope)
        self.routes = tuple(self.scenario.fulfillment_routes)
        validate_routes(self.routes, {s.id for s in book.stock_locations})
        self._validate_events()
        self.inventory_base = {
            **inventory,
            "opening_at": self.start.isoformat(),
            "products": [p.model_dump() for p in book.products],
            "stock_locations": [s.model_dump() for s in book.stock_locations],
            "inventory_scope": [
                {"product_id": p, "stock_location_id": s} for p, s in initial.scope
            ],
        }
        self.supply_base = {
            **supply,
            "products": [p.model_dump() for p in book.products],
            "stock_locations": [s.model_dump() for s in book.stock_locations],
            "suppliers": [s.model_dump() for s in book.suppliers],
            "product_suppliers": [q.model_dump() for q in book.product_suppliers],
        }
        self.parameters = {
            t.supplier_id: t
            for t in validate_supplier_truth(truth, {s.supplier_id for s in book.suppliers})
        }
        self.movements = list(initial.movements)
        self.balances = {m.position: m.quantity_delta for m in initial.movements}
        self.availability = {m.position: utc_timestamp(m.available_at) for m in initial.movements}
        self.orders: list[dict] = []
        self.plans: list[dict] = []
        self.receipts: list[dict] = []
        self.sales: dict[str, dict] = {}
        self.returns: list[dict] = []
        self.reviews: list[dict] = []
        self.coverage: list[dict] = []
        self.outcomes: list[dict] = []
        self.samples: list[dict] = []
        self.tail: list[dict] = []
        self._initialize_queue(initial)

    def _validate_foundation(self, ledger: InventoryLedger, book: ReplenishmentBook) -> None:
        require(
            all(
                m.movement_type == "opening_stock" and utc_timestamp(m.occurred_at) == self.start
                for m in ledger.movements
            ),
            "Chronological execution requires opening-only inventory at start.",
        )
        require(
            not book.orders and not book.plans and not book.receipts,
            "Chronological execution requires an empty initial order book.",
        )
        book.reconcile_ledger(ledger)
        require(
            {(r.product_id, r.stock_location_id) for r in self.policy.rules} == set(ledger.scope),
            "Policy must exactly cover simulation scope.",
        )
        require(
            {p.id: p.unit_of_measure for p in book.products}
            == {m.product_id: m.unit_of_measure for m in ledger.movements},
            "Simulation product units differ from opening.",
        )
        require(
            {s.id: s.location_code for s in book.stock_locations}
            == dict(ledger.stock_location_codes),
            "Simulation physical locations differ from opening.",
        )
        anchor = utc_timestamp(self.policy.review_anchor_at)
        require(
            self.start + timedelta(days=max(r.history_window_days for r in self.policy.rules))
            <= anchor
            <= self.end,
            "Review anchor must allow full warmup and at least one review.",
        )

    def _validate_events(self) -> None:
        selling = {s.id for s in self.scenario.selling_locations}
        for demand in self.scenario.demand_arrivals:
            require(
                demand.product_id in self.units and demand.selling_location_id in selling,
                "Demand references unknown product or selling location.",
            )
            require(
                int(demand.unit_price.replace(".", "")) > 0, "Sale unit price must be positive."
            )
        actions = tuple(
            InventoryMovement.from_record(a.model_dump()) for a in self.scenario.inventory_actions
        )
        for action in actions:
            require(
                action.movement_type
                in {"inventory_adjustment", "write_off", "transfer_in", "transfer_out"},
                "Only explicit adjustments, write-offs and paired transfers are scenario actions.",
            )
            validate_movement(action, self.units, self.scope)
        pairs = transfer_pairs(tuple(a for a in actions if a.transfer_id is not None))
        self.transfer_inbounds = {out.transfer_id: inbound for out, inbound in pairs}

    def _initialize_queue(self, initial: InventoryLedger) -> None:
        self.queue: list[tuple[datetime, int, int, str, Any]] = []
        self.reserved_sequences: dict[datetime, int] = {}
        keys = {m.ordering_key for m in initial.movements}
        for kind, rows, field in (
            ("demand", self.scenario.demand_arrivals, "occurred_at"),
            ("return", self.scenario.return_events, "returned_at"),
            ("action", self.scenario.inventory_actions, "occurred_at"),
        ):
            for row in rows:
                stamp = utc_timestamp(getattr(row, field))
                require(
                    (stamp, row.sequence) not in keys,
                    "Event timestamp/sequence collides with opening or another event.",
                )
                keys.add((stamp, row.sequence))
                self.reserved_sequences[stamp] = max(
                    self.reserved_sequences.get(stamp, -1), row.sequence
                )
                heapq.heappush(self.queue, (stamp, 0, row.sequence, kind, row))
        stamp = utc_timestamp(self.policy.review_anchor_at)
        while stamp <= self.end:
            heapq.heappush(self.queue, (stamp, 1, 0, "review", None))
            stamp += timedelta(days=1)

    def _book_payload(self) -> dict:
        return {
            **self.supply_base,
            "replenishment_orders": self.orders,
            "delivery_plan_versions": self.plans,
            "replenishment_receipts": self.receipts,
        }

    def _ledger(self) -> InventoryLedger:
        present = {m.inventory_event_id for m in self.movements}
        pending = []
        for out in self.movements:
            if out.movement_type == "transfer_out":
                inbound = self.transfer_inbounds[out.transfer_id]
                if inbound.inventory_event_id not in present:
                    record = inbound.record()
                    record["available_at"] = max(
                        utc_timestamp(inbound.available_at),
                        utc_timestamp(out.available_at),
                        self.availability[inbound.position],
                    ).isoformat()
                    pending.append(record)
        return InventoryLedger.from_payload(
            {**self.inventory_base, "movements": [*(m.record() for m in self.movements), *pending]}
        )

    def _apply(self, record: dict) -> InventoryMovement:
        movement = InventoryMovement.from_record(record)
        validate_movement(movement, self.units, self.scope)
        require(
            not any(m.inventory_event_id == movement.inventory_event_id for m in self.movements),
            "Duplicate generated inventory event ID.",
        )
        available = max(utc_timestamp(movement.available_at), self.availability[movement.position])
        if movement.movement_type == "transfer_in":
            outbound = next(
                m
                for m in self.movements
                if m.transfer_id == movement.transfer_id and m.movement_type == "transfer_out"
            )
            available = max(available, utc_timestamp(outbound.available_at))
        movement = InventoryMovement.from_record(
            {**movement.record(), "available_at": available.isoformat()}
        )
        quantity = self.balances[movement.position] + movement.quantity_delta
        require(quantity >= 0, "Physical event would produce a negative inventory balance.")
        self.balances[movement.position] = quantity
        self.availability[movement.position] = available
        self.movements.append(movement)
        return movement

    def _movement(
        self,
        event_id: str,
        position: tuple[str, str],
        kind: str,
        quantity: int,
        happened: str,
        ingested: str,
        available: str,
        sequence: int,
        reference: str,
    ) -> dict:
        return {
            "inventory_event_id": event_id,
            "product_id": position[0],
            "stock_location_id": position[1],
            "movement_type": kind,
            "quantity_delta": quantity,
            "unit_of_measure": self.units[position[0]],
            "occurred_at": happened,
            "ingested_at": ingested,
            "available_at": available,
            "sequence": sequence,
            "source_process": "sale" if kind == "sale" else "return",
            "source_reference": reference,
            "transfer_id": None,
            "supplier_id": None,
            "order_id": None,
        }

    def _demand(self, demand: DemandArrival) -> None:
        route = resolve_route(
            self.routes, demand.selling_location_id, demand.channel, demand.occurred_at
        )
        position = demand.product_id, route.stock_location_id
        require(position in self.scope, "Fulfillment maps product outside declared stock scope.")
        before = self.balances[position]
        quantity = min(demand.latent_quantity, before)
        if quantity:
            self._sale(demand, route.id, position, quantity)
        self.outcomes.append(
            {
                "demand_id": demand.demand_id,
                "product_id": demand.product_id,
                "selling_location_id": demand.selling_location_id,
                "channel": demand.channel,
                "stock_location_id": position[1],
                "occurred_at": utc_timestamp(demand.occurred_at).isoformat(),
                "sequence": demand.sequence,
                "latent_quantity": demand.latent_quantity,
                "observed_quantity": quantity,
                "lost_sales_quantity": demand.latent_quantity - quantity,
                "stock_before": before,
                "stock_after": self.balances[position],
                "reason": "no_demand"
                if demand.latent_quantity == 0
                else "inventory_constraint"
                if quantity < demand.latent_quantity
                else "fulfilled",
            }
        )

    def _sale(
        self, demand: DemandArrival, route_id: str, position: tuple[str, str], quantity: int
    ) -> None:
        stamp = utc_timestamp(demand.occurred_at)
        ingestion = stamp + timedelta(seconds=self.scenario.settings.sale_ingestion_delay_seconds)
        availability = ingestion + timedelta(
            seconds=self.scenario.settings.sale_availability_delay_seconds
        )
        sale_id = deterministic_uuid("inventory_sale", f"{SIMULATION_VERSION}:{demand.demand_id}")
        movement = self._apply(
            self._movement(
                deterministic_uuid("inventory_event", sale_id),
                position,
                "sale",
                -quantity,
                stamp.isoformat(),
                ingestion.isoformat(),
                availability.isoformat(),
                demand.sequence,
                sale_id,
            )
        )
        self.sales[demand.demand_id] = {
            "sale_id": sale_id,
            "order_id": deterministic_uuid("customer_order", sale_id),
            "product_id": demand.product_id,
            "selling_location_id": demand.selling_location_id,
            "channel": demand.channel,
            "stock_location_id": position[1],
            "fulfillment_route_id": route_id,
            "quantity": quantity,
            "unit_of_measure": self.units[position[0]],
            "unit_price": demand.unit_price,
            "currency": demand.currency,
            "gross_revenue": money_amount(demand.unit_price, quantity),
            "ordered_at": stamp.isoformat(),
            "sold_at": stamp.isoformat(),
            "ingested_at": movement.ingested_at,
            "available_at": movement.available_at,
            "sequence": movement.sequence,
            "source_reference": demand.demand_id,
        }

    def _return(self, event: ReturnEvent) -> None:
        require(event.demand_id in self.sales, "Return has no preceding fulfilled sale.")
        sale = self.sales[event.demand_id]
        require(
            (event.product_id, event.stock_location_id, event.unit_of_measure)
            == (sale["product_id"], sale["stock_location_id"], sale["unit_of_measure"]),
            "Return product, original fulfillment location or unit differs from sale.",
        )
        total = (
            sum(r["quantity"] for r in self.returns if r["sale_id"] == sale["sale_id"])
            + event.returned_quantity
        )
        require(
            total <= sale["quantity"], "Cumulative returned quantity exceeds fulfilled purchase."
        )
        happened = utc_timestamp(event.returned_at).isoformat()
        ingested = max(
            utc_timestamp(event.ingested_at), utc_timestamp(sale["ingested_at"])
        ).isoformat()
        available = max(
            utc_timestamp(event.available_at),
            utc_timestamp(sale["available_at"]),
            utc_timestamp(ingested),
        ).isoformat()
        if event.quality_status == "accepted":
            movement = self._apply(
                self._movement(
                    deterministic_uuid(
                        "inventory_event", f"{SIMULATION_VERSION}:return:{event.return_id}"
                    ),
                    (event.product_id, event.stock_location_id),
                    "return_to_stock",
                    event.returned_quantity,
                    happened,
                    ingested,
                    available,
                    event.sequence,
                    event.return_id,
                )
            )
            available = movement.available_at
        self.returns.append(
            {
                "return_id": event.return_id,
                "sale_id": sale["sale_id"],
                "product_id": event.product_id,
                "stock_location_id": event.stock_location_id,
                "unit_of_measure": event.unit_of_measure,
                "quantity": event.returned_quantity,
                "quality_status": event.quality_status,
                "refund_amount": money_amount(sale["unit_price"], event.returned_quantity),
                "currency": sale["currency"],
                "returned_at": happened,
                "ingested_at": ingested,
                "available_at": available,
                "sequence": event.sequence,
                "source_reference": event.source_reference,
            }
        )

    def _receipt(self, receipt: ReplenishmentReceipt) -> None:
        position = receipt.product_id, receipt.stock_location_id
        receipt = receipt.model_copy(
            update={
                "available_at": max(
                    utc_timestamp(receipt.available_at), self.availability[position]
                ).isoformat()
            }
        )
        self.receipts.append(receipt.model_dump())
        book = ReplenishmentBook.from_payload(self._book_payload())
        movement = next(
            m for m in book.receipt_movements() if m.source_reference == receipt.receipt_id
        )
        self._apply(movement.record())

    def _review(self, stamp: datetime) -> None:
        coverage: dict[str, Any] = {
            "contract_version": "inventory-history-coverage-1.0.0",
            "coverage_basis": "observed_ledger_stream",
            "coverage": [
                {
                    "coverage_id": deterministic_uuid(
                        "history_coverage",
                        f"{SIMULATION_VERSION}:{p}:{s}:{self.start.isoformat()}:{stamp.isoformat()}",
                    ),
                    "product_id": p,
                    "stock_location_id": s,
                    "covered_from_at": self.start.isoformat(),
                    "covered_through_at": stamp.isoformat(),
                    "available_at": stamp.isoformat(),
                    "source_reference": "chronological-processed-window",
                }
                for p, s in sorted(self.scope)
            ],
        }
        book = ReplenishmentBook.from_payload(self._book_payload())
        result = review_reorder(
            self._ledger(), book, self.policy, parse_history_coverage(coverage), stamp.isoformat()
        )
        self.coverage.extend(coverage["coverage"])
        self.reviews.append({"origin": stamp.isoformat(), **result.record()})
        self.orders.extend(o.model_dump() for o in result.orders)
        self.plans.extend(p.model_dump() for p in result.plans)
        for order in result.orders:
            sample = simulate_fulfillment(
                order, self.parameters[order.supplier_id], self.fulfillment, first_sequence=0
            )
            self.samples.append(
                {
                    "order_id": order.replenishment_order_id,
                    "simulation_id": sample.simulation_id,
                    "disrupted": sample.disrupted,
                    "lead_days": sample.lead_days,
                }
            )
            for receipt in sample.receipts:
                time = utc_timestamp(receipt.received_at)
                sequence = self.reserved_sequences.get(time, -1) + 1
                self.reserved_sequences[time] = sequence
                scheduled = receipt.model_copy(update={"sequence": sequence})
                if time < self.end:
                    heapq.heappush(self.queue, (time, 0, sequence, "receipt", scheduled))
                else:
                    self.tail.append(scheduled.model_dump())

    def execute(self) -> dict[str, Any]:
        while self.queue:
            stamp, _phase, _sequence, kind, row = heapq.heappop(self.queue)
            if kind == "review":
                self._review(stamp)
            elif kind == "demand":
                self._demand(row)
            elif kind == "return":
                self._return(row)
            elif kind == "receipt":
                self._receipt(row)
            else:
                self._apply(row.model_dump())
        ledger = self._ledger()
        require(
            len(ledger.movements) == len(self.movements),
            "Unfinished transfer remains at simulation end.",
        )
        book = ReplenishmentBook.from_payload(self._book_payload())
        reconciliation = book.reconcile_ledger(ledger)
        return {
            "operational": {
                "ledger": {
                    **self.inventory_base,
                    "movements": [m.record() for m in ledger.movements],
                },
                "supply": self._book_payload(),
                "sales": list(self.sales.values()),
                "returns": self.returns,
                "fulfillment_routes": [
                    {**r.model_dump(), "available_at": utc_timestamp(r.available_at).isoformat()}
                    for r in sorted(self.routes, key=lambda r: r.id)
                ],
                "reviews": self.reviews,
                "selling_locations": [
                    s.model_dump()
                    for s in sorted(self.scenario.selling_locations, key=lambda s: s.id)
                ],
                "history_coverage": self.coverage,
            },
            "simulation_truth": {
                "data_class": "simulation_truth",
                "demand_outcomes": self.outcomes,
                "supplier_samples": self.samples,
                "scheduled_receipt_tail": self.tail,
            },
            "reconciliation": reconciliation,
            "final_physical_positions": ledger.balances_at(self.end.isoformat()),
            "final_known_positions": ledger.balances_at(
                self.end.isoformat(), known_at=self.end.isoformat()
            ),
        }
