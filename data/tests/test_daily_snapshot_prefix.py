"""Compare every field and failure to daily replay, including late availability."""

import json
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest

from data.inventory import snapshots
from data.inventory.contract import utc_timestamp
from data.inventory.ledger import InventoryLedger
from data.inventory.projection_contract import ProjectionConfig
from data.inventory.simulator import ChronologicalSimulator


@pytest.fixture
def sample():
    fixtures = Path(__file__).parent / "fixtures"
    names = [
        "chronological-opening-v1.json",
        "reorder-supply-v1.json",
        "chronological-scenario-v1.json",
        "reorder-config-v1.json",
        "supplier-fulfillment-config-v1.json",
        "chronological-supplier-truth-v1.json",
    ]
    inputs = [json.loads((fixtures / name).read_bytes()) for name in names]
    parent = ChronologicalSimulator(*inputs).execute()
    ledger = InventoryLedger.from_payload(parent["operational"]["ledger"])
    config = ProjectionConfig.from_payload(
        json.loads((fixtures / "inventory-projection-config-v1.json").read_bytes())
    )
    return ledger, config


def outcome(function, ledger, config):
    try:
        return function(ledger, config)
    except ValueError as error:
        return type(error), str(error)


@pytest.mark.parametrize(
    "mode", ["normal", "late_day", "missing_position", "before_opening", "partial_day"]
)
def test_complete_snapshot_bytes_and_errors_match_replay(sample, mode):
    ledger, config = sample
    if mode == "late_day":
        rows = list(ledger.movements)
        rows[2] = replace(
            rows[2],
            available_at=(rows[2].available_time + timedelta(days=3)).isoformat(),
        )
        ledger = replace(ledger, movements=tuple(rows))
    elif mode == "missing_position":
        position = ledger.scope[0]
        later = (utc_timestamp(config.end_at) + timedelta(days=1)).isoformat()
        ledger = replace(
            ledger,
            movements=tuple(
                replace(m, available_at=later) if m.position == position else m
                for m in ledger.movements
            ),
        )
    elif mode == "before_opening":
        values = config.model_dump()
        values["start_at"] = (
            utc_timestamp(config.start_at) - timedelta(days=2)
        ).isoformat()
        config = ProjectionConfig.from_payload(values)
    elif mode == "partial_day":
        values = config.model_dump()
        values["end_at"] = (
            utc_timestamp(config.end_at) - timedelta(hours=7)
        ).isoformat()
        config = ProjectionConfig.from_payload(values)
    assert outcome(snapshots.daily_snapshots, ledger, config) == outcome(
        snapshots._daily_replayed_snapshots, ledger, config
    )


def test_same_day_visibility_reordering_keeps_chronological_prefix(sample, monkeypatch):
    ledger, config = sample
    # All availability stays in the event's business day even if event order differs.
    rows = tuple(
        replace(
            m,
            available_at=(
                m.occurred_time + timedelta(minutes=(20 if i % 2 else 40))
            ).isoformat(),
        )
        for i, m in enumerate(ledger.movements)
    )
    changed = replace(ledger, movements=rows)
    expected = outcome(snapshots._daily_replayed_snapshots, changed, config)

    def forbidden(*args):
        raise AssertionError("same-day ledger unnecessarily replayed every day")

    monkeypatch.setattr(snapshots, "_daily_replayed_snapshots", forbidden)
    assert outcome(snapshots.daily_snapshots, changed, config) == expected


def test_prefix_reads_each_position_once_per_movement(sample, monkeypatch):
    ledger, config = sample
    from data.inventory.ledger import InventoryMovement

    getter = InventoryMovement.position.fget
    calls = []

    def counted(movement):
        calls.append(movement.inventory_event_id)
        return getter(movement)

    monkeypatch.setattr(InventoryMovement, "position", property(counted))
    actual = snapshots.daily_snapshots(ledger, config)
    assert actual
    assert len(calls) == len(ledger.movements)
