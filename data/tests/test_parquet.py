"""Parity, resource policy and cleanup regressions, without a DB or worker image."""

import csv
import json
import shutil
import sqlite3
import subprocess
import tempfile
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from data.export.benchmark import enforce_limits
from data.export.hashing import ContentHash
from data.export.parquet import MAX_RECORD_BYTES, convert, csv_chunks, parquet_rows, partition_key, write_table
from data.export.policy import GENERATED_ROOT, ROOT, cleanup, fixture_budget, generated_target
from data.export.schema import table_schema, typed_row
from data.generator.configuration import DatasetGenerationConfig
from data.generator.csv_writer import source_columns, write_csv
from data.generator.identity import content_sha256, file_sha256
from data.generator.main import generate_demo_dataset
from data.generator.manifest_v2 import MANIFEST_V2_FILENAME, artifact_metadata
from data.seed_files import ensure_seed_files


@pytest.fixture(scope="module")
def smoke():
    GENERATED_ROOT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ai03-test-", dir=GENERATED_ROOT) as temporary:
        base = Path(temporary)
        source = base / "csv"
        generate_demo_dataset(source, DatasetGenerationConfig(profile="ai-smoke"))
        yield base, source


def test_full_source_parity_and_partition_independence(smoke):
    base, source = smoke
    before = {p.name: file_sha256(p) for p in source.iterdir()}
    first = convert(source, base / "first", chunk_rows=511, partition_min_rows=100)
    second = convert(source, base / "second", chunk_rows=2048, partition_min_rows=50000)
    assert first["source_dataset_id"] == second["source_dataset_id"]
    assert not first["snapshot_ready"]
    assert len(first["tables"]) == 40
    assert before == {p.name: file_sha256(p) for p in source.iterdir()}
    for one, two in zip(first["tables"], second["tables"], strict=True):
        name = one["table"]
        with (source / f"{name}.csv").open() as stream:
            expected = list(csv.DictReader(stream))
        paths = [base / "first" / file["path"] for file in one["files"]]
        actual = [row for rows in parquet_rows(paths, table_schema(name, "ai-smoke"), 321) for row in rows]
        assert content_sha256(actual, source_columns(name, "ai-smoke")) == content_sha256(expected, source_columns(name, "ai-smoke"))
        assert one["content_sha256"] == two["content_sha256"]
        assert one["row_count"] == two["row_count"] == len(actual)
        for file in one["files"]:
            path = base / "first" / file["path"]
            assert file_sha256(path) == file["sha256"]
            assert path.stat().st_size == file["bytes"]
            assert pq.ParquetFile(path).metadata.row_group(0).num_rows <= 511 if len(actual) else True
    facts = list((base / "first/facts").rglob("*.parquet"))
    assert any("business_date=" in str(path) for path in facts)
    items = next(table for table in first["tables"] if table["table"] == "order_items")
    assert items["partition_source_field"] == "orders.ordered_at"
    assert all("business_date=" in file["path"] for file in items["files"])
    assert not any("truth" in str(path) for path in facts)
    assert (base / "first/truth/daily_demand_truth").is_dir()
    assert (base / "first/operational_outputs/forecasts").is_dir()
    assert (base / "first/raw_events").is_dir()
    assert (base / "first/manifests" / MANIFEST_V2_FILENAME).is_file()
    assert (base / "first/reports/source_report.json").is_file()
    assert not list((base / "first").glob(".hash-*"))
    with pytest.raises(ValueError, match="already exists"):
        convert(source, base / "first")


