"""Private physical inventory episodes and mature diagnostic windows, never features."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

from data.generator.common import deterministic_uuid
from data.inventory.contract import require, utc_timestamp
from data.inventory.projection_contract import PROJECTION_VERSION

if TYPE_CHECKING:
    from data.inventory.ledger import InventoryLedger
    from data.inventory.projection_contract import ProjectionConfig


def elapsed_microseconds(delta: timedelta) -> int:
    return (delta.days * 86400 + delta.seconds) * 1000000 + delta.microseconds


def stockout_episodes(
    ledger: InventoryLedger,
    config: ProjectionConfig,
    outcomes: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    end = utc_timestamp(config.end_at)
    delay = timedelta(seconds=config.truth_delay_seconds)
    episodes: list[dict[str, Any]] = []
    for position in ledger.scope:
        quantity = 0
        active: dict[str, Any] | None = None
        for movement in (m for m in ledger.movements if m.position == position):
            quantity += movement.quantity_delta
            if quantity == 0 and active is None:
                active = {
                    "episode_id": deterministic_uuid(
                        "stockout_episode", f"{PROJECTION_VERSION}:{movement.inventory_event_id}"
                    ),
                    "product_id": position[0],
                    "stock_location_id": position[1],
                    "unit_of_measure": movement.unit_of_measure,
                    "start_at": movement.occurred_at,
                    "start_sequence": movement.sequence,
                    "start_event_id": movement.inventory_event_id,
                    "start_available_at": movement.available_at,
                    "onset_kind": "opening_zero"
                    if movement.movement_type == "opening_stock"
                    else "depleted_by_movement",
                    "left_censored": movement.movement_type == "opening_stock",
                }
            elif quantity > 0 and active is not None:
                episodes.append(
                    {
                        **active,
                        "end_at": movement.occurred_at,
                        "end_sequence": movement.sequence,
                        "end_event_id": movement.inventory_event_id,
                        "end_available_at": movement.available_at,
                    }
                )
                active = None
        if active is not None:
            episodes.append(
                {
                    **active,
                    "end_at": None,
                    "end_sequence": None,
                    "end_event_id": None,
                    "end_available_at": None,
                }
            )
    episodes.sort(key=lambda r: (r["start_at"], r["start_sequence"], r["episode_id"]))
    impacts = []
    for episode in episodes:
        start_key = utc_timestamp(episode["start_at"]), episode["start_sequence"]
        end_key = (
            (utc_timestamp(episode["end_at"]), episode["end_sequence"])
            if episode["end_at"] is not None
            else (end, -1)
        )
        affected = [
            r
            for r in outcomes
            if (r["product_id"], r["stock_location_id"])
            == (episode["product_id"], episode["stock_location_id"])
            and start_key <= (utc_timestamp(r["occurred_at"]), r["sequence"]) < end_key
            and r["lost_sales_quantity"] > 0
        ]
        for row in affected:
            impacts.append(
                {
                    "episode_id": episode["episode_id"],
                    **{
                        f: row[f]
                        for f in (
                            "demand_id",
                            "product_id",
                            "stock_location_id",
                            "selling_location_id",
                            "channel",
                            "occurred_at",
                            "sequence",
                            "lost_sales_quantity",
                        )
                    },
                }
            )
        close = utc_timestamp(episode["end_at"]) if episode["end_at"] is not None else end
        availability = max(
            utc_timestamp(episode["start_available_at"]),
            close + delay,
            utc_timestamp(episode["end_available_at"])
            if episode["end_available_at"] is not None
            else close,
            *(
                utc_timestamp(m.available_at)
                for m in ledger.movements
                if m.position == (episode["product_id"], episode["stock_location_id"])
                and m.ordering_key <= end_key
            ),
        )
        episode.update(
            observed_through_exclusive_at=end.isoformat(),
            duration_microseconds=elapsed_microseconds(close - start_key[0]),
            right_censored=episode["end_at"] is None,
            diagnostic_available_at=availability.isoformat(),
            lost_sales_quantity=sum(r["lost_sales_quantity"] for r in affected),
            affected_demand_count=len(affected),
        )
    impacts.sort(key=lambda r: (r["occurred_at"], r["sequence"], r["demand_id"]))
    return episodes, impacts


def diagnose_windows(
    ledger: InventoryLedger,
    config: ProjectionConfig,
    episodes: list[dict[str, Any]],
    *,
    origin: str,
    evaluated_at: str,
) -> list[dict[str, Any]]:
    stamp, evaluation = utc_timestamp(origin), utc_timestamp(evaluated_at)
    require(
        utc_timestamp(config.start_at) <= stamp < utc_timestamp(config.end_at),
        "Diagnostic origin outside observation window.",
    )
    require(evaluation >= stamp, "Diagnostic evaluation precedes origin.")
    finish = stamp + timedelta(days=config.diagnostic_horizon_days)
    known = ledger.balances_at(stamp.isoformat(), known_at=stamp.isoformat())
    rows = []
    for balance in known:
        position = balance["product_id"], balance["stock_location_id"]
        movements = [
            m
            for m in ledger.movements
            if m.position == position and utc_timestamp(m.occurred_at) <= finish
        ]
        status, reason, incident, available = "not_evaluable", None, None, None
        if balance["on_hand"] is None:
            reason = "inventory_unknown"
        elif any(
            utc_timestamp(m.occurred_at) <= stamp < utc_timestamp(m.available_at) for m in movements
        ):
            reason = "origin_state_unavailable"
        elif balance["available_qty"] == 0:
            status = "already_stockout"
        elif finish >= utc_timestamp(config.end_at):
            reason = "incomplete_window"
        else:
            available = max(
                finish + timedelta(seconds=config.truth_delay_seconds),
                *(utc_timestamp(m.available_at) for m in movements),
            )
            if evaluation < available:
                reason = "outcomes_not_available"
            else:
                status = "evaluable"
                incident = int(
                    any(
                        (e["product_id"], e["stock_location_id"]) == position
                        and stamp < utc_timestamp(e["start_at"]) <= finish
                        for e in episodes
                    )
                )
        rows.append(
            {
                "product_id": position[0],
                "stock_location_id": position[1],
                "origin": stamp.isoformat(),
                "window_end_at": finish.isoformat(),
                "evaluated_at": evaluation.isoformat(),
                "status": status,
                "reason": reason,
                "incident_stockout": incident,
                "label_available_at": available.isoformat() if available is not None else None,
            }
        )
    return rows
