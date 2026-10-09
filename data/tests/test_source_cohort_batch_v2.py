"""Exact source/review parity and ledger invariant coverage for cached execution."""

from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
import gc
import json
from pathlib import Path
import weakref

import pytest

from data.generator.common import deterministic_uuid
from data.generator.configuration import resolve_generation_config
from data.generator.identity import canonical_json
from data.generator.main import build_dataset
from data.inventory.contract import utc_timestamp
from data.inventory.ledger import InventoryMovement
from data.inventory.source_cohort_batch_v2 import (
    CachedLedgerSourceCommerceSimulator,
    build_source_dataset_fast,
    run,
)
from data.inventory.source_commerce import SourceCommerceSimulator
from data.inventory.source_dataset_contract import SOURCE_TABLES, csv_path
from data.inventory.source_dataset_io import (
    normalize_source,
    read_source_dataset,
    write_source_dataset,
)
from data.inventory.source_foundation import source_foundation
from data.tests.test_source_cohort_batch import parity_sample


@pytest.fixture(scope="module")
def cached_sample(parity_sample):
    tables, context = build_source_dataset_fast(
        parity_sample["generation"], parity_sample["config"]
    )
    return normalize_source(tables), context


def test_all_58_tables_and_csv_bytes_equal_ordinary_path(parity_sample, cached_sample, tmp_path):
    tables, context = cached_sample
    assert tables == parity_sample["ordinary"]
    assert context == parity_sample["ordinary_context"]
    paths = []
    for name, records, ctx in (
        ("ordinary", parity_sample["ordinary"], parity_sample["ordinary_context"]),
        ("cached", tables, context),
    ):
        paths.append(
            write_source_dataset(
                records, ctx, parity_sample["generation"], parity_sample["config"], tmp_path / name
            )
        )
    restored, manifest = read_source_dataset(paths[1])
    assert restored == parity_sample["ordinary"]
    assert manifest["facts_ready"] is True
    for name in SOURCE_TABLES:
        assert (paths[0] / csv_path(name)).read_bytes() == (paths[1] / csv_path(name)).read_bytes()
    report = json.loads((paths[1] / "source_report.json").read_text())
    assert len(report["checks"]) == 36
    assert all(r["status"] == "passed" for r in report["checks"])


def test_published_runner_releases_build_state_and_fully_revalidates(parity_sample, tmp_path):
    stages = []
    result = run(parity_sample["generation"], tmp_path / "cohort", on_stage=stages.append)
    restored, manifest = read_source_dataset(Path(result["directory"]))
    assert restored == parity_sample["ordinary"]
    assert manifest["descriptor"]["context"] == parity_sample["ordinary_context"].model_dump()
    assert result["status"] == "passed" and result["table_count"] == 58
    assert [stage["stage"] for stage in stages] == [
        "source_build_started",
        "source_built",
        "source_written_and_staging_verified",
        "published_source_verified",
    ]


@pytest.mark.parametrize("seed", [42, 137, 2026])
def test_cached_native_source_matches_complete_copy_and_detaches_consumed_inputs(seed, monkeypatch):
    from data.generator.configuration import DatasetGenerationConfig
    from data.inventory import source_cohort_batch_v2 as cached
    from data.inventory.run_source_dataset import default_inventory_config

    generation = DatasetGenerationConfig(
        profile="ai-load", days=45, products=2, stores=1, warehouses=1,
        seed=seed, forecast_plan_days=14, max_daily_rows=90,
    )
    candidate = build_dataset(generation)
    original = deepcopy(candidate)
    effective = resolve_generation_config(generation)
    config = default_inventory_config(generation)
    actual = cached.simulate_source_commerce_fast(candidate, effective, config)
    assert candidate == original
    monkeypatch.setattr(cached, "_copy_commerce_inputs", deepcopy)
    expected = cached.simulate_source_commerce_fast(candidate, effective, config)
    assert actual == expected and candidate == original
    actual["commerce"]["product_catalog"][0]["name"] = "changed output only"
    assert candidate == original


