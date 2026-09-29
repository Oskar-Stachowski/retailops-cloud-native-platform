"""Operational decisions; this module has no access to supplier or demand truth."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from data.generator.common import deterministic_uuid
from data.generator.identity import json_sha256
from data.inventory.contract import require, utc_timestamp
from data.inventory.replenishment_contract import DeliveryPlanVersion, ReplenishmentOrder

if TYPE_CHECKING:
    from datetime import datetime

    from data.inventory.ledger import InventoryLedger, InventoryMovement, Position
    from data.inventory.reorder_contract import HistoryCoverage, ReorderConfig, ReorderRule
    from data.inventory.replenishment import ReplenishmentBook
    from data.inventory.replenishment_contract import ProductSupplier


@dataclass(frozen=True)
class ReorderDecision:
    decision_id: str
    product_id: str
    stock_location_id: str
    origin: str
    status: str
    on_hand: int | None = None
    on_order: int | None = None
    stock_position: int | None = None
    observed_sales_quantity: int | None = None
    coverage_id: str | None = None
    product_supplier_id: str | None = None
    quoted_lead_time_days: int | None = None
    effective_moq: int | None = None
    target_quantity: int | None = None
    order_quantity: int = 0


@dataclass(frozen=True)
class ReorderReview:
    policy_sha256: str
    decisions: tuple[ReorderDecision, ...]
    orders: tuple[ReplenishmentOrder, ...]
    plans: tuple[DeliveryPlanVersion, ...]

    def record(self) -> dict[str, Any]:
        return {
            "policy_sha256": self.policy_sha256,
            "decisions": [asdict(d) for d in self.decisions],
            "new_orders": [o.model_dump() for o in self.orders],
            "initial_delivery_plans": [p.model_dump() for p in self.plans],
        }


def _validate_context(
    ledger: InventoryLedger,
    book: ReplenishmentBook,
    config: ReorderConfig,
    coverage: tuple[HistoryCoverage, ...],
) -> None:
    book.reconcile_ledger(ledger)
    require(
        {(r.product_id, r.stock_location_id) for r in config.rules} == set(ledger.scope),
        "Reorder configuration must exactly cover ledger scope.",
    )
    openings = {m.position: m for m in ledger.movements if m.movement_type == "opening_stock"}
    for c in coverage:
        position = c.product_id, c.stock_location_id
        require(position in openings, "History coverage references unknown inventory position.")
        require(
            utc_timestamp(c.covered_from_at) >= utc_timestamp(openings[position].occurred_at),
            "History coverage cannot assert data before opening.",
        )
    codes = {s.id: s.location_code for s in book.stock_locations}
    units = {p.id: p.unit_of_measure for p in book.products}
    require(
        all(
            units.get(p) == openings[(p, s)].unit_of_measure
            and codes.get(s) == dict(ledger.stock_location_codes).get(s)
            for p, s in ledger.scope
        ),
        "Supplier catalog differs from ledger product unit or physical location.",
    )


def _known_history(
    coverage: tuple[HistoryCoverage, ...],
    movements: tuple[InventoryMovement, ...],
    position: Position,
    cutoff: datetime,
    window_days: int,
) -> tuple[str, int] | None:
    window_start = cutoff - timedelta(days=window_days)
    certificates = [
        c
        for c in coverage
        if (c.product_id, c.stock_location_id) == position
        and utc_timestamp(c.covered_from_at) <= window_start
        and utc_timestamp(c.covered_through_at) >= cutoff
        and utc_timestamp(c.available_at) <= cutoff
    ]
    if not certificates:
        return None
    certificate = max(certificates, key=lambda c: (c.available_at, c.coverage_id))
    sold = sum(
        -m.quantity_delta
        for m in movements
        if m.position == position
        and m.movement_type == "sale"
        and window_start < utc_timestamp(m.occurred_at) <= cutoff
    )
    return certificate.coverage_id, sold


def _new_order(
    position: Position,
    quote: ProductSupplier,
    origin: str,
    quantity: int,
    decision_id: str,
) -> tuple[ReplenishmentOrder, DeliveryPlanVersion]:
    order_id = deterministic_uuid("replenishment_order", decision_id)
    promise = (utc_timestamp(origin) + timedelta(days=quote.quoted_lead_time_days)).isoformat()
    order = ReplenishmentOrder(
        replenishment_order_id=order_id,
        product_supplier_id=quote.product_supplier_id,
        product_id=position[0],
        supplier_id=quote.supplier_id,
        stock_location_id=position[1],
        ordered_quantity=quantity,
        unit_of_measure=quote.unit_of_measure,
        ordered_at=origin,
        expected_delivery_at=promise,
        ingested_at=origin,
        available_at=origin,
        status="ordered",
        source_reference=decision_id,
    )
    plan = DeliveryPlanVersion(
        plan_version_id=deterministic_uuid("delivery_plan", f"{order_id}:1"),
        replenishment_order_id=order_id,
        version=1,
        expected_delivery_at=promise,
        known_at=origin,
        ingested_at=origin,
        available_at=origin,
        source_reference=decision_id,
    )
    return order, plan


def _order_parameters(
    rule: ReorderRule,
    quote: ProductSupplier,
    supplier_moq: int,
    sold: int,
    stock_position: int,
) -> tuple[int, int, int]:
    moq = max(rule.minimum_order_quantity, supplier_moq)
    numerator = sold * (quote.quoted_lead_time_days + rule.review_cadence_days)
    target = max(
        rule.reorder_point + rule.safety_stock,
        rule.safety_stock + (numerator + rule.history_window_days - 1) // rule.history_window_days,
    )
    deficit = target - stock_position
    quantity = max(deficit, moq) if stock_position <= rule.reorder_point and deficit > 0 else 0
    return moq, target, quantity


def review_reorder(
    ledger: InventoryLedger,
    book: ReplenishmentBook,
    config: ReorderConfig,
    coverage: tuple[HistoryCoverage, ...],
    origin: str,
) -> ReorderReview:
    cutoff = utc_timestamp(origin)
    origin = cutoff.isoformat()
    _validate_context(ledger, book, config, coverage)
    balances = {
        (r["product_id"], r["stock_location_id"]): r
        for r in ledger.balances_at(origin, known_at=origin)
    }
    movements = ledger.known_movements(origin, known_at=origin)
    known_orders = book.orders_at(origin)
    suppliers = {s.supplier_id: s for s in book.suppliers}
    policy_hash = json_sha256(config.model_dump())
    decisions, new_orders, plans = [], [], []
    for rule in config.rules:
        position = rule.product_id, rule.stock_location_id
        decision_id = deterministic_uuid("reorder_decision", f"{policy_hash}:{position}:{origin}")
        attributes: dict[str, Any] = {
            "decision_id": decision_id,
            "product_id": position[0],
            "stock_location_id": position[1],
            "origin": origin,
        }
        elapsed = cutoff - utc_timestamp(config.review_anchor_at)
        cadence = timedelta(days=rule.review_cadence_days)
        if utc_timestamp(config.available_at) > cutoff:
            decisions.append(ReorderDecision(**attributes, status="config_unavailable"))
            continue
        if elapsed < timedelta(0) or elapsed % cadence != timedelta(0):
            decisions.append(ReorderDecision(**attributes, status="not_due"))
            continue
        if balances[position]["status"] != "known":
            decisions.append(ReorderDecision(**attributes, status="inventory_unknown"))
            continue
        on_hand = balances[position]["available_qty"]
        pending = sum(
            r["outstanding_quantity"]
            for r in known_orders
            if (r["product_id"], r["stock_location_id"]) == position
        )
        attributes.update(on_hand=on_hand, on_order=pending, stock_position=on_hand + pending)
        if any(
            r["source_reference"] == decision_id
            and (r["product_id"], r["stock_location_id"]) == position
            and r["ordered_at"] == origin
            for r in known_orders
        ):
            decisions.append(ReorderDecision(**attributes, status="already_ordered"))
            continue
        history = _known_history(coverage, movements, position, cutoff, rule.history_window_days)
        if history is None:
            decisions.append(ReorderDecision(**attributes, status="history_missing"))
            continue
        certificate_id, sold = history
        attributes.update(observed_sales_quantity=sold, coverage_id=certificate_id)
        quotes = book.known_quotes(position[0], cutoff.date().isoformat(), known_at=origin)
        if not quotes:
            decisions.append(ReorderDecision(**attributes, status="supplier_missing"))
            continue
        quote = quotes[0]
        moq, target, quantity = _order_parameters(
            rule,
            quote,
            suppliers[quote.supplier_id].minimum_order_quantity,
            sold,
            on_hand + pending,
        )
        attributes.update(
            product_supplier_id=quote.product_supplier_id,
            quoted_lead_time_days=quote.quoted_lead_time_days,
            effective_moq=moq,
            target_quantity=target,
        )
        if quantity == 0:
            decisions.append(ReorderDecision(**attributes, status="no_order"))
            continue
        order, plan = _new_order(position, quote, origin, quantity, decision_id)
        decisions.append(ReorderDecision(**attributes, status="ordered", order_quantity=quantity))
        new_orders.append(order)
        plans.append(plan)
    return ReorderReview(policy_hash, tuple(decisions), tuple(new_orders), tuple(plans))
