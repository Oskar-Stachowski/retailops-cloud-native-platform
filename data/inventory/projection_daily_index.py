"""Coalesce native daily verification facts independently of production queries."""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from data.inventory.ledger import InventoryMovement


@dataclass(frozen=True, slots=True)
class DailyVerificationIndex:
    visible: tuple[tuple[int | None, int, str | None, datetime | None], ...]
    physical: tuple[tuple[int, int, int], ...]

    @classmethod
    def build(
        cls,
        movements: list[InventoryMovement],
        ends: tuple[datetime, ...],
        cutoffs: tuple[datetime, ...],
    ) -> DailyVerificationIndex:
        """Accumulate every validated movement at its first eligible daily cutoff."""
        size = len(ends)
        physical_delta = [0] * size
        physical_opening = [0] * size
        visible_delta = [0] * size
        visible_count = [0] * size
        visible_opening = [False] * size
        last_event = [-1] * size
        available: list[datetime | None] = [None] * size
        for order, movement in enumerate(movements):
            physical_day = bisect_right(ends, movement.occurred_time)
            if physical_day < size:
                physical_delta[physical_day] += movement.quantity_delta
                if movement.movement_type == "opening_stock":
                    physical_opening[physical_day] += movement.quantity_delta
            visible_day = bisect_left(cutoffs, max(movement.occurred_time, movement.available_time))
            if visible_day < size:
                visible_delta[visible_day] += movement.quantity_delta
                visible_count[visible_day] += 1
                visible_opening[visible_day] |= movement.movement_type == "opening_stock"
                last_event[visible_day] = max(last_event[visible_day], order)
                previous = available[visible_day]
                available[visible_day] = (
                    movement.available_time
                    if previous is None
                    else max(previous, movement.available_time)
                )
        physical = []
        visible = []
        physical_quantity = quantity = count = 0
        opened = False
        last = -1
        latest: datetime | None = None
        for day in range(size):
            preceding = physical_quantity
            physical_quantity += physical_delta[day]
            physical.append((preceding, physical_opening[day], physical_quantity))
            quantity += visible_delta[day]
            count += visible_count[day]
            opened |= visible_opening[day]
            last = max(last, last_event[day])
            next_available = available[day]
            if next_available is not None:
                latest = next_available if latest is None else max(latest, next_available)
            visible.append(
                (
                    quantity if opened else None,
                    count,
                    movements[last].inventory_event_id if last >= 0 else None,
                    latest,
                )
            )
        return cls(tuple(visible), tuple(physical))
