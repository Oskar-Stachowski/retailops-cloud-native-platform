"""Live counters are observational and preserve complete chronological Source output."""

import io
import json
from pathlib import Path

import pytest

from data.generator.progress import PREFIX, advance, counted, reporting, stage
from data.inventory.source_cohort_batch_v2 import run
from data.inventory.source_dataset_io import read_source_dataset
from data.tests.test_source_cohort_batch import parity_sample  # noqa: F401


class Flushed(io.StringIO):
    def __init__(self):
        super().__init__()
        self.flushes = 0

    def flush(self):
        self.flushes += 1
        super().flush()


def records(stream):
    return [json.loads(line.removeprefix(PREFIX)) for line in stream.getvalue().splitlines()]


def test_progress_is_immediate_flush_and_has_no_invented_eta_or_fraction():
    stream = Flushed()
    with reporting(stream):
        advance("build", 7, total=19, unit="records")
        assert stream.flushes == 1
        advance("build", 8, total=19, unit="records")
        advance("build", 19, total=19, unit="records", final=True)
    assert [row["completed"] for row in records(stream)] == [7, 19]
    assert stream.flushes == 2
    assert not any("eta" in row or "percent" in row for row in records(stream))


def test_nested_stage_failure_keeps_error_and_resets_reporter():
    stream = Flushed()

    @stage("inner")
    def inner():
        raise ValueError("private payload must not be logged")

    @stage("outer")
    def outer():
        inner()

    with pytest.raises(ValueError, match="private payload"), reporting(stream):
        outer()
    assert [(r["stage"], r["event"]) for r in records(stream)] == [
        ("outer", "started"), ("inner", "started"), ("inner", "failed"), ("outer", "failed")
    ]
    assert "private payload" not in stream.getvalue()
    advance("after", 1, unit="records")
    assert len(records(stream)) == 4


def test_counted_does_not_prefetch_or_finish_an_incomplete_stream():
    stream = Flushed()
    consumed = []

    def source():
        for value in range(3):
            consumed.append(value)
            yield value

    with reporting(stream):
        iterator = counted("source", source(), total=3)
        assert consumed == []
        assert next(iterator) == 0
        assert consumed == [0]
        iterator.close()
    assert not any(row["event"] == "counter_final" for row in records(stream))


def test_failed_log_write_keeps_original_operation_error_and_resets_context():
    class BrokenAfterStart(Flushed):
        def write(self, value):
            if self.flushes:
                raise OSError("log disk unavailable")
            return super().write(value)

    original = ValueError("native invariant rejected")

    @stage("validation")
    def invalid():
        raise original

    stream = BrokenAfterStart()
    with pytest.raises(ValueError) as caught, reporting(stream):
        invalid()
    assert caught.value is original
    assert original.__notes__ == ["source_progress_failure_event_unavailable"]
    assert len(records(stream)) == 1
    advance("after", 1, unit="records")
    assert len(records(stream)) == 1


def test_log_failure_on_success_is_not_reported_as_success():
    class BrokenFinish(Flushed):
        def write(self, value):
            if self.flushes:
                raise OSError("no final event could be persisted")
            return super().write(value)

    @stage("build")
    def valid():
        return 1

    with pytest.raises(OSError, match="final event"), reporting(BrokenFinish()):
        valid()


@pytest.mark.parametrize("interval", [0, -1, 121])
def test_live_reporting_cannot_silently_exceed_two_minutes(interval):
    with pytest.raises(ValueError), reporting(io.StringIO(), interval_seconds=interval):
        pass


def test_real_full_source_parity_with_progress_and_final_counters(parity_sample, tmp_path):
    stream = Flushed()
    with reporting(stream, interval_seconds=0.001):
        result = run(parity_sample["generation"], tmp_path / "source")
    tables, manifest = read_source_dataset(Path(result["directory"]))
    assert tables == parity_sample["ordinary"]
    assert manifest["facts_ready"]
    values = records(stream)
    assert stream.flushes == len(values)
    stages = {row["stage"] for row in values if row["event"] == "completed"}
    assert {
        "candidate_build", "demand_commerce_build", "source_build", "chronological_simulation",
        "source_reconciliation", "source_validation", "source_write", "source_read",
        "inventory_projection", "validation/private_supplier_realization",
        "validation/inventory_daily_demand_conservation",
    } <= stages
    simulation = [row for row in values if row["stage"] == "chronological_simulation"
                  and row["event"] == "counter_final"]
    assert simulation and all(row["completed"] > 0 for row in simulation)
    assert all(row["completed_business_days"] == 10 for row in simulation)
    assert all(row["known_queued_remaining"] == 0 for row in simulation)
    writes = {row["stage"].split("/", 1)[1]: row for row in values
              if row["stage"].startswith("source_write/") and row["event"] == "counter_final"}
    assert set(writes) == set(tables)
    assert all(writes[name]["completed"] == writes[name]["total"] == len(rows)
               for name, rows in tables.items())


@pytest.mark.parametrize("kind", ["demand", "physical"])
def test_live_planned_source_keeps_all_tables_and_operational_context(kind):
    from data.anomalies.example import example_plan
    from data.anomalies.physical_scenarios import physical_example_plan
    from data.anomalies.source_cohort import build_tables as cached_build
    from data.anomalies.source_process import build_tables as native_build
    from data.generator.configuration import DatasetGenerationConfig
    from data.inventory.run_source_dataset import default_inventory_config
    from data.inventory.source_dataset_io import normalize_source

    generation = DatasetGenerationConfig(
        profile="ai-smoke", days=30, products=8, stores=3, warehouses=2,
        seed=42, forecast_plan_days=14,
    )
    payload = (example_plan if kind == "demand" else physical_example_plan)(generation)
    config = default_inventory_config(generation)
    expected, expected_context = native_build(generation, payload, config)
    stream = Flushed()
    with reporting(stream, interval_seconds=0.001):
        actual, actual_context = cached_build(generation, payload, config)
    assert len(actual) == 58
    assert normalize_source(actual) == normalize_source(expected)
    assert actual_context == expected_context
    values = records(stream)
    assert values[-1]["event"] == "completed"
    assert values[-1]["stage"] == "planned_source_build"
    assert any(row["stage"] == "chronological_simulation" and row["event"] == "counter_final"
               and row["completed_business_days"] == 30 for row in values)
