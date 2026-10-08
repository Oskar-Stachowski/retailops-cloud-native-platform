from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass, fields
from functools import cached_property
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from data.generator.common import deterministic_uuid
from data.inventory.contract import (
    LEDGER_VERSION,
    MOVEMENT_PROCESSES,
    NEGATIVE_MOVEMENTS,
    POSITIVE_MOVEMENTS,
    require,
    utc_timestamp,
    validate_structure,
)
from data.inventory.ledger_index import PositionIndex

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import datetime

Position = tuple[str, str]


@dataclass(frozen=True)
class InventoryMovement:
    inventory_event_id: str
    product_id: str
    stock_location_id: str
    movement_type: str
    quantity_delta: int
    unit_of_measure: str
    occurred_at: str
    ingested_at: str
    available_at: str
    sequence: int
    source_process: str
    source_reference: str
    transfer_id: str | None
    supplier_id: str | None
    order_id: str | None

    @property
    def position(self) -> Position:
        return self.product_id, self.stock_location_id

    @cached_property
    def occurred_time(self) -> datetime:
        return utc_timestamp(self.occurred_at)

    @cached_property
    def available_time(self) -> datetime:
        return utc_timestamp(self.available_at)

    @cached_property
    def ordering_key(self) -> tuple[datetime, int]:
        return self.occurred_time, self.sequence

    def record(self) -> dict[str, Any]:
        # Valid movements contain immutable CSV scalars. Avoid recursively
        # deepcopying every scalar on each full-ledger view. Keep asdict's
        # behavior for malformed/replaced objects until validation rejects them.
        values = {field.name: getattr(self, field.name) for field in fields(self)}
        if all(type(value) in (str, int, type(None)) for value in values.values()):
            return values
        return asdict(self)

    @classmethod
    def from_record(cls, row: dict[str, Any]) -> InventoryMovement:
        normalized = {
            **row,
            **{
                field: utc_timestamp(row[field]).isoformat()
                for field in ("occurred_at", "ingested_at", "available_at")
            },
        }
        return cls(**normalized)


def build_opening_movements(
    quantities: Mapping[Position, int],
    product_units: Mapping[str, str],
    *,
    occurred_at: str,
    ingested_at: str,
    available_at: str,
) -> list[dict[str, Any]]:
    """Create one opening event per declared position, including zero openings."""
    happened, ingested, available = map(utc_timestamp, (occurred_at, ingested_at, available_at))
    require(happened <= ingested <= available, "Invalid opening availability chronology.")
    rows = []
    for sequence, ((product, location), quantity) in enumerate(sorted(quantities.items())):
        require(
            type(quantity) is int and quantity >= 0,
            "Opening quantity must be a nonnegative integer.",
        )
        require(product in product_units, "Opening references an unknown product.")
        reference = f"opening:{product}:{location}"
        rows.append(
            InventoryMovement(
                deterministic_uuid(
                    "inventory_event", f"{LEDGER_VERSION}:{reference}:{happened.isoformat()}"
                ),
                product,
                location,
                "opening_stock",
                quantity,
                product_units[product],
                happened.isoformat(),
                ingested.isoformat(),
                available.isoformat(),
                sequence,
                "opening",
                reference,
                None,
                None,
                None,
            ).record()
        )
    return rows


def validate_movement(
    movement: InventoryMovement, units: dict[str, str], scope: set[Position]
) -> None:
    require(movement.position in scope, "Movement is outside the declared inventory scope.")
    require(
        movement.unit_of_measure == units[movement.product_id],
        "Movement unit differs from product unit.",
    )
    require(type(movement.quantity_delta) is int, "Movement quantity must be a typed integer.")
    require(type(movement.sequence) is int, "Movement sequence must be a typed integer.")
    require(
        movement.source_process == MOVEMENT_PROCESSES[movement.movement_type],
        "Movement type does not match its source process.",
    )
    happened, ingested, available = map(
        utc_timestamp, (movement.occurred_at, movement.ingested_at, movement.available_at)
    )
    require(
        happened <= ingested <= available, "Require occurred_at <= ingested_at <= available_at."
    )
    quantity, kind = movement.quantity_delta, movement.movement_type
    if kind in POSITIVE_MOVEMENTS:
        require(quantity > 0, "Inbound quantity must be positive.")
    elif kind in NEGATIVE_MOVEMENTS:
        require(quantity < 0, "Outbound quantity must be negative.")
    elif kind == "opening_stock":
        require(quantity >= 0, "Opening quantity must be nonnegative.")
    else:
        require(quantity != 0, "An adjustment must have a nonzero signed quantity.")
    require(
        (movement.transfer_id is not None) == kind.startswith("transfer_"),
        "Only transfer movements require a transfer ID.",
    )


