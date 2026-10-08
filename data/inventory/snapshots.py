"""Operational snapshot projection. This module never reads demand/supplier truth."""

from __future__ import annotations

from bisect import bisect_left
from collections import defaultdict
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from data.generator.common import deterministic_uuid
from data.inventory.contract import require, utc_timestamp
from data.inventory.projection_contract import PROJECTION_VERSION

if TYPE_CHECKING:
    from collections.abc import Iterator
    from datetime import datetime

    from data.inventory.ledger import InventoryLedger, InventoryMovement, Position
    from data.inventory.projection_contract import ProjectionConfig


def day_periods(config: ProjectionConfig) -> Iterator[tuple[datetime, datetime, datetime]]:
    start, end = utc_timestamp(config.start_at), utc_timestamp(config.end_at)
    midnight = start.replace(hour=0, minute=0, second=0, microsecond=0)
    while midnight < end:
        following = midnight + timedelta(days=1)
        yield midnight, max(start, midnight), min(end, following)
        midnight = following


def snapshot_at(
    ledger: InventoryLedger,
    *,
    snapshot_time: str,
    as_of_time: str,
) -> list[dict[str, Any]]:
    stamp, known = utc_timestamp(snapshot_time), utc_timestamp(as_of_time)
    require(known >= stamp, "Snapshot cannot be available before its business cutoff.")
    visible = ledger.known_movements(stamp.isoformat(), known_at=known.isoformat())
    balances = ledger.balances_at(stamp.isoformat(), known_at=known.isoformat())
    by_position: dict[Position, list[InventoryMovement]] = defaultdict(list)
    for movement in visible:
        by_position[movement.position].append(movement)
    result = []
    units = {m.product_id: m.unit_of_measure for m in ledger.movements}
    for position in balances:
        rows = by_position[position["product_id"], position["stock_location_id"]]
        result.append(
            {
                "snapshot_id": deterministic_uuid(
                    "inventory_snapshot",
                    f"{PROJECTION_VERSION}:{position['product_id']}:{position['stock_location_id']}:{stamp.isoformat()}:{known.isoformat()}",
                ),
                **position,
                "snapshot_at": stamp.isoformat(),
                "as_of_time": known.isoformat(),
                "unit_of_measure": units[position["product_id"]],
                "source_available_at": max(m.available_time for m in rows).isoformat()
                if rows
                else None,
                "last_inventory_event_id": rows[-1].inventory_event_id if rows else None,
                "movement_count": len(rows),
            }
        )
    return result


def daily_snapshots(ledger: InventoryLedger, config: ProjectionConfig) -> list[dict[str, Any]]:
    periods = list(day_periods(config))
    if not periods:
        return []
    cutoffs = [end - timedelta(microseconds=1) for _, _, end in periods]
    # A common source has availability in the same daily bucket as occurrence.
    # Its visible sets are chronological prefixes, so each movement can be
    # applied once. Late facts that change an earlier prefix retain the general
    # snapshot_at path and its exact validation/order semantics.
    previous = -1
    for movement in ledger.movements:
        slot = bisect_left(cutoffs, max(movement.occurred_time, movement.available_time))
        if slot < previous:
            return _daily_replayed_snapshots(ledger, config)
        previous = slot
    return _daily_prefix_snapshots(ledger, periods)


def _daily_replayed_snapshots(
    ledger: InventoryLedger, config: ProjectionConfig
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for midnight, start, end in day_periods(config):
        cutoff = end - timedelta(microseconds=1)
        rows.extend(
            {
                **row,
                "business_date": midnight.date().isoformat(),
                "period_from_at": start.isoformat(),
                "period_to_at": end.isoformat(),
                "is_full_business_day": start == midnight and end == midnight + timedelta(days=1),
            }
            for row in snapshot_at(
                ledger, snapshot_time=cutoff.isoformat(), as_of_time=cutoff.isoformat()
            )
        )
    return rows


def _daily_prefix_snapshots(
    ledger: InventoryLedger, periods: list[tuple[datetime, datetime, datetime]]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    balances: dict[Position, int] = {}
    counts: dict[Position, int] = defaultdict(int)
    last: dict[Position, str] = {}
    available: dict[Position, datetime] = {}
    units = {m.product_id: m.unit_of_measure for m in ledger.movements}
    movements = iter(ledger.movements)
    movement = next(movements, None)
    visible_at = max(movement.occurred_time, movement.available_time) if movement else None
    for midnight, start, end in periods:
        cutoff = end - timedelta(microseconds=1)
        stamp = cutoff.isoformat()
        while movement is not None and visible_at is not None and visible_at <= cutoff:
            position = movement.position
            if movement.movement_type == "opening_stock":
                require(position not in balances, "Opening cannot reset an existing position.")
                balances[position] = movement.quantity_delta
            else:
                require(position in balances, "Movement has no known preceding opening.")
                balances[position] += movement.quantity_delta
            require(balances[position] >= 0, "Inventory ledger would produce a negative balance.")
            counts[position] += 1
            last[position] = movement.inventory_event_id
            available[position] = max(
                available.get(position, movement.available_time), movement.available_time
            )
            movement = next(movements, None)
            visible_at = max(movement.occurred_time, movement.available_time) if movement else None
        for product, location in ledger.scope:
            position = product, location
            quantity = balances.get(position)
            rows.append(
                {
                    "snapshot_id": deterministic_uuid(
                        "inventory_snapshot",
                        f"{PROJECTION_VERSION}:{product}:{location}:{stamp}:{stamp}",
                    ),
                    "product_id": product,
                    "stock_location_id": location,
                    "on_hand": quantity,
                    "reserved_qty": 0 if position in balances else None,
                    "available_qty": quantity,
                    "status": "known" if position in balances else "not_available",
                    "snapshot_at": stamp,
                    "as_of_time": stamp,
                    "unit_of_measure": units[product],
                    "source_available_at": available[position].isoformat()
                    if position in available
                    else None,
                    "last_inventory_event_id": last.get(position),
                    "movement_count": counts[position],
                    "business_date": midnight.date().isoformat(),
                    "period_from_at": start.isoformat(),
                    "period_to_at": end.isoformat(),
                    "is_full_business_day": start == midnight
                    and end == midnight + timedelta(days=1),
                }
            )
    return rows
