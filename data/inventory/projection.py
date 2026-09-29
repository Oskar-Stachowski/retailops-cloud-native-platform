from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from data.generator.common import deterministic_uuid
from data.inventory.contract import require, utc_timestamp
from data.inventory.ledger import InventoryLedger
from data.inventory.projection_contract import (
    PROJECTION_VERSION,
    ProjectionConfig,
    ProjectionOutput,
)
from data.inventory.simulation_reconciliation import reconcile_simulation, verify_demand_outcomes
from data.inventory.snapshots import daily_snapshots, day_periods
from data.inventory.stockout import diagnose_windows, elapsed_microseconds, stockout_episodes

if TYPE_CHECKING:
    from data.inventory.ledger import Position


def validate_window(ledger: InventoryLedger, config: ProjectionConfig) -> None:
    start, end = utc_timestamp(config.start_at), utc_timestamp(config.end_at)
    require(
        all(start <= m.occurred_time < end for m in ledger.movements),
        "Ledger outside projection observation window.",
    )
    require(
        all(
            m.occurred_time == start for m in ledger.movements if m.movement_type == "opening_stock"
        ),
        "Projection start differs from opening.",
    )


def physical_daily_balances(
    ledger: InventoryLedger, config: ProjectionConfig
) -> list[dict[str, Any]]:
    rows = []
    by_position = defaultdict(list)
    for movement in ledger.movements:
        by_position[movement.position].append(movement)
    for midnight, start, end in day_periods(config):
        for product, location in ledger.scope:
            movements = by_position[product, location]
            preceding = sum(m.quantity_delta for m in movements if m.occurred_time < start)
            included = [m for m in movements if start <= m.occurred_time < end]
            opening = sum(m.quantity_delta for m in included if m.movement_type == "opening_stock")
            delta = sum(m.quantity_delta for m in included if m.movement_type != "opening_stock")
            rows.append(
                {
                    "product_id": product,
                    "stock_location_id": location,
                    "business_date": midnight.date().isoformat(),
                    "snapshot_at": (end - timedelta(microseconds=1)).isoformat(),
                    "balance_before_period": preceding,
                    "opening_quantity": opening,
                    "movement_delta": delta,
                    "closing_quantity": preceding + opening + delta,
                    "reserved_qty": 0,
                    "available_qty": preceding + opening + delta,
                }
            )
    return rows


def project_inventory(
    operational: dict[str, Any],
    truth: dict[str, Any],
    config: ProjectionConfig,
    *,
    evaluated_at: str,
) -> dict[str, Any]:
    reconcile_simulation(operational)
    verify_demand_outcomes(operational, truth)
    ledger = InventoryLedger.from_payload(operational["ledger"])
    validate_window(ledger, config)
    evaluation = utc_timestamp(evaluated_at)
    require(
        evaluation >= utc_timestamp(config.end_at),
        "Projection evaluation must reach observation end.",
    )
    require(
        all(
            utc_timestamp(config.start_at)
            <= utc_timestamp(r["occurred_at"])
            < utc_timestamp(config.end_at)
            for r in truth["demand_outcomes"]
        ),
        "Demand outcome outside projection window.",
    )
    snapshots = daily_snapshots(ledger, config)
    episodes, impacts = stockout_episodes(ledger, config, truth["demand_outcomes"])
    diagnostics = []
    for origin in sorted({r["snapshot_at"] for r in snapshots}):
        diagnostics.extend(
            diagnose_windows(
                ledger, config, episodes, origin=origin, evaluated_at=evaluation.isoformat()
            )
        )
    output = {
        "contract_version": PROJECTION_VERSION,
        "configuration": config.model_dump(),
        "operational": snapshots,
        "simulation_truth": {
            "data_class": "simulation_truth",
            "physical_daily_balances": physical_daily_balances(ledger, config),
            "stockout_episodes": episodes,
            "lost_sales_impacts": impacts,
            "window_diagnostics": diagnostics,
        },
    }
    reconcile_projection(output, operational, truth)
    return output


