"""Independent parity and strict rejection controls for capacity optimizations."""

from copy import deepcopy
from dataclasses import asdict, replace
from datetime import UTC, date, datetime, timedelta
import hashlib

import pyarrow as pa
import pytest

from data.export.inventory_typed import logical
from data.generator.identity import canonical_file_matches, canonical_json, canonical_json_chunks, content_sha256, json_sha256
from data.inventory.contract import _cached_utc_timestamp, _parse_utc_timestamp, utc_timestamp
from data.inventory.ledger import InventoryMovement
from data.inventory.qualification import Eligibility
from data.inventory.source_dataset_io import normalize_source, verify_normalized_source
from data.tests.test_source_cohort_batch import parity_sample
from data.tests.test_source_cohort_batch_v2 import cached_sample
from data.tests.test_inventory_qualification import isolated


@pytest.mark.parametrize("value", [[], [None, True, 17, "żółć"], [{"z": [1, 2], "a": "é"}]])
def test_streamed_identity_is_the_exact_original_canonical_byte_hash(value):
    assert json_sha256(value) == hashlib.sha256(canonical_json(value)).hexdigest()
    assert b"".join(canonical_json_chunks(value)) == canonical_json(value)


@pytest.mark.parametrize("suffix", [b"\n", b"", b"\n\n", b"\nextra"])
def test_streamed_canonical_file_comparison_checks_all_bytes_and_terminal_newline(tmp_path, suffix):
    value = [{"name": "żółć", "nullable": None}, {"name": "a", "quantity": 7}]
    path = tmp_path / "document.json"
    path.write_bytes(canonical_json(value) + suffix)
    assert canonical_file_matches(path, value) is (suffix == b"\n")


def test_large_disk_sort_preserves_original_nfc_multiset_hash_and_duplicates():
    from data.generator.identity import canonical_cell

    columns = ["name", "quantity"]
    rows = [{"name": "e\u0301" if i % 2 else "é", "quantity": str(i % 7)} for i in range(8193)]
    expected = hashlib.sha256(canonical_json(columns) + b"\n")
    for record in sorted(canonical_json({k: canonical_cell(k, r.get(k)) for k in columns}) for r in rows):
        expected.update(record + b"\n")
    assert content_sha256(rows, columns) == expected.hexdigest()
    assert content_sha256(list(reversed(rows)), columns) == expected.hexdigest()


def test_writer_consumes_only_explicitly_transferred_state_and_fully_revalidates(parity_sample, cached_sample, tmp_path):
    from data.inventory.source_dataset_io import read_source_dataset, write_source_dataset

    rows = deepcopy(cached_sample[0])
    path = write_source_dataset(rows, cached_sample[1], parity_sample["generation"], parity_sample["config"], tmp_path / "consumed", consume_input=True)
    assert rows == {}
    restored, manifest = read_source_dataset(path)
    assert restored == parity_sample["ordinary"] and manifest["facts_ready"]
    kept = deepcopy(cached_sample[0])
    write_source_dataset(kept, cached_sample[1], parity_sample["generation"], parity_sample["config"], tmp_path / "retained")
    assert kept == cached_sample[0]


@pytest.mark.parametrize("value", [None, [], True, "2026-07-01", "2026-07-01T00:00:00+01:00", "2026-02-30T00:00:00Z"])
def test_cached_time_keeps_original_invalid_type_calendar_and_offset_rejection(value):
    with pytest.raises(ValueError) as original:
        _parse_utc_timestamp(value)
    with pytest.raises(ValueError, match=str(original.value)):
        utc_timestamp(value)


def test_timestamp_cache_has_a_fixed_size_and_equal_results_after_eviction():
    _cached_utc_timestamp.cache_clear()
    start = datetime(2026, 7, 1, tzinfo=UTC)
    for offset in range(4100):
        text = (start + timedelta(microseconds=offset)).isoformat()
        assert utc_timestamp(text) == _parse_utc_timestamp(text)
    assert _cached_utc_timestamp.cache_info().currsize == 4096
    assert utc_timestamp(start.isoformat()) == start
    _cached_utc_timestamp.cache_clear()


def test_movement_serialization_matches_asdict_and_detaches_malformed_nested_values(cached_sample):
    row = cached_sample[0]["inventory_ledger"][0]
    movement = InventoryMovement.from_record(row)
    assert movement.record() == asdict(movement)
    nested = ["invalid transfer"]
    replaced = replace(movement, transfer_id=nested)
    serialized = replaced.record()
    assert serialized == asdict(replaced)
    serialized["transfer_id"].append("changed")
    assert nested == ["invalid transfer"]


def test_streaming_normalization_accepts_every_original_canonical_source_table(cached_sample):
    tables = cached_sample[0]
    verify_normalized_source(tables)
    assert normalize_source(tables) == tables


@pytest.mark.parametrize("fault", ["duplicate", "unsorted", "timestamp", "scalar", "extra_table"])
def test_streaming_normalization_preserves_canonical_order_type_and_grain_gates(cached_sample, fault):
    tables = deepcopy(cached_sample[0])
    if fault == "duplicate":
        tables["inventory_ledger"].insert(0, deepcopy(tables["inventory_ledger"][0]))
    elif fault == "unsorted":
        tables["inventory_ledger"][:2] = reversed(tables["inventory_ledger"][:2])
    elif fault == "timestamp":
        tables["inventory_ledger"][0]["occurred_at"] = tables["inventory_ledger"][0]["occurred_at"].replace("+00:00", "Z")
    elif fault == "scalar":
        tables["products"][0]["name"] = 123
    else:
        tables["unexpected"] = []
    with pytest.raises(ValueError):
        verify_normalized_source(tables)
    try:
        ordinary = normalize_source(tables)
    except ValueError:
        pass
    else:
        assert ordinary != tables


def test_eligibility_cache_is_bounded_without_changing_evicted_results(isolated):
    tables, _, diagnostic = isolated
    eligibility = Eligibility(tables)
    product, stock = diagnostic["product_id"], diagnostic["stock_location_id"]
    start = datetime(2026, 7, 1, tzinfo=UTC)
    expected = eligibility.day(product, stock, "2026-07-01", start.isoformat())
    for offset in range(4100):
        eligibility.day(product, stock, "2026-07-01", (start + timedelta(microseconds=offset)).isoformat())
    assert len(eligibility.cache) == 4096
    assert eligibility.day(product, stock, "2026-07-01", start.isoformat()) == expected


def test_streaming_typed_hash_consumes_a_single_pass_with_original_ranges_and_nulls(tmp_path):
    schema = pa.schema([pa.field("id", pa.string()), pa.field("day", pa.date32())])
    rows = [{"id": "z", "day": date(2026, 7, 3)}, {"id": "a", "day": None}, {"id": "z", "day": date(2026, 7, 1)}]
    expected = logical("sample", rows, schema, ["id"], "operational_fact", tmp_path)
    assert logical("sample", iter(rows), schema, ["id"], "operational_fact", tmp_path) == expected
    assert expected["field_ranges"]["day"] == {"date_start": "2026-07-01", "date_end": "2026-07-03", "value_count": 2}
    empty = logical("sample", iter([]), schema, ["id"], "operational_fact", tmp_path)
    assert empty["row_count"] == 0 and empty["date_range"]["value_count"] == 0