@pytest.mark.parametrize("fault", ["corrupt", "missing", "symlink", "header", "logical", "missing_table", "duplicate_table", "identity"])
def test_invalid_source_refused(smoke, fault):
    base, source = smoke
    bad = base / ("bad-" + fault)
    shutil.copytree(source, bad)
    path = bad / "sales.csv"
    manifest_path = bad / MANIFEST_V2_FILENAME
    manifest = json.loads(manifest_path.read_text())
    if fault == "corrupt":
        path.write_text(path.read_text() + "corrupt\n")
    elif fault == "missing":
        path.unlink()
    elif fault == "symlink":
        path.unlink()
        path.symlink_to(source / "sales.csv")
    elif fault == "header":
        path.write_text(path.read_text().replace("quantity", "unknown", 1))
    elif fault == "logical":
        path.write_text(path.read_text().replace(",PLN,", ",EUR,", 1))
        artifact = next(a for a in manifest["artifacts"] if a["table"] == "sales")
        artifact["sha256"] = file_sha256(path)
        artifact["size_bytes"] = path.stat().st_size
    elif fault == "missing_table":
        manifest["artifacts"].pop()
    elif fault == "duplicate_table":
        manifest["artifacts"][-1] = manifest["artifacts"][0]
    elif fault == "identity":
        manifest["dataset_id"] = "source-sha256-" + "0" * 64
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises((ValueError, OSError)):
        convert(bad, base / ("out-" + fault))
    assert not (base / ("out-" + fault) / "manifests/format.json").exists()


def test_history_null_zero_versions_and_utc_are_preserved(tmp_path):
    name = "daily_demand_versions"
    rows = []
    for version, units, status in [(1, "", "missing"), (2, "0", "observed_zero"), (3, "4", "observed_positive")]:
        rows.append({"id": str(version), "observation_id": "observation", "business_date": "2026-07-01", "product_id": "product", "selling_location_id": "location", "channel": "store", "version": str(version), "observed_units": units, "observation_status": status, "available_at": f"2026-07-0{version+1}T02:00:00+02:00", "history_policy_version": "observed-quantity-history-1.0.0"})
    path = tmp_path / f"{name}.csv"
    write_csv(path, rows, source_columns(name, "ai-smoke"))
    artifact = artifact_metadata(name, rows, tmp_path, "2026-07-31", "ai-smoke")
    result = write_table(path, tmp_path, artifact, "ai-smoke", chunk_rows=1, partition_min_rows=1)
    actual = [row for chunk in parquet_rows([tmp_path / f["path"] for f in result["files"]], table_schema(name, "ai-smoke"), 1) for row in chunk]
    assert [row["observed_units"] for row in actual] == [None, 0, 4]
    assert [row["version"] for row in actual] == [1, 2, 3]
    assert actual[0]["business_date"] == date(2026, 7, 1)
    assert actual[0]["available_at"] == datetime(2026, 7, 2, tzinfo=timezone.utc)


@pytest.mark.parametrize("field,value", [("version", "1.2"), ("version", "NaN"), ("available_at", "2026-07-01T00:00:00"), ("observed_units", "inf"), ("id", "")])
def test_invalid_types_refused(field, value):
    row = {key: "value" for key in source_columns("daily_demand_versions", "ai-smoke")}
    row.update(business_date="2026-07-01", version="1", observed_units="0", available_at="2026-07-02T00:00:00Z")
    row[field] = value
    with pytest.raises(ValueError):
        typed_row(row, table_schema("daily_demand_versions", "ai-smoke"))


def test_money_has_no_rounding_and_factors_retain_precision():
    schema = pa.schema([pa.field("price", pa.decimal128(38, 2)), pa.field("noise", pa.decimal256(76, 40))])
    typed = typed_row({"price": "123.45", "noise": "0.001234567890123456789012345678"}, schema)
    assert typed["price"] == Decimal("123.45")
    assert typed["noise"] == Decimal("0.001234567890123456789012345678")
    with pytest.raises(pa.ArrowInvalid):
        pa.Table.from_pylist([typed_row({"price": "1.001", "noise": "1"}, schema)], schema=schema)
    with pytest.raises(ValueError, match="precision"):
        typed_row({"price": "1", "noise": "1.123456789012345678901234567890123"}, schema)


def test_disk_multiset_hash_preserves_duplicates_and_nulls(tmp_path):
    rows = [{"quantity": "0"}, {"quantity": ""}, {"quantity": "0"}]
    with ContentHash(["quantity"], tmp_path) as content:
        content.add(rows[::-1])
        assert content.rows == 3
        assert content.digest() == content_sha256(rows, ["quantity"])
        assert content.digest() != content_sha256(rows[:2], ["quantity"])