def _reconcile_daily(
    output: dict[str, Any],
    ledger: InventoryLedger,
    config: ProjectionConfig,
) -> None:
    periods = {day.date().isoformat(): (day, start, end) for day, start, end in day_periods(config)}
    expected = {(day, *position) for day in periods for position in ledger.scope}
    snapshots = output["operational"]
    physical = output["simulation_truth"]["physical_daily_balances"]
    by_position = defaultdict(list)
    for movement in ledger.movements:
        by_position[movement.position].append(movement)
    for rows in (snapshots, physical):
        keys = [(r["business_date"], r["product_id"], r["stock_location_id"]) for r in rows]
        require(
            len(set(keys)) == len(keys) and set(keys) == expected,
            "Missing/duplicate/extra daily inventory grain.",
        )
    for row in snapshots:
        midnight, start, end = periods[row["business_date"]]
        cutoff = end - timedelta(microseconds=1)
        require(
            utc_timestamp(row["snapshot_at"]) == utc_timestamp(row["as_of_time"]) == cutoff
            and utc_timestamp(row["period_from_at"]) == start
            and utc_timestamp(row["period_to_at"]) == end
            and row["is_full_business_day"]
            == (start == midnight and end == midnight + timedelta(days=1)),
            "Wrong snapshot period or cutoff.",
        )
        visible = [
            m
            for m in by_position[row["product_id"], row["stock_location_id"]]
            if m.occurred_time <= cutoff and m.available_time <= cutoff
        ]
        known = any(m.movement_type == "opening_stock" for m in visible)
        quantity = sum(m.quantity_delta for m in visible) if known else None
        require(
            (row["on_hand"], row["reserved_qty"], row["available_qty"], row["status"])
            == (quantity, 0 if known else None, quantity, "known" if known else "not_available"),
            "Snapshot differs from known ledger balance.",
        )
        require(
            row["movement_count"] == len(visible)
            and row["last_inventory_event_id"]
            == (visible[-1].inventory_event_id if visible else None)
            and row["source_available_at"]
            == (max(m.available_time for m in visible).isoformat() if visible else None),
            "Snapshot source lineage is inconsistent.",
        )
        require(
            row["unit_of_measure"]
            == next(
                m.unit_of_measure for m in ledger.movements if m.product_id == row["product_id"]
            ),
            "Snapshot unit mismatch.",
        )
        require(
            row["snapshot_id"]
            == deterministic_uuid(
                "inventory_snapshot",
                f"{PROJECTION_VERSION}:{row['product_id']}:{row['stock_location_id']}:{cutoff.isoformat()}:{cutoff.isoformat()}",
            ),
            "Snapshot identity mismatch.",
        )
    for row in physical:
        _day, start, end = periods[row["business_date"]]
        movements = by_position[row["product_id"], row["stock_location_id"]]
        closing = sum(m.quantity_delta for m in movements if m.occurred_time < end)
        preceding = sum(m.quantity_delta for m in movements if m.occurred_time < start)
        opening = sum(
            m.quantity_delta
            for m in movements
            if m.movement_type == "opening_stock" and start <= m.occurred_time < end
        )
        require(
            utc_timestamp(row["snapshot_at"]) == end - timedelta(microseconds=1)
            and (
                row["balance_before_period"],
                row["opening_quantity"],
                row["movement_delta"],
                row["closing_quantity"],
                row["reserved_qty"],
                row["available_qty"],
            )
            == (preceding, opening, closing - preceding - opening, closing, 0, closing),
            "Physical daily balance does not reconcile.",
        )


