"""Development-only parity for the additive indexed source execution path."""

from copy import deepcopy
from datetime import date
import json
from pathlib import Path
from time import perf_counter

import pytest

from data.generator.configuration import DatasetGenerationConfig, resolve_generation_config
from data.generator.common import deterministic_uuid
from data.generator.identity import canonical_json
from data.generator.main import build_dataset
from data.inventory.run_source_dataset import build_source_dataset, default_inventory_config
from data.inventory.source_cohort_batch import (
    IndexedSourceCommerceSimulator,
    UPSTREAM_SHA256,
    build_source_dataset_fast,
    implementation,
    run,
    verify_upstream_pins,
)
from data.inventory.source_commerce import SourceCommerceSimulator
from data.inventory.source_dataset_contract import SOURCE_TABLES, csv_path
from data.inventory.source_dataset_io import (
    normalize_source,
    read_source_dataset,
    write_source_dataset,
)
from data.inventory.source_foundation import source_foundation


@pytest.fixture(scope="module")
def parity_sample():
    generation = DatasetGenerationConfig(
        profile="ai-intermittent-v1",
        seed=710001,
        days=10,
        products=8,
        stores=2,
        warehouses=2,
        end_date=date(2026, 9, 30),
    )
    config = default_inventory_config(generation)
    start = perf_counter()
    ordinary, ordinary_context = build_source_dataset(generation, config)
    ordinary_seconds = perf_counter() - start
    start = perf_counter()
    indexed, indexed_context = build_source_dataset_fast(generation, config)
    indexed_seconds = perf_counter() - start
    return {
        "generation": generation,
        "config": config,
        "ordinary": normalize_source(ordinary),
        "indexed": normalize_source(indexed),
        "ordinary_context": ordinary_context,
        "indexed_context": indexed_context,
        "seconds": {"ordinary": ordinary_seconds, "indexed": indexed_seconds},
    }


def test_exact_all_source_tables_and_context(parity_sample):
    sample = parity_sample
    assert sample["ordinary_context"] == sample["indexed_context"]
    assert sample["ordinary"] == sample["indexed"]
    assert set(sample["indexed"]) == set(SOURCE_TABLES)
    assert len(sample["indexed"]) == 58
    for name in SOURCE_TABLES:
        assert canonical_json(sample["indexed"][name]) == canonical_json(sample["ordinary"][name])
    assert implementation()["rng_and_chronological_process"] == "unchanged"


def test_ordinary_source_writer_reader_and_bytes_are_identical(parity_sample, tmp_path):
    sample = parity_sample
    paths = {}
    for mode in ("ordinary", "indexed"):
        paths[mode] = write_source_dataset(
            sample[mode],
            sample[mode + "_context"],
            sample["generation"],
            sample["config"],
            tmp_path / mode,
        )
    restored, actual = read_source_dataset(paths["indexed"])
    assert restored == sample["ordinary"]
    assert paths["ordinary"].name == paths["indexed"].name
    for name in SOURCE_TABLES:
        relative = csv_path(name)
        assert (paths["ordinary"] / relative).read_bytes() == (
            paths["indexed"] / relative
        ).read_bytes()
    report = json.loads((paths["indexed"] / "source_report.json").read_text())
    assert actual["facts_ready"] is True
    assert len(report["checks"]) == 36
    assert all(row["status"] == "passed" for row in report["checks"])
    assert (paths["ordinary"] / "source_report.json").read_bytes() == (
        paths["indexed"] / "source_report.json"
    ).read_bytes()


@pytest.fixture
def simulators(parity_sample):
    generation = parity_sample["generation"]
    effective = resolve_generation_config(generation)
    config = parity_sample["config"]
    candidate = build_dataset(generation)
    inputs = source_foundation(candidate, effective, config)
    return [
        cls(inputs, deepcopy(candidate), effective, config)
        for cls in (SourceCommerceSimulator, IndexedSourceCommerceSimulator)
    ]


def test_same_duplicate_and_negative_balance_rejections_without_state_change(simulators):
    for simulator in simulators:
        before = (list(simulator.movements), dict(simulator.balances), dict(simulator.availability))
        initial = simulator.movements[0].record()
        with pytest.raises(ValueError, match="Duplicate generated inventory event ID"):
            simulator._apply(initial)
        negative = {
            **initial,
            "inventory_event_id": deterministic_uuid("source-fast-test", "negative"),
            "movement_type": "inventory_adjustment",
            "source_process": "adjustment",
            "quantity_delta": -100000,
        }
        with pytest.raises(ValueError, match="negative inventory balance"):
            simulator._apply(negative)
        assert before == (simulator.movements, simulator.balances, simulator.availability)
        if isinstance(simulator, IndexedSourceCommerceSimulator):
            assert negative["inventory_event_id"] not in simulator._movement_ids


def test_new_movement_is_indexed_and_second_application_is_rejected(simulators):
    results = []
    for simulator in simulators:
        record = {
            **simulator.movements[0].record(),
            "inventory_event_id": deterministic_uuid("source-fast-test", "positive"),
            "movement_type": "inventory_adjustment",
            "source_process": "adjustment",
            "quantity_delta": 1,
        }
        results.append(simulator._apply(record).record())
        with pytest.raises(ValueError, match="Duplicate generated inventory event ID"):
            simulator._apply(record)
    assert results[0] == results[1]
    assert simulators[0].movements == simulators[1].movements


def test_upstream_code_pin_detects_drift(monkeypatch):
    assert verify_upstream_pins() == UPSTREAM_SHA256
    monkeypatch.setitem(UPSTREAM_SHA256, "simulator.py", "0" * 64)
    with pytest.raises(ValueError, match="upstream code changed"):
        verify_upstream_pins()


def test_entrypoint_refuses_existing_output_root_before_generation(parity_sample, tmp_path):
    with pytest.raises(ValueError, match="new cohort output root"):
        run(parity_sample["generation"], tmp_path)