def test_csv_chunk_bounds_and_oversize_record(tmp_path):
    path = tmp_path / "rows.csv"
    write_csv(path, [{"id": str(i)} for i in range(7)], ["id"])
    assert [len(chunk) for chunk in csv_chunks(path, ["id"], 3)] == [3, 3, 1]
    with pytest.raises(ValueError):
        list(csv_chunks(path, ["id"], 0))
    write_csv(path, [{"id": "x" * MAX_RECORD_BYTES, "sku": "x"}], ["id", "sku"])
    with pytest.raises(ValueError, match="byte bound"):
        list(csv_chunks(path, ["id", "sku"], 10))


def test_missing_order_date_is_not_invented():
    with sqlite3.connect(":memory:") as connection:
        connection.execute("CREATE TABLE dates (id TEXT PRIMARY KEY, day TEXT)")
        with pytest.raises(ValueError, match="cannot invent"):
            partition_key({"order_id": "unknown"}, "orders.ordered_at", connection)


def test_sub_microsecond_timestamp_is_not_truncated():
    schema = pa.schema([pa.field("available_at", pa.timestamp("us", tz="UTC"))])
    with pytest.raises(ValueError, match="microsecond"):
        typed_row({"available_at": "2026-07-01T00:00:00.1234567Z"}, schema)


@pytest.fixture
def repository(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "data/generated").mkdir(parents=True)
    return tmp_path


@pytest.mark.parametrize("kind", ["root", "outside", "traversal", "symlink", "nested_symlink", "tracked", "tracked_literal"])
def test_cleanup_guards(repository, kind):
    target = repository / "data/generated" / ("run[1]" if kind == "tracked_literal" else "run")
    target.mkdir()
    file = target / "fixture.csv"
    file.write_text("keep me")
    if kind == "root":
        target = target.parent
    elif kind == "outside":
        target = repository / "data"
    elif kind == "traversal":
        target = target.parent / "../generated/run"
    elif kind == "symlink":
        alias = target.parent / "alias"
        alias.symlink_to(target, target_is_directory=True)
        target = alias
    elif kind == "nested_symlink":
        (target / "alias").symlink_to(file)
    elif kind in {"tracked", "tracked_literal"}:
        subprocess.run(["git", "add", "-f", str(file)], cwd=repository, check=True)
    with pytest.raises(ValueError):
        cleanup(target, delete=True, repository=repository)
    assert file.read_text() == "keep me"


def test_cleanup_preview_and_actual_delete(repository):
    target = repository / "data/generated/run"
    target.mkdir()
    (target / "file").write_text("123")
    assert cleanup(target, repository=repository) == {"files": 1, "bytes": 3, "deleted": False}
    assert target.exists()
    assert cleanup(target, delete=True, repository=repository)["deleted"]
    assert not target.exists()


def test_tracked_artifact_budget_and_demo_protection():
    assert fixture_budget()["unpacked_bytes"] < 5 * 1024 * 1024
    with pytest.raises(ValueError):
        generated_target(ROOT / "data/demo")
    assert (ROOT / "data/demo/sales.csv").is_file()


@pytest.mark.parametrize("seconds,rss", [(301, 100), (1, 1025)])
def test_resource_budget_is_blocking(seconds, rss):
    with pytest.raises(ValueError, match="budget"):
        enforce_limits({"total_seconds": seconds, "peak_rss_mib": rss}, 300, 1024)


@pytest.mark.parametrize("profile", ["demo", "small"])
def test_seed_from_fresh_checkout_and_existing_csv_untouched(tmp_path, profile):
    target = ensure_seed_files(profile, tmp_path)
    assert len(list(target.glob("*.csv"))) == 17
    before = {p.name: file_sha256(p) for p in target.iterdir()}
    ensure_seed_files(profile, tmp_path)
    assert before == {p.name: file_sha256(p) for p in target.iterdir()}
    (target / "sales.csv").unlink()
    with pytest.raises(ValueError, match="Incomplete"):
        ensure_seed_files(profile, tmp_path)