def reconcile_projection(
    output: dict[str, Any],
    operational: dict[str, Any],
    truth: dict[str, Any],
) -> dict[str, int]:
    """Check every emitted grain against prefix sums and physical zero transitions."""
    ProjectionOutput.model_validate(output)
    config = ProjectionConfig.from_payload(output["configuration"])
    reconcile_simulation(operational)
    demand = verify_demand_outcomes(operational, truth)
    ledger = InventoryLedger.from_payload(operational["ledger"])
    validate_window(ledger, config)
    _reconcile_daily(output, ledger, config)
    snapshots = output["operational"]
    physical = output["simulation_truth"]["physical_daily_balances"]
    episodes = output["simulation_truth"]["stockout_episodes"]
    events = {m.inventory_event_id: m for m in ledger.movements}
    zero_starts = set()
    quantities: dict[Position, int] = {}
    for m in ledger.movements:
        before = quantities.get(m.position)
        quantities[m.position] = (before or 0) + m.quantity_delta
        if quantities[m.position] == 0 and (before is None or before > 0):
            zero_starts.add(m.inventory_event_id)
    require(
        len({e["episode_id"] for e in episodes}) == len(episodes)
        and len({e["start_event_id"] for e in episodes}) == len(episodes)
        and {e["start_event_id"] for e in episodes} == zero_starts,
        "Episodes do not cover physical zero transitions exactly once.",
    )
    for episode in episodes:
        onset = events[episode["start_event_id"]]
        later = [
            m
            for m in ledger.movements
            if m.position == onset.position and m.ordering_key > onset.ordering_key
        ]
        recovery = next((m for m in later if m.quantity_delta > 0), None)
        end_key = recovery.ordering_key if recovery else (utc_timestamp(config.end_at), -1)
        close = end_key[0]
        maturity = max(
            close + timedelta(seconds=config.truth_delay_seconds),
            *(
                m.available_time
                for m in ledger.movements
                if m.position == onset.position and m.ordering_key <= end_key
            ),
        )
        require(
            (
                episode["product_id"],
                episode["stock_location_id"],
                episode["unit_of_measure"],
                utc_timestamp(episode["start_at"]),
                episode["start_sequence"],
                utc_timestamp(episode["start_available_at"]),
            )
            == (
                *onset.position,
                onset.unit_of_measure,
                *onset.ordering_key,
                utc_timestamp(onset.available_at),
            ),
            "Episode onset is not the zero-producing movement.",
        )
        require(
            (
                episode["end_at"],
                episode["end_sequence"],
                episode["end_event_id"],
                episode["end_available_at"],
            )
            == (
                recovery.occurred_at,
                recovery.sequence,
                recovery.inventory_event_id,
                recovery.available_at,
            )
            if recovery
            else (
                episode["end_at"],
                episode["end_sequence"],
                episode["end_event_id"],
                episode["end_available_at"],
            )
            == (None, None, None, None),
            "Episode does not end at first positive recovery.",
        )
        opening = onset.movement_type == "opening_stock"
        require(
            episode["episode_id"]
            == deterministic_uuid(
                "stockout_episode", f"{PROJECTION_VERSION}:{onset.inventory_event_id}"
            )
            and episode["onset_kind"] == ("opening_zero" if opening else "depleted_by_movement")
            and episode["left_censored"] == opening
            and episode["right_censored"] == (recovery is None)
            and episode["duration_microseconds"]
            == elapsed_microseconds(close - onset.ordering_key[0])
            and utc_timestamp(episode["observed_through_exclusive_at"])
            == utc_timestamp(config.end_at)
            and utc_timestamp(episode["diagnostic_available_at"]) == maturity,
            "Episode duration, censoring or maturity is inconsistent.",
        )
    impacts = output["simulation_truth"]["lost_sales_impacts"]
    losses = {r["demand_id"]: r for r in truth["demand_outcomes"] if r["lost_sales_quantity"] > 0}
    require(
        len({r["demand_id"] for r in impacts}) == len(impacts)
        and {r["demand_id"] for r in impacts} == set(losses),
        "Lost demand is missing, duplicated or invented.",
    )
    episode_by_id = {e["episode_id"]: e for e in episodes}
    for row in impacts:
        require(row["episode_id"] in episode_by_id, "Unknown stockout episode for lost demand.")
        require(
            all(row[f] == losses[row["demand_id"]][f] for f in row if f != "episode_id"),
            "Lost-sales impact differs from demand outcome.",
        )
        episode = episode_by_id[row["episode_id"]]
        lower = utc_timestamp(episode["start_at"]), episode["start_sequence"]
        upper = (
            (utc_timestamp(episode["end_at"]), episode["end_sequence"])
            if episode["end_at"]
            else (utc_timestamp(config.end_at), -1)
        )
        require(
            (row["product_id"], row["stock_location_id"])
            == (episode["product_id"], episode["stock_location_id"])
            and lower <= (utc_timestamp(row["occurred_at"]), row["sequence"]) < upper,
            "Lost demand lies outside its physical zero episode.",
        )
    for episode in episodes:
        members = [r for r in impacts if r["episode_id"] == episode["episode_id"]]
        require(
            episode["lost_sales_quantity"] == sum(r["lost_sales_quantity"] for r in members)
            and episode["affected_demand_count"] == len(members),
            "Episode lost-sales aggregation differs from impacts.",
        )
    diagnostics = output["simulation_truth"]["window_diagnostics"]
    keys = [(r["origin"], r["product_id"], r["stock_location_id"]) for r in diagnostics]
    require(
        len(set(keys)) == len(keys)
        and set(keys)
        == {(r["snapshot_at"], r["product_id"], r["stock_location_id"]) for r in snapshots},
        "Missing/duplicate diagnostic origin grain.",
    )
    expected_windows = {}
    for origin, evaluation in {(r["origin"], r["evaluated_at"]) for r in diagnostics}:
        expected_windows[origin, evaluation] = {
            (r["product_id"], r["stock_location_id"]): r
            for r in diagnose_windows(
                ledger, config, episodes, origin=origin, evaluated_at=evaluation
            )
        }
    for row in diagnostics:
        expected_row = expected_windows[row["origin"], row["evaluated_at"]][
            row["product_id"], row["stock_location_id"]
        ]
        require(row == expected_row, "Window diagnostic ignores eligibility or maturity.")
    return {
        "snapshots": len(snapshots),
        "physical_daily_balances": len(physical),
        "stockout_episodes": len(episodes),
        "right_censored_episodes": sum(e["right_censored"] for e in episodes),
        "lost_sales_impacts": len(impacts),
        "lost_sales_quantity": demand["lost_sales_quantity"],
        "window_diagnostics": len(diagnostics),
    }
