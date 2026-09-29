"""Qualified publication, corruption, concurrency and immutable repeat regressions."""

import csv
import json
import multiprocessing
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from data.export.ai_snapshot import export_snapshot
from data.export.atomic import publish_directory
from data.export.parquet import parquet_rows
from data.export.policy import GENERATED_ROOT, ROOT
from data.export.schema import table_schema
from data.export.snapshot_contract import FACT_TABLES, MANIFEST_NAME, TRUTH_TABLES, SnapshotManifest
from data.export.snapshot_validation import verify_snapshot
from data.generator.configuration import DatasetGenerationConfig
from data.generator.csv_writer import source_columns, write_csv
from data.generator.identity import file_sha256, json_sha256
from data.generator.main import generate_demo_dataset
from data.generator.manifest_v2 import MANIFEST_V2_FILENAME, artifact_metadata


def hashes(root):
    return {p.relative_to(root).as_posix(): file_sha256(p) for p in root.rglob("*") if p.is_file()}


def save_manifest(path, payload):
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    if path.name == MANIFEST_NAME:
        (path.parent / "manifest.sha256").write_text(file_sha256(path) + "\n")


@pytest.fixture(scope="module")
def snapshot():
    GENERATED_ROOT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ai03-snapshot-test-", dir=GENERATED_ROOT) as temporary:
        base = Path(temporary)
        source = base / "source"
        generate_demo_dataset(source, DatasetGenerationConfig(profile="ai-smoke", seed=42, end_date=date(2026, 7, 31)))
        dataset_id = json.loads((source / MANIFEST_V2_FILENAME).read_text())["dataset_id"]
        before = hashes(source)
        result = export_snapshot(source, dataset_id, base / "snapshots", chunk_rows=511, partition_min_rows=100)
        assert hashes(source) == before
        yield base, source, dataset_id, result


def test_publish_and_idempotent_reuse(snapshot):
    base, source, dataset_id, result = snapshot
    output = Path(result["path"])
    before = hashes(output)
    repeated = export_snapshot(source, dataset_id, base / "snapshots")
    assert result["publication"] == "published"
    assert repeated["publication"] == "reused"
    assert repeated["manifest"] == result["manifest"]
    assert hashes(output) == before
    assert not list((base / "snapshots/.staging").iterdir())
    manifest = verify_snapshot(output)
    assert manifest["snapshot_ready"]
    assert {t["table"] for t in manifest["tables"]} == set(FACT_TABLES)
    assert not (output / "evaluation_truth").exists()
    assert not any(p in str(path) for p in ("users/", "operational_outputs/", "inventory_snapshots/") for path in output.rglob("*.parquet"))
    report = json.loads((output / "reports/source_report.json").read_text())
    assert len(report["checks"]) == 46
    assert report["readiness"]["forecast_source"]["status"] == "ready"
    assert report["readiness"]["forecasting"]["status"] == "not_ready"
    assert manifest["source"]["inventory_ready"] is False
    assert manifest["source"]["watermarks"]


def test_partition_and_execution_metadata_do_not_change_identity(snapshot):
    base, source, dataset_id, result = snapshot
    second = export_snapshot(source, dataset_id, base / "other", chunk_rows=2048)
    assert second["manifest"]["snapshot_id"] == result["manifest"]["snapshot_id"]
    assert next(t for t in second["manifest"]["tables"] if t["table"] == "sales")["files"] != next(t for t in result["manifest"]["tables"] if t["table"] == "sales")["files"]
    reordered = base / "reordered"
    shutil.copytree(source, reordered)
    path = reordered / "users.csv"
    with path.open() as stream:
        rows = list(csv.DictReader(stream))
    write_csv(path, rows[::-1], source_columns("users", "ai-smoke"))
    source_manifest_path = reordered / MANIFEST_V2_FILENAME
    payload = json.loads(source_manifest_path.read_text())
    artifact = next(a for a in payload["artifacts"] if a["table"] == "users")
    artifact.update(sha256=file_sha256(path), size_bytes=path.stat().st_size)
    payload["generated_at"] = "2026-09-29T00:00:00+00:00"
    payload["provenance"]["git_commit"] = "f" * 40
    save_manifest(source_manifest_path, payload)
    before = hashes(Path(result["path"]))
    reused = export_snapshot(reordered, dataset_id, base / "snapshots")
    assert reused["publication"] == "reused"
    assert hashes(Path(result["path"])) == before


def test_optional_truth_is_separate_and_variant_conflicts(snapshot):
    base, source, dataset_id, result = snapshot
    before = hashes(Path(result["path"]))
    with pytest.raises(ValueError, match="conflict"):
        export_snapshot(source, dataset_id, base / "snapshots", include_truth=True)
    assert hashes(Path(result["path"])) == before
    truth = export_snapshot(source, dataset_id, base / "truth", include_truth=True)
    assert truth["manifest"]["snapshot_id"] != result["manifest"]["snapshot_id"]
    output = Path(truth["path"])
    assert {p.name for p in (output / "facts").iterdir()} == set(FACT_TABLES)
    assert {p.name for p in (output / "evaluation_truth").iterdir()} == set(TRUTH_TABLES)
    assert (output / "evaluation_truth").stat().st_mode & 0o777 == 0o700
    assert not (output / "truth").exists()


