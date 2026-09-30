from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from itertools import pairwise
from typing import TYPE_CHECKING, Any, TypeVar

from data.generator.common import deterministic_uuid
from data.inventory.contract import Product, StockLocation, require, utc_timestamp
from data.inventory.ledger import InventoryMovement
from data.inventory.replenishment_contract import (
    REPLENISHMENT_VERSION,
    DeliveryPlanVersion,
    ProductSupplier,
    ReplenishmentOrder,
    ReplenishmentReceipt,
    Supplier,
    SupplyRecord,
    parse_replenishment,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from data.inventory.ledger import InventoryLedger

Record = TypeVar("Record", bound=SupplyRecord)


def _index(rows: Iterable[Record], field: str) -> dict[str, Record]:
    result = {}
    count = 0
    for row in rows:
        count += 1
        result[getattr(row, field)] = row
    require(len(result) == count, "Duplicate replenishment primary key: " + field)
    return result


def _normalize(row: Record, fields: tuple[str, ...]) -> Record:
    values = {field: utc_timestamp(getattr(row, field)).isoformat() for field in fields}
    return row.model_copy(update=values)


def _chronology(
    row: ProductSupplier | ReplenishmentOrder | DeliveryPlanVersion | ReplenishmentReceipt,
    business_field: str,
) -> None:
    require(
        utc_timestamp(getattr(row, business_field))
        <= utc_timestamp(row.ingested_at)
        <= utc_timestamp(row.available_at),
        "Supply requires business/known time <= ingested_at <= available_at.",
    )


@dataclass(frozen=True)
class ReplenishmentBook:
    products: tuple[Product, ...]
    stock_locations: tuple[StockLocation, ...]
    suppliers: tuple[Supplier, ...]
    product_suppliers: tuple[ProductSupplier, ...]
    orders: tuple[ReplenishmentOrder, ...]
    plans: tuple[DeliveryPlanVersion, ...]
    receipts: tuple[ReplenishmentReceipt, ...]

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> ReplenishmentBook:
        parsed = parse_replenishment(payload)
        require(
            len({p.id for p in parsed.products}) == len(parsed.products), "Duplicate product ID."
        )
        require(
            len({s.id for s in parsed.stock_locations}) == len(parsed.stock_locations),
            "Duplicate stock location ID.",
        )
        require(
            len({s.location_code for s in parsed.stock_locations}) == len(parsed.stock_locations),
            "Duplicate stock location code.",
        )
        result = cls(
            tuple(sorted(parsed.products, key=lambda r: r.id)),
            tuple(sorted(parsed.stock_locations, key=lambda r: r.id)),
            tuple(
                sorted(
                    (_normalize(r, ("available_at",)) for r in parsed.suppliers),
                    key=lambda r: r.supplier_id,
                )
            ),
            tuple(
                sorted(
                    (
                        _normalize(r, ("known_at", "ingested_at", "available_at"))
                        for r in parsed.product_suppliers
                    ),
                    key=lambda r: r.product_supplier_id,
                )
            ),
            tuple(
                sorted(
                    (
                        _normalize(
                            r, ("ordered_at", "expected_delivery_at", "ingested_at", "available_at")
                        )
                        for r in parsed.replenishment_orders
                    ),
                    key=lambda r: r.replenishment_order_id,
                )
            ),
            tuple(
                sorted(
                    (
                        _normalize(
                            r, ("expected_delivery_at", "known_at", "ingested_at", "available_at")
                        )
                        for r in parsed.delivery_plan_versions
                    ),
                    key=lambda r: (r.replenishment_order_id, r.version),
                )
            ),
            tuple(
                sorted(
                    (
                        _normalize(r, ("received_at", "ingested_at", "available_at"))
                        for r in parsed.replenishment_receipts
                    ),
                    key=lambda r: (utc_timestamp(r.received_at), r.sequence),
                )
            ),
        )
        result._validate_quotes()
        result._validate_orders()
        result._validate_plans()
        result._validate_receipts()
        return result

    def _validate_quotes(self) -> None:
        suppliers = _index(self.suppliers, "supplier_id")
        require(
            len({s.supplier_code for s in suppliers.values()}) == len(suppliers),
            "Duplicate supplier code.",
        )
        products = {p.id: p for p in self.products}
        offers = _index(self.product_suppliers, "product_supplier_id")
        periods = defaultdict(list)
        for offer in offers.values():
            require(
                offer.product_id in products and offer.supplier_id in suppliers,
                "Quote references unknown product or supplier.",
            )
            require(
                offer.unit_of_measure == products[offer.product_id].unit_of_measure,
                "Quote unit differs from catalog.",
            )
            require(Decimal(offer.unit_cost) > 0, "Quoted unit cost must be positive.")
            first, last = (
                date.fromisoformat(offer.effective_from),
                date.fromisoformat(offer.effective_to),
            )
            require(first < last, "Quote effective period must be nonempty and half-open.")
            _chronology(offer, "known_at")
            require(
                utc_timestamp(suppliers[offer.supplier_id].available_at)
                <= utc_timestamp(offer.known_at),
                "Quote predates known supplier metadata.",
            )
            periods[(offer.product_id, offer.supplier_id)].append((first, last))
        for group in periods.values():
            ordered = sorted(group)
            require(
                all(left[1] <= right[0] for left, right in pairwise(ordered)),
                "Ambiguous overlapping product-supplier quotes.",
            )

    def known_quotes(
        self, product_id: str, business_date: str, *, known_at: str
    ) -> tuple[ProductSupplier, ...]:
        day, cutoff = date.fromisoformat(business_date), utc_timestamp(known_at)
        suppliers = {s.supplier_id: s for s in self.suppliers}
        require(product_id in {p.id for p in self.products}, "Unknown product for supplier lookup.")
        return tuple(
            sorted(
                (
                    q
                    for q in self.product_suppliers
                    if q.product_id == product_id
                    and date.fromisoformat(q.effective_from)
                    <= day
                    < date.fromisoformat(q.effective_to)
                    and utc_timestamp(q.available_at) <= cutoff
                    and suppliers[q.supplier_id].status == "active"
                    and utc_timestamp(suppliers[q.supplier_id].available_at) <= cutoff
                ),
                key=lambda q: (q.priority, q.supplier_id, q.product_supplier_id),
            )
        )

    def _validate_orders(self) -> None:
        orders = _index(self.orders, "replenishment_order_id")
        offers = _index(self.product_suppliers, "product_supplier_id")
        suppliers = _index(self.suppliers, "supplier_id")
        locations = {s.id for s in self.stock_locations}
        for order in orders.values():
            require(order.product_supplier_id in offers, "Order references unknown quote.")
            quote = offers[order.product_supplier_id]
            require(
                (order.product_id, order.supplier_id, order.unit_of_measure)
                == (quote.product_id, quote.supplier_id, quote.unit_of_measure),
                "Order differs from its product-supplier quote.",
            )
            require(order.stock_location_id in locations, "Order references unknown destination.")
            _chronology(order, "ordered_at")
            require(
                utc_timestamp(order.expected_delivery_at) >= utc_timestamp(order.ordered_at),
                "Expected delivery precedes ordering.",
            )
            require(
                order.ordered_quantity >= suppliers[order.supplier_id].minimum_order_quantity,
                "Order is below supplier MOQ.",
            )
            eligible = self.known_quotes(
                order.product_id,
                utc_timestamp(order.ordered_at).date().isoformat(),
                known_at=order.ordered_at,
            )
            require(
                quote in eligible,
                "Order quote is inactive, out of period or unavailable at ordering.",
            )

    def _validate_plans(self) -> None:
        _index(self.plans, "plan_version_id")
        orders = _index(self.orders, "replenishment_order_id")
        groups = defaultdict(list)
        for plan in self.plans:
            require(
                plan.replenishment_order_id in orders, "Delivery plan references unknown order."
            )
            order = orders[plan.replenishment_order_id]
            _chronology(plan, "known_at")
            require(
                utc_timestamp(order.ordered_at) <= utc_timestamp(plan.known_at),
                "Delivery revision predates order.",
            )
            require(
                utc_timestamp(order.ordered_at) <= utc_timestamp(plan.expected_delivery_at),
                "Delivery promise predates order.",
            )
            groups[plan.replenishment_order_id].append(plan)
        require(set(groups) == set(orders), "Every order requires its initial delivery plan.")
        for order_id, group in groups.items():
            order = orders[order_id]
            require(
                [p.version for p in group] == list(range(1, len(group) + 1)),
                "Delivery versions must be unique and consecutive from one.",
            )
            first = group[0]
            require(
                (first.known_at, first.ingested_at, first.available_at, first.expected_delivery_at)
                == (
                    order.ordered_at,
                    order.ingested_at,
                    order.available_at,
                    order.expected_delivery_at,
                ),
                "Initial delivery plan must match the order promise and availability.",
            )
            require(
                all(
                    utc_timestamp(a.known_at) <= utc_timestamp(b.known_at)
                    and utc_timestamp(a.available_at) <= utc_timestamp(b.available_at)
                    for a, b in pairwise(group)
                ),
                "Delivery versions must preserve chronological knowledge.",
            )

    def _validate_receipts(self) -> None:
        _index(self.receipts, "receipt_id")
        orders = _index(self.orders, "replenishment_order_id")
        quantities: dict[str, int] = defaultdict(int)
        require(
            len({(r.received_at, r.sequence) for r in self.receipts}) == len(self.receipts),
            "Duplicate receipt timestamp/sequence.",
        )
        for receipt in self.receipts:
            require(receipt.replenishment_order_id in orders, "Receipt references unknown order.")
            order = orders[receipt.replenishment_order_id]
            require(
                (
                    receipt.product_id,
                    receipt.supplier_id,
                    receipt.stock_location_id,
                    receipt.unit_of_measure,
                )
                == (
                    order.product_id,
                    order.supplier_id,
                    order.stock_location_id,
                    order.unit_of_measure,
                ),
                "Receipt differs from order product, supplier, destination or unit.",
            )
            _chronology(receipt, "received_at")
            require(
                utc_timestamp(order.ordered_at) <= utc_timestamp(receipt.received_at),
                "Receipt precedes order.",
            )
            require(
                utc_timestamp(order.available_at) <= utc_timestamp(receipt.available_at),
                "Receipt is known before its order.",
            )
            quantities[receipt.replenishment_order_id] += receipt.received_quantity
            require(
                quantities[receipt.replenishment_order_id] <= order.ordered_quantity,
                "Cumulative receipts exceed ordered quantity.",
            )

    def orders_at(self, known_at: str) -> list[dict[str, Any]]:
        cutoff = utc_timestamp(known_at)
        latest_plans = {}
        received_by_order: dict[str, int] = defaultdict(int)
        for plan in self.plans:
            if utc_timestamp(plan.available_at) <= cutoff:
                latest_plans[plan.replenishment_order_id] = plan
        for receipt in self.receipts:
            if utc_timestamp(receipt.available_at) <= cutoff:
                received_by_order[receipt.replenishment_order_id] += receipt.received_quantity
        result = []
        for order in self.orders:
            if utc_timestamp(order.available_at) > cutoff:
                continue
            plan = latest_plans[order.replenishment_order_id]
            received = received_by_order[order.replenishment_order_id]
            result.append(
                {
                    **order.model_dump(),
                    "expected_delivery_at": plan.expected_delivery_at,
                    "delivery_plan_version": plan.version,
                    "received_quantity": received,
                    "outstanding_quantity": order.ordered_quantity - received,
                    "status": "ordered"
                    if received == 0
                    else "received"
                    if received == order.ordered_quantity
                    else "partially_received",
                }
            )
        return result

    def receipt_movements(self) -> tuple[InventoryMovement, ...]:
        return tuple(
            InventoryMovement.from_record(
                {
                    "inventory_event_id": deterministic_uuid(
                        "inventory_event", f"{REPLENISHMENT_VERSION}:receipt:{receipt.receipt_id}"
                    ),
                    "product_id": receipt.product_id,
                    "stock_location_id": receipt.stock_location_id,
                    "movement_type": "replenishment_received",
                    "quantity_delta": receipt.received_quantity,
                    "unit_of_measure": receipt.unit_of_measure,
                    "occurred_at": receipt.received_at,
                    "ingested_at": receipt.ingested_at,
                    "available_at": receipt.available_at,
                    "sequence": receipt.sequence,
                    "source_process": "replenishment",
                    "source_reference": receipt.receipt_id,
                    "supplier_id": receipt.supplier_id,
                    "order_id": receipt.replenishment_order_id,
                    "transfer_id": None,
                }
            )
            for receipt in self.receipts
        )

    def reconcile_ledger(self, ledger: InventoryLedger) -> dict[str, int]:
        expected = {m.inventory_event_id: m for m in self.receipt_movements()}
        actual = {
            m.inventory_event_id: m
            for m in ledger.movements
            if m.movement_type == "replenishment_received"
        }
        require(
            expected == actual, "Ledger replenishments must match actual receipts exactly once."
        )
        codes = {s.id: s.location_code for s in self.stock_locations}
        ledger_codes = dict(ledger.stock_location_codes)
        require(
            all(
                codes[o.stock_location_id] == ledger_codes.get(o.stock_location_id)
                for o in self.orders
            ),
            "Order destination differs from ledger physical location.",
        )
        require(
            all((o.product_id, o.stock_location_id) in ledger.scope for o in self.orders),
            "Order destination is outside ledger inventory scope.",
        )
        ledger_units = {
            m.position: m.unit_of_measure
            for m in ledger.movements
            if m.movement_type == "opening_stock"
        }
        require(
            all(
                o.unit_of_measure == ledger_units[(o.product_id, o.stock_location_id)]
                for o in self.orders
            ),
            "Order unit differs from ledger inventory unit.",
        )
        return {
            "orders": len(self.orders),
            "receipts": len(self.receipts),
            "receipt_movements": len(actual),
            "received_quantity": sum(r.received_quantity for r in self.receipts),
        }
