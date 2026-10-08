"""Immutable position prefixes; irregular knowledge order keeps native replay."""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from itertools import pairwise
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from data.inventory.ledger import InventoryMovement


@dataclass(frozen=True)
class PositionIndex:
    movements: tuple[InventoryMovement, ...]
    occurred: tuple[datetime, ...]
    available: tuple[datetime, ...]
    quantities: tuple[int, ...]
    physical_ordered: bool
    knowledge_ordered: bool
    invalid_from: int | None

    @classmethod
    def build(cls, movements: tuple[InventoryMovement, ...]) -> PositionIndex:
        occurred = tuple(m.occurred_time for m in movements)
        available = tuple(m.available_time for m in movements)
        quantities = [0]
        opened = False
        invalid_from = None
        for index, movement in enumerate(movements, 1):
            invalid = False
            if movement.movement_type == "opening_stock":
                invalid = opened
                opened = True
                quantity = movement.quantity_delta
            else:
                invalid = not opened
                quantity = quantities[-1] + movement.quantity_delta
            invalid = invalid or quantity < 0
            if invalid and invalid_from is None:
                invalid_from = index
            quantities.append(quantity)
        return cls(
            movements,
            occurred,
            available,
            tuple(quantities),
            all(a <= b for a, b in pairwise(occurred)),
            all(a <= b for a, b in pairwise(available)),
            invalid_from,
        )

    def balance(self, happened: datetime, known: datetime | None) -> tuple[bool, int | None]:
        """Return replay support and the quantity, or None for an unknown opening."""
        if not self.physical_ordered or (known is not None and not self.knowledge_ordered):
            return False, None
        count = bisect_right(self.occurred, happened)
        if known is not None:
            count = min(count, bisect_right(self.available, known))
        if self.invalid_from is not None and count >= self.invalid_from:
            return False, None
        return True, self.quantities[count] if count else None

    def physical_period(self, start: datetime, end: datetime) -> tuple[int, int, int] | None:
        """Return preceding, opening and closing sums for a validated physical prefix."""
        if not self.physical_ordered or self.invalid_from is not None:
            return None
        first = self.movements[0] if self.movements else None
        opening = (
            first.quantity_delta if first is not None and start <= first.occurred_time < end else 0
        )
        return (
            self.quantities[bisect_left(self.occurred, start)],
            opening,
            self.quantities[bisect_left(self.occurred, end)],
        )