@pytest.mark.parametrize("use_case", ["forecasting", "anomaly", "stockout", "replay", "rag"])
def test_required_unready_use_case_blocks_publication(snapshot, use_case):
    base, source, dataset_id, _ = snapshot
    root = base / ("unready-" + use_case)
    with pytest.raises(ValueError, match="not ready"):
        export_snapshot(source, dataset_id, root, required_use_cases=(use_case,))
    assert not (root / dataset_id).exists()


@pytest.mark.parametrize("fault", ["bytes", "missing", "symlink", "unsafe", "version", "identity", "gate"])
def test_source_fault_never_publishes(snapshot, fault):
    base, source, dataset_id, _ = snapshot
    broken = base / ("source-" + fault)
    shutil.copytree(source, broken)
    path = broken / "sales.csv"
    manifest_path = broken / MANIFEST_V2_FILENAME
    manifest = json.loads(manifest_path.read_text())
    if fault == "bytes":
        path.write_text(path.read_text() + "corrupted\n")
    elif fault == "missing":
        path.unlink()
    elif fault == "symlink":
        path.unlink()
        path.symlink_to(source / "sales.csv")
    elif fault == "unsafe":
        manifest["artifacts"][0]["path"] = "../products.csv"
    elif fault == "version":
        manifest["schema_version"] = "9.0.0"
    elif fault == "identity":
        manifest["dataset_id"] = "source-sha256-" + "0" * 64
    elif fault == "gate":
        path = broken / "source_report.json"
        report = json.loads(path.read_text())
        report["checks"][0]["status"] = "failed"
        report["status"] = "failed"
        path.write_text(json.dumps(report))
        ref = next(r for r in manifest["reports"] if r["path"] == path.name)
        ref.update(sha256=file_sha256(path), size_bytes=path.stat().st_size)
    save_manifest(manifest_path, manifest)
    root = base / ("rejected-" + fault)
    with pytest.raises((ValueError, OSError)):
        export_snapshot(broken, dataset_id, root)
    assert not (root / dataset_id).exists()
    assert not list((root / ".staging").iterdir())


def test_passed_report_does_not_hide_an_actual_failed_gate(snapshot):
    base, source, _, _ = snapshot
    broken = base / "forged-passed-gate"
    shutil.copytree(source, broken)
    path = broken / "orders.csv"
    with path.open() as stream:
        rows = list(csv.DictReader(stream))
    rows[0]["order_total"] = "-1.00"
    write_csv(path, rows, source_columns("orders", "ai-smoke"))
    manifest_path = broken / MANIFEST_V2_FILENAME
    manifest = json.loads(manifest_path.read_text())
    actual = artifact_metadata("orders", rows, broken, "2026-07-31", "ai-smoke")
    artifact = next(a for a in manifest["artifacts"] if a["table"] == "orders")
    artifact.update(actual)
    identity = manifest["descriptor"]["tables"]["orders"]
    identity.update({key: actual[key] for key in identity})
    dataset_id = "source-sha256-" + json_sha256(manifest["descriptor"])
    manifest["dataset_id"] = dataset_id
    save_manifest(manifest_path, manifest)
    assert json.loads((broken / "source_report.json").read_text())["status"] == "passed"
    root = base / "rejected-forged-gate"
    with pytest.raises(ValueError):
        export_snapshot(broken, dataset_id, root)
    assert not (root / dataset_id).exists()


@pytest.mark.parametrize("fault", ["bytes", "missing", "extra", "directory", "symlink", "path", "version", "identity", "logical", "file_count", "partition", "manifest"])
def test_published_bundle_faults_are_rejected(snapshot, fault):
    base, _, _, result = snapshot
    output = base / ("bundle-" + fault)
    shutil.copytree(result["path"], output)
    path = output / MANIFEST_NAME
    payload = json.loads(path.read_text())
    table = next(t for t in payload["tables"] if t["table"] == "sales")
    ref = table["files"][0]
    parquet = output / ref["path"]
    if fault == "bytes":
        with parquet.open("ab") as stream:
            stream.write(b"corrupted")
    elif fault == "missing":
        parquet.unlink()
    elif fault == "extra":
        (output / "credentials.txt").write_text("unreferenced")
    elif fault == "directory":
        (output / "users").mkdir()
    elif fault == "symlink":
        parquet.unlink()
        parquet.symlink_to(Path(result["path"]) / ref["path"])
    elif fault == "path":
        ref["path"] = "../outside.parquet"
    elif fault == "version":
        payload["schema_version"] = "9.0.0"
    elif fault == "identity":
        payload["source_dataset_id"] = "source-sha256-" + "0" * 64
    elif fault == "logical":
        original = pq.ParquetFile(parquet).read()
        rows = original.to_pylist()
        rows[0]["quantity"] += 1
        pq.write_table(pa.Table.from_pylist(rows, schema=original.schema), parquet)
        ref.update(bytes=parquet.stat().st_size, sha256=file_sha256(parquet))
    elif fault == "file_count":
        ref["row_count"] += 1
    elif fault == "partition":
        original = parquet.parent
        moved = original.parent / "business_date=1900-01-01"
        original.rename(moved)
        for file_ref in table["files"]:
            file_ref["path"] = file_ref["path"].replace(original.name, moved.name)
    elif fault == "manifest":
        path.write_text(path.read_text() + " ")
    if fault != "manifest":
        save_manifest(path, payload)
    with pytest.raises((ValueError, OSError)):
        verify_snapshot(output)