def test_cached_native_orchestration_does_not_copy_unconsumed_candidate_outputs():
    from data.generator.configuration import DatasetGenerationConfig
    from data.inventory import source_cohort_batch_v2 as cached
    from data.inventory.run_source_dataset import default_inventory_config

    class Unused:
        def __deepcopy__(self, memo):
            raise AssertionError("Cached source copied an unused candidate table")

    generation = DatasetGenerationConfig(
        profile="ai-load", days=45, products=2, stores=1, warehouses=1, seed=42,
        max_daily_rows=90,
    )
    candidate = build_dataset(generation)
    candidate["unrelated_private_output"] = Unused()
    result = cached.simulate_source_commerce_fast(
        candidate, resolve_generation_config(generation), default_inventory_config(generation)
    )
    assert "unrelated_private_output" not in result["commerce"]


@pytest.fixture
def simulators(parity_sample):
    generation = parity_sample["generation"]
    effective = resolve_generation_config(generation)
    candidate = build_dataset(generation)
    inputs = source_foundation(candidate, effective, parity_sample["config"])
    return [
        cls(inputs, deepcopy(candidate), effective, parity_sample["config"])
        for cls in (SourceCommerceSimulator, CachedLedgerSourceCommerceSimulator)
    ]


def test_ledger_state_matches_after_every_review_and_final_execution(simulators):
    outputs, reviews = [], []
    for simulator in simulators:
        capture = []
        original = simulator._review

        def review(stamp, original=original, capture=capture, simulator=simulator):
            original(stamp)
            ledger = simulator._ledger()
            capture.append(
                canonical_json(
                    {
                        "review": simulator.reviews[-1],
                        "movements": [m.record() for m in ledger.movements],
                        "balances": sorted(
                            (list(k), v) for k, v in ledger._balances(ledger.movements).items()
                        ),
                    }
                )
            )

        simulator._review = review
        outputs.append(simulator.execute())
        reviews.append(capture)
    assert outputs[0] == outputs[1]
    assert reviews[0] and reviews[0] == reviews[1]


def test_complete_event_heap_releases_consumed_typed_rows_without_changing_outputs(simulators):
    ordinary, cached = simulators
    physical_kinds = {"demand", "return", "action"}

    def events(simulator):
        return sorted(
            (stamp, phase, sequence, kind, row.model_dump())
            for stamp, phase, sequence, kind, row in simulator.queue
            if kind in physical_kinds
        )

    # Every validated physical row, timestamp and sequence is still in the heap.
    assert events(cached) == events(ordinary)
    assert cached.scenario.settings == ordinary.scenario.settings
    assert cached.scenario.selling_locations == ordinary.scenario.selling_locations
    assert cached.scenario.fulfillment_routes == ordinary.scenario.fulfillment_routes
    assert not cached.scenario.demand_arrivals
    assert not cached.scenario.return_events
    assert not cached.scenario.inventory_actions
    refs = [
        [weakref.ref(row) for _, _, _, kind, row in simulator.queue if kind in physical_kinds]
        for simulator in simulators
    ]
    assert refs[0] and len(refs[0]) == len(refs[1])
    assert all(ref() is not None for ref in refs[1])

    released_during_reviews = []
    original_review = cached._review

    def review(stamp):
        original_review(stamp)
        gc.collect()
        released_during_reviews.append(sum(ref() is None for ref in refs[1]))

    cached._review = review
    expected = ordinary.execute()
    actual = cached.execute()
    gc.collect()
    assert actual == expected
    assert released_during_reviews and max(released_during_reviews) > 0
    assert all(ref() is None for ref in refs[1])
    assert all(ref() is not None for ref in refs[0])


@pytest.mark.parametrize("change", ["unknown_product", "duplicate_time_sequence", "outside_window"])
def test_scenario_events_are_fully_validated_before_releasing_lists(parity_sample, change):
    generation = resolve_generation_config(parity_sample["generation"])
    config = parity_sample["config"]
    candidate = build_dataset(parity_sample["generation"])
    inputs = source_foundation(candidate, generation, config)
    demand = inputs["scenario"]["demand_arrivals"]
    if change == "unknown_product":
        demand[0]["product_id"] = deterministic_uuid("invalid-demand", "unknown-product")
    elif change == "duplicate_time_sequence":
        demand[1]["occurred_at"] = demand[0]["occurred_at"]
        demand[1]["sequence"] = demand[0]["sequence"]
    else:
        demand[0]["occurred_at"] = inputs["scenario"]["settings"]["end_at"]
    with pytest.raises(ValueError):
        CachedLedgerSourceCommerceSimulator(inputs, deepcopy(candidate), generation, config)


