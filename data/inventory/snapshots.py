"""Operational snapshot projection. This module never reads demand/supplier truth."""

from __future__ import annotations

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