def test_snapshot_schema_matches_executable_contract():
    path = ROOT / "data/contracts/ai_snapshot.v1.schema.json"
    assert json.loads(path.read_text()) == SnapshotManifest.model_json_schema()


def test_atomic_publication_refuses_even_an_empty_destination(tmp_path):
    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "payload").write_text("complete")
    destination = tmp_path / "destination"
    destination.mkdir()
    with pytest.raises(FileExistsError):
        publish_directory(staging, destination)
    assert (staging / "payload").is_file()
    assert not list(destination.iterdir())
    destination.rmdir()
    publish_directory(staging, destination)
    assert (destination / "payload").read_text() == "complete"
    assert not staging.exists()


def export_worker(source, dataset_id, root, queue):
    try:
        result = export_snapshot(Path(source), dataset_id, Path(root))
        queue.put((result["publication"], result["manifest"]["snapshot_id"]))
    except Exception as error:
        queue.put(("error", repr(error)))


def test_concurrent_exports_publish_once(snapshot):
    base, source, dataset_id, _ = snapshot
    context = multiprocessing.get_context("spawn")
    queue = context.Queue()
    root = base / "concurrent"
    processes = [context.Process(target=export_worker, args=(str(source), dataset_id, str(root), queue)) for _ in range(2)]
    for process in processes:
        process.start()
    results = [queue.get(timeout=120) for _ in processes]
    for process in processes:
        process.join(timeout=120)
        assert process.exitcode == 0
    assert sorted(item[0] for item in results) == ["published", "reused"]
    assert results[0][1] == results[1][1]
    assert not list((root / ".staging").iterdir())
    verify_snapshot(root / dataset_id)


def test_publication_failure_leaves_no_ready_snapshot(snapshot, monkeypatch):
    base, source, dataset_id, _ = snapshot
    def failed_publish(*args):
        raise OSError("simulated crash before publication")
    monkeypatch.setattr("data.export.ai_snapshot.publish_directory", failed_publish)
    root = base / "crash"
    with pytest.raises(OSError, match="simulated crash"):
        export_snapshot(source, dataset_id, root)
    assert not (root / dataset_id).exists()
    assert not list((root / ".staging").iterdir())


@pytest.mark.parametrize("arguments", [[], ["--profile", "ai-smoke"], ["--source-dir", "missing"], ["--profile", "ai-smoke", "--seed", "42", "--end-date", "2026-07-31", "--dataset-id", "wrong"]])
def test_cli_requires_explicit_input(arguments):
    process = subprocess.run([sys.executable, "-m", "data.export.ai_snapshot", *arguments], cwd=ROOT, capture_output=True, text=True)
    assert process.returncode == 2


def test_history_keeps_all_versions_and_availability(snapshot):
    _, source, _, result = snapshot
    table = next(t for t in result["manifest"]["tables"] if t["table"] == "daily_demand_versions")
    paths = [Path(result["path"]) / f["path"] for f in table["files"]]
    actual = [row for chunk in parquet_rows(paths, table_schema(table["table"], "ai-smoke"), 41) for row in chunk]
    with (source / "daily_demand_versions.csv").open() as stream:
        expected = list(csv.DictReader(stream))
    assert len(actual) == len(expected)
    by_id = {row["id"]: row for row in actual}
    for row in expected:
        assert by_id[row["id"]]["version"] == int(row["version"])
        assert by_id[row["id"]]["available_at"].isoformat() == row["available_at"].replace("Z", "+00:00")


def test_mutating_original_after_validation_cannot_change_published_data(snapshot, monkeypatch):
    import data.export.ai_snapshot as exporter
    base, source, dataset_id, result = snapshot
    mutable = base / "mutable-after-validation"
    shutil.copytree(source, mutable)
    seal = exporter.seal_source
    def seal_and_mutate(*args):
        manifest = seal(*args)
        (mutable / "sales.csv").write_text("changed after successful validation\n")
        return manifest
    monkeypatch.setattr(exporter, "seal_source", seal_and_mutate)
    exported = exporter.export_snapshot(mutable, dataset_id, base / "sealed-copy")
    assert exported["manifest"]["snapshot_id"] == result["manifest"]["snapshot_id"]
    verify_snapshot(Path(exported["path"]))