def transfer_pairs(
    movements: tuple[InventoryMovement, ...],
) -> tuple[tuple[InventoryMovement, InventoryMovement], ...]:
    groups = defaultdict(list)
    for movement in movements:
        if movement.transfer_id is not None:
            groups[movement.transfer_id].append(movement)
    pairs = []
    for group in groups.values():
        require(
            len(group) == 2 and {m.movement_type for m in group} == {"transfer_out", "transfer_in"},
            "A complete ledger requires one outbound and one inbound per transfer.",
        )
        outbound = next(m for m in group if m.movement_type == "transfer_out")
        inbound = next(m for m in group if m.movement_type == "transfer_in")
        require(
            outbound.product_id == inbound.product_id
            and outbound.unit_of_measure == inbound.unit_of_measure
            and outbound.stock_location_id != inbound.stock_location_id
            and -outbound.quantity_delta == inbound.quantity_delta,
            "Transfer must preserve product, unit and quantity between distinct locations.",
        )
        require(
            outbound.ordering_key < inbound.ordering_key
            and utc_timestamp(outbound.available_at) <= utc_timestamp(inbound.available_at),
            "Transfer inbound must follow outbound in physical and knowledge order.",
        )
        pairs.append((outbound, inbound))
    return tuple(pairs)


@dataclass(frozen=True)
class InventoryLedger:
    movements: tuple[InventoryMovement, ...]
    scope: tuple[Position, ...]
    stock_location_codes: tuple[tuple[str, str], ...]
    transfers: tuple[tuple[InventoryMovement, InventoryMovement], ...]

    @cached_property
    def _movement_groups(self) -> Mapping[Position, tuple[InventoryMovement, ...]]:
        grouped: dict[Position, list[InventoryMovement]] = defaultdict(list)
        for movement in self.movements:
            grouped[movement.position].append(movement)
        return MappingProxyType({position: tuple(rows) for position, rows in grouped.items()})

    def movements_by_position(self) -> Mapping[Position, tuple[InventoryMovement, ...]]:
        """Group movements once for validated immutable ledgers."""
        if getattr(self, "_payload_validated", False):
            return self._movement_groups
        grouped: dict[Position, list[InventoryMovement]] = defaultdict(list)
        for movement in self.movements:
            grouped[movement.position].append(movement)
        return {position: tuple(rows) for position, rows in grouped.items()}

    @cached_property
    def _position_index(self) -> Mapping[Position, PositionIndex]:
        return MappingProxyType(
            {
                position: PositionIndex.build(rows)
                for position, rows in self._movement_groups.items()
            }
        )

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> InventoryLedger:
        validate_structure(payload)
        units = {row["id"]: row["unit_of_measure"] for row in payload["products"]}
        codes = {row["id"]: row["location_code"] for row in payload["stock_locations"]}
        require(len(units) == len(payload["products"]), "Duplicate product ID.")
        require(len(codes) == len(payload["stock_locations"]), "Duplicate stock location ID.")
        require(len(set(codes.values())) == len(codes), "Duplicate stock location code.")
        scope = {
            (row["product_id"], row["stock_location_id"]) for row in payload["inventory_scope"]
        }
        require(len(scope) == len(payload["inventory_scope"]), "Duplicate inventory position.")
        require(
            all(p in units and location in codes for p, location in scope),
            "Scope references unknown masters.",
        )
        opening_at = utc_timestamp(payload["opening_at"])
        movements = tuple(InventoryMovement.from_record(row) for row in payload["movements"])
        for movement in movements:
            validate_movement(movement, units, scope)
        require(
            len({m.inventory_event_id for m in movements}) == len(movements),
            "Duplicate inventory event ID.",
        )
        require(
            len({m.ordering_key for m in movements}) == len(movements),
            "Duplicate timestamp/sequence.",
        )
        openings = [m for m in movements if m.movement_type == "opening_stock"]
        require(
            len(openings) == len(scope) and {m.position for m in openings} == scope,
            "Require exactly one opening movement per inventory position.",
        )
        require(
            all(utc_timestamp(m.occurred_at) == opening_at for m in openings),
            "Opening timestamp differs from declared opening_at.",
        )
        ordered = tuple(sorted(movements, key=lambda m: m.ordering_key))
        result = cls(
            ordered, tuple(sorted(scope)), tuple(sorted(codes.items())), transfer_pairs(ordered)
        )
        result._balances(ordered)
        # The fast query index is only used after this complete independent
        # validation. A manually constructed or dataclass-replaced ledger keeps
        # the original lazy filtering/replay and its exception semantics.
        object.__setattr__(result, "_payload_validated", True)
        return result

    def _balances(self, movements: tuple[InventoryMovement, ...]) -> dict[Position, int]:
        balances: dict[Position, int] = {}
        for movement in movements:
            position = movement.position
            if movement.movement_type == "opening_stock":
                require(position not in balances, "Opening cannot reset an existing position.")
                balances[position] = movement.quantity_delta
            else:
                require(position in balances, "Movement has no known preceding opening.")
                balances[position] += movement.quantity_delta
            require(balances[position] >= 0, "Inventory ledger would produce a negative balance.")
        return balances

    def known_movements(
        self, occurred_through: str, *, known_at: str | None = None
    ) -> tuple[InventoryMovement, ...]:
        happened = utc_timestamp(occurred_through)
        known = utc_timestamp(known_at) if known_at is not None else None
        return tuple(
            m
            for m in self.movements
            if m.occurred_time <= happened and (known is None or m.available_time <= known)
        )

    def balances_at(
        self, occurred_through: str, *, known_at: str | None = None
    ) -> list[dict[str, Any]]:
        """Return physical balances or only the facts available at a knowledge cutoff."""
        happened = utc_timestamp(occurred_through)
        known = utc_timestamp(known_at) if known_at is not None else None
        balances: dict[Position, int] = {}
        if getattr(self, "_payload_validated", False):
            for position, index in self._position_index.items():
                supported, quantity = index.balance(happened, known)
                if not supported:
                    # Preserve exact native filtering, ordering and errors
                    # whenever late availability breaks a physical prefix.
                    balances = self._balances(
                        self.known_movements(occurred_through, known_at=known_at)
                    )
                    break
                if quantity is not None:
                    balances[position] = quantity
        else:
            balances = self._balances(self.known_movements(occurred_through, known_at=known_at))
        return [
            {
                "product_id": product,
                "stock_location_id": location,
                "on_hand": balances.get((product, location)),
                "reserved_qty": 0 if (product, location) in balances else None,
                "available_qty": balances.get((product, location)),
                "status": "known" if (product, location) in balances else "not_available",
            }
            for product, location in self.scope
        ]

    def transit_at(
        self, occurred_through: str, *, known_at: str | None = None
    ) -> list[dict[str, Any]]:
        visible = {
            m.inventory_event_id for m in self.known_movements(occurred_through, known_at=known_at)
        }
        return [
            {
                "transfer_id": outbound.transfer_id,
                "product_id": outbound.product_id,
                "source_stock_location_id": outbound.stock_location_id,
                "destination_stock_location_id": inbound.stock_location_id,
                "quantity": -outbound.quantity_delta,
                "unit_of_measure": outbound.unit_of_measure,
            }
            for outbound, inbound in self.transfers
            if outbound.inventory_event_id in visible and inbound.inventory_event_id not in visible
        ]
