"""Indexed balances preserve the original independent replay at every cutoff."""

from __future__ import annotations

import copy
from datetime import timedelta

import pytest

import data.tests.test_inventory_projection as controls
from data.inventory.contract import utc_timestamp
from data.inventory.ledger import InventoryLedger, InventoryMovement
from data.inventory.projection_contract import ProjectionConfig
from data.inventory.projection_daily_index import DailyVerificationIndex
from data.inventory.snapshots import day_periods
from data.inventory.stockout import diagnose_windows

inputs = controls.inputs
config = controls.config


def reference(ledger, happened, known):
    balances = ledger._balances(ledger.known_movements(happened, known_at=known))
    return [
        {
            "product_id": product,
            "stock_location_id": location,
            "on_hand": balances.get((product, location)),
            "reserved_qty": 0 if (product, location) in balances else None,
            "available_qty": balances.get((product, location)),
            "status": "known" if (product, location) in balances else "not_available",
        }
        for product, location in ledger.scope
    ]


@pytest.mark.parametrize("availability", ["original", "immediate", "late_opening", "late_receipt"])
def test_all_physical_and_knowledge_boundaries_match_native_replay(inputs, availability):
    payload = payload_for(inputs, availability)
    ledger = InventoryLedger.from_payload(payload)
    times = {
        utc_timestamp(row[field]) + timedelta(microseconds=delta)
        for row in payload["movements"]
        for field in ("occurred_at", "available_at")
        for delta in (-1, 0, 1)
    }
    for happened in sorted(times):
        for known in (None, *sorted(times)):
            cutoff = known.isoformat() if known is not None else None
            try:
                expected = reference(ledger, happened.isoformat(), cutoff)
            except ValueError as error:
                with pytest.raises(ValueError) as actual:
                    ledger.balances_at(happened.isoformat(), known_at=cutoff)
                assert str(actual.value) == str(error)
            else:
                assert ledger.balances_at(happened.isoformat(), known_at=cutoff) == expected


def payload_for(inputs, availability):
    payload = copy.deepcopy(controls.simulate(inputs)["operational"]["ledger"])
    if availability == "immediate":
        for row in payload["movements"]:
            row["ingested_at"] = row["available_at"] = row["occurred_at"]
    elif availability == "late_opening":
        for row in payload["movements"]:
            if row["movement_type"] == "opening_stock":
                row["available_at"] = "2026-07-11T00:00:00Z"
    elif availability == "late_receipt":
        row = next(
            r
            for r in payload["movements"]
            if r["quantity_delta"] > 0 and r["movement_type"] != "opening_stock"
        )
        row["available_at"] = "2026-07-11T00:00:00Z"
    return payload


@pytest.mark.parametrize("availability", ["original", "immediate", "late_opening", "late_receipt"])
def test_independent_daily_index_matches_literal_movement_sums(inputs, config, availability):
    ledger = InventoryLedger.from_payload(payload_for(inputs, availability))
    periods = list(day_periods(ProjectionConfig.from_payload(config)))
    ends = tuple(end for _, _, end in periods)
    cutoffs = tuple(end - timedelta(microseconds=1) for end in ends)
    for position in ledger.scope:
        movements = [m for m in ledger.movements if m.position == position]
        actual = DailyVerificationIndex.build(movements, ends, cutoffs)
        for day, (_, start, end) in enumerate(periods):
            visible = [
                m
                for m in movements
                if m.occurred_time <= cutoffs[day] and m.available_time <= cutoffs[day]
            ]
            known = any(m.movement_type == "opening_stock" for m in visible)
            assert actual.visible[day] == (
                sum(m.quantity_delta for m in visible) if known else None,
                len(visible),
                visible[-1].inventory_event_id if visible else None,
                max((m.available_time for m in visible), default=None),
            )
            assert actual.physical[day] == (
                sum(m.quantity_delta for m in movements if m.occurred_time < start),
                sum(
                    m.quantity_delta
                    for m in movements
                    if m.movement_type == "opening_stock" and start <= m.occurred_time < end
                ),
                sum(m.quantity_delta for m in movements if m.occurred_time < end),
            )


def test_chronological_queries_and_windows_do_not_rescan_whole_ledger(inputs, config, monkeypatch):
    parent = controls.simulate(inputs)
    payload = copy.deepcopy(parent["operational"]["ledger"])
    for row in payload["movements"]:
        row["ingested_at"] = row["available_at"] = row["occurred_at"]
    ledger = InventoryLedger.from_payload(payload)
    counted = []
    original = InventoryMovement.position.fget

    def position(movement):
        counted.append(movement.inventory_event_id)
        return original(movement)

    def forbidden(*args, **kwargs):
        pytest.fail("chronological query rescanned the complete ledger")

    monkeypatch.setattr(InventoryMovement, "position", property(position))
    monkeypatch.setattr(InventoryLedger, "known_movements", forbidden)
    for day in range(1, 10):
        cutoff = f"2026-07-{day:02}T23:59:59.999999Z"
        ledger.balances_at(cutoff, known_at=cutoff)
        diagnose_windows(
            ledger,
            ProjectionConfig.from_payload(config),
            [],
            origin=cutoff,
            evaluated_at=controls.EVALUATION,
        )
    assert len(counted) == len(ledger.movements)


def test_replaced_ledger_does_not_reuse_validated_prefix_cache(inputs):
    from dataclasses import replace

    ledger = InventoryLedger.from_payload(controls.simulate(inputs)["operational"]["ledger"])
    cutoff = "2026-07-06T23:59:59.999999Z"
    ledger.balances_at(cutoff, known_at=cutoff)  # build original immutable cache
    replaced = replace(ledger, movements=ledger.movements)
    assert not getattr(replaced, "_payload_validated", False)
    assert replaced.balances_at(cutoff, known_at=cutoff) == reference(replaced, cutoff, cutoff)