def test_pending_transfer_uses_destination_and_outbound_availability(simulators):
    ledgers = []
    for simulator in simulators:
        first = simulator.movements[0]
        other = next(
            m
            for m in simulator.movements
            if m.product_id == first.product_id and m.stock_location_id != first.stock_location_id
        )
        start = utc_timestamp(first.occurred_at)
        transfer_id = deterministic_uuid("cached-ledger-test", "transfer")
        out = {
            **first.record(),
            "inventory_event_id": deterministic_uuid("cached-ledger-test", "out"),
            "movement_type": "transfer_out",
            "source_process": "transfer",
            "transfer_id": transfer_id,
            "quantity_delta": -1,
            "occurred_at": (start + timedelta(hours=1)).isoformat(),
            "ingested_at": (start + timedelta(hours=1)).isoformat(),
            "available_at": (start + timedelta(hours=2)).isoformat(),
            "sequence": 1000,
        }
        inbound = InventoryMovement.from_record(
            {
                **out,
                "inventory_event_id": deterministic_uuid("cached-ledger-test", "in"),
                "stock_location_id": other.stock_location_id,
                "movement_type": "transfer_in",
                "quantity_delta": 1,
                "occurred_at": (start + timedelta(hours=2)).isoformat(),
                "ingested_at": (start + timedelta(hours=2)).isoformat(),
                "sequence": 1001,
            }
        )
        simulator.transfer_inbounds[transfer_id] = inbound
        simulator.availability[other.position] = start + timedelta(hours=3)
        simulator._apply(out)
        ledger = simulator._ledger()
        pending = next(
            m for m in ledger.movements if m.inventory_event_id == inbound.inventory_event_id
        )
        assert pending.available_time == start + timedelta(hours=3)
        assert inbound.inventory_event_id not in {m.inventory_event_id for m in simulator.movements}
        ledgers.append(ledger)
    assert ledgers[0] == ledgers[1]


@pytest.mark.parametrize(
    "change",
    ["duplicate_id", "duplicate_order", "negative_opening", "bad_identifier", "empty_reference"],
)
def test_untracked_malformed_record_replacements_are_revalidated(simulators, change):
    for simulator in simulators:
        first = simulator.movements[0]
        if change == "duplicate_id":
            simulator.movements.append(first)
        elif change == "duplicate_order":
            simulator.movements[1] = replace(simulator.movements[1], sequence=first.sequence)
        elif change == "negative_opening":
            simulator.movements[0] = replace(first, quantity_delta=-1)
        elif change == "bad_identifier":
            simulator.movements[0] = replace(first, inventory_event_id="not-a-uuid")
        else:
            simulator.movements[0] = replace(first, source_reference="")
        with pytest.raises(ValueError):
            simulator._ledger()


def test_cached_master_change_is_rejected(simulators):
    cached = simulators[1]
    cached.inventory_base["stock_locations"][0]["location_code"] = "changed"
    with pytest.raises(ValueError, match="master context changed"):
        cached._ledger()


def test_cached_validated_ledger_index_matches_original_at_all_initial_boundaries(simulators):
    ordinary, cached = (simulator._ledger() for simulator in simulators)
    assert getattr(cached, "_payload_validated", False)
    times = {
        utc_timestamp(value) + timedelta(microseconds=delta)
        for movement in ordinary.movements
        for value in (movement.occurred_at, movement.available_at)
        for delta in (-1, 0, 1)
    }
    for happened in sorted(times):
        for known in (None, *sorted(times)):
            cutoff = known.isoformat() if known is not None else None
            assert cached.balances_at(happened.isoformat(), known_at=cutoff) == ordinary.balances_at(
                happened.isoformat(), known_at=cutoff
            )
