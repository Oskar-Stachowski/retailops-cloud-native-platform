"""Inventory source 2.7 -> snapshot 1.1 transport, isolation and immutable publication."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from data.export import inventory_snapshot as exporter
from data.export.inventory_contract import (
    FACT_TABLES,
    TRUTH_TABLES,
    handoff_contract,
    snapshot_schema,
)
from data.export.inventory_typed import logical
from data.export.policy import GENERATED_ROOT
from data.generator.configuration import DatasetGenerationConfig
from data.generator.identity import canonical_json, file_sha256, json_sha256
from data.inventory.qualification_io import write_qualification
from data.inventory import qualification_io
from data.inventory.run_source_dataset import build_source_dataset, default_inventory_config
from data.inventory.source_dataset_io import write_source_dataset


def hashes(root):
    return {p.relative_to(root).as_posix(): file_sha256(p) for p in root.rglob("*") if p.is_file()}


def reseal(root, document):
    for ref in [*document["metadata_files"], *(r for t in document["tables"] for r in t["files"])]:
        path = root / ref["path"]
        ref.update(bytes=path.stat().st_size, sha256=file_sha256(path))
    document["descriptor"]["schemas"] = {
        r["path"]: r["sha256"]
        for r in document["metadata_files"]
        if r["path"].startswith("schemas/")
    }
    document["snapshot_id"] = "snapshot-sha256-" + json_sha256(document["descriptor"])
    (root / "snapshot_manifest.json").write_bytes(canonical_json(document) + b"\n")
    (root / "manifest.sha256").write_text(file_sha256(root / "snapshot_manifest.json") + "\n")


@pytest.fixture(scope="module")
def snapshot():
    GENERATED_ROOT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="ai06-snapshot11-test-", dir=GENERATED_ROOT
    ) as temporary:
        base = Path(temporary)
        generation = DatasetGenerationConfig(
            profile="ai-smoke", days=10, products=3, stores=3, warehouses=2
        )
        config = default_inventory_config(generation)
        tables, context = build_source_dataset(generation, config)
        source = write_source_dataset(tables, context, generation, config, base / "sources")
        qualification = write_qualification(source, base / "qualifications")
        before = hashes(source), hashes(qualification)
        result = exporter.export_inventory_snapshot(
            source, source.name, qualification, base / "snapshots", chunk_rows=17
        )
        private = exporter.export_inventory_snapshot(
            source, source.name, qualification, base / "private", include_truth=True
        )
        assert before == (hashes(source), hashes(qualification))
        yield base, source, qualification, result, private


def test_checked_schema_and_43_fact_allowlist(snapshot):
    _, _, _, result, _ = snapshot
    root = Path(result["path"])
    manifest = exporter.verify_inventory_snapshot(root)
    assert (
        json.loads(Path("data/contracts/inventory_snapshot.v1_1.schema.json").read_text())
        == snapshot_schema()
    )
    assert (
        json.loads((root / "schemas/source_snapshot_handoff.v1_1.json").read_text())
        == handoff_contract()
    )
    assert len(FACT_TABLES) == 43 and len(TRUTH_TABLES) == 12
    assert [t["table"] for t in manifest["tables"]] == list(FACT_TABLES)
    assert not (root / "evaluation_truth").exists()
    assert all(
        manifest["source"][k] is False for k in ("source_ready", "inventory_ready", "model_ready")
    )
    assert all(p.stat().st_mode & 0o777 == 0o600 for p in root.rglob("*") if p.is_file())


def test_default_export_preserves_pinned_independent_consumer_schema_bytes(snapshot):
    _, _, _, result, _ = snapshot
    root = Path(result["path"])
    assert result["manifest"]["source"]["descriptor"]["generator_version"] == "0.9.0"
    assert file_sha256(root / "schemas/inventory_snapshot.v1_1.schema.json") == (
        "ec040a294eff7a898eba59572dc7cf2deec01b29a48ed555b493154ce0694447"
    )
    assert file_sha256(root / "schemas/inventory_source_dataset.v2_7.schema.json") == (
        "22938590dcf0183e8c5a7f83a648a7e037dad794e71a0e26158bb6aef43f75a9"
    )


@pytest.mark.parametrize(
    "filename", ["inventory_snapshot.v1_1.schema.json", "inventory_source_dataset.v2_7.schema.json"]
)
def test_resealed_mixed_legacy_and_forecast_contracts_are_refused(snapshot, tmp_path, filename):
    _, _, _, result, _ = snapshot
    root = tmp_path / "mixed-contracts"
    shutil.copytree(result["path"], root)
    (root / "schemas" / filename).write_bytes((Path("data/contracts") / filename).read_bytes())
    document = json.loads((root / "snapshot_manifest.json").read_text())
    reseal(root, document)
    with pytest.raises(ValueError, match="Unreviewed snapshot schema"):
        exporter.verify_inventory_snapshot(root)


def test_partition_metadata_and_chunking_do_not_change_identity(snapshot):
    base, source, qualification, result, _ = snapshot
    original = hashes(Path(result["path"]))
    repeat = exporter.export_inventory_snapshot(
        source, source.name, qualification, base / "other", chunk_rows=127
    )
    assert repeat["manifest"]["snapshot_id"] == result["manifest"]["snapshot_id"]
    reused = exporter.export_inventory_snapshot(
        source, source.name, qualification, base / "snapshots"
    )
    assert reused["publication"] == "reused" and hashes(Path(result["path"])) == original
    assert not list((base / "snapshots/.staging").iterdir())


def test_private_qualification_has_explicit_opt_in_and_variant_identity(snapshot):
    base, source, qualification, result, private = snapshot
    root = Path(private["path"])
    with pytest.raises(ValueError, match="opt-in"):
        exporter.verify_inventory_snapshot(root)
    manifest = exporter.verify_inventory_snapshot(root, allow_evaluation_truth=True)
    assert [t["table"] for t in manifest["tables"]] == [*FACT_TABLES, *TRUTH_TABLES]
    assert manifest["snapshot_id"] != result["manifest"]["snapshot_id"]
    assert (
        root / "evaluation_truth/qualification/simulation_truth/inventory_qualified_windows.json"
    ).is_file()
    before = hashes(Path(result["path"]))
    with pytest.raises(ValueError, match="conflict"):
        exporter.export_inventory_snapshot(
            source, source.name, qualification, base / "snapshots", include_truth=True
        )
    assert before == hashes(Path(result["path"]))


@pytest.mark.parametrize(
    "fault",
    [
        "bytes",
        "extra",
        "symlink",
        "parent",
        "qualification",
        "gate",
        "schema",
        "typed_content",
        "projection",
    ],
)
def test_corruption_and_resealed_forgery_fail_closed(snapshot, tmp_path, fault):
    original = Path(snapshot[3]["path"])
    root = Path(shutil.copytree(original, tmp_path / "input"))
    document = json.loads((root / "snapshot_manifest.json").read_text())
    table = next(t for t in document["tables"] if t["table"] == "inventory_ledger")
    path = root / table["files"][0]["path"]
    if fault == "bytes":
        path.write_bytes(path.read_bytes() + b"corruption")
    elif fault == "extra":
        (root / "evaluation_truth").mkdir()
        (root / "evaluation_truth/secret.json").write_text("[]")
    elif fault == "symlink":
        path.unlink()
        path.symlink_to(original / table["files"][0]["path"])
    elif fault == "parent":
        document["descriptor"]["parent_source_dataset_id"] = "source-sha256-" + "a" * 64
        reseal(root, document)
    elif fault == "qualification":
        document["descriptor"]["qualification"]["parent_source_id"] = "source-sha256-" + "a" * 64
        document["descriptor"]["parent_qualification_id"] = (
            "inventory-labels-sha256-" + json_sha256(document["descriptor"]["qualification"])
        )
        reseal(root, document)
    elif fault == "gate":
        report_path = root / "reports/source_report.json"
        report = json.loads(report_path.read_text())
        report["checks"][-1]["check_id"] = "unknown_passed_gate"
        report_path.write_bytes(canonical_json(report) + b"\n")
        ref = document["source"]["reports"]["source_report.json"]
        ref.update(sha256=file_sha256(report_path), size_bytes=report_path.stat().st_size)
        (root / "manifests/dataset_manifest.v2.json").write_bytes(
            canonical_json(document["source"]) + b"\n"
        )
        document["descriptor"]["source_qualification_sha256"] = ref["sha256"]
        reseal(root, document)
    elif fault == "schema":
        schema_path = root / "schemas/inventory_source_tables.v1.schema.json"
        schema_path.write_text("{}")
        reseal(root, document)
    else:
        arrow = pq.ParquetFile(path).read()
        rows = arrow.to_pylist()
        rows[0]["quantity_delta"] += 1
        pq.write_table(pa.Table.from_pylist(rows, schema=arrow.schema), path)
        if fault == "projection":
            all_rows = []
            for ref in table["files"]:
                all_rows.extend(pq.ParquetFile(root / ref["path"]).read().to_pylist())
            computed = logical(
                table["table"],
                all_rows,
                arrow.schema,
                table["grain"],
                table["data_class"],
                tmp_path,
            )
            table.update(computed)
            document["descriptor"]["tables"] = [
                {k: t[k] for k in computed} for t in document["tables"]
            ]
        reseal(root, document)
    with pytest.raises((ValueError, OSError)):
        exporter.verify_inventory_snapshot(root)


@pytest.mark.parametrize("use_case", ["forecasting", "stockout", "model08", "replay", "rag"])
def test_model_readiness_is_not_implied_by_local_source_facts(snapshot, use_case):
    base, source, qualification, _, _ = snapshot
    with pytest.raises(ValueError, match="options"):
        exporter.export_inventory_snapshot(
            source, source.name, qualification, base / use_case, required_use_cases=(use_case,)
        )
    assert not (base / use_case / source.name).exists()


def test_rejected_export_and_invalid_outputs_leave_no_publication(snapshot, tmp_path):
    base, source, qualification, _, _ = snapshot
    with pytest.raises(ValueError, match="data/generated"):
        exporter.export_inventory_snapshot(source, source.name, qualification, tmp_path / "outside")
    broken = Path(shutil.copytree(qualification, base / "broken-qualification"))
    (broken / "qualification_report.json").write_text("{}")
    with pytest.raises(ValueError):
        exporter.export_inventory_snapshot(source, source.name, broken, base / "broken-output")
    assert not (base / "broken-output" / source.name).exists()
    assert not list((base / "broken-output/.staging").iterdir())


def test_sealing_checks_full_source_once_and_requalifies_verified_copy(snapshot, monkeypatch):
    base, source, qualification, _, _ = snapshot
    original = exporter.read_source_dataset
    checks = []

    def checked(path):
        checks.append(path)
        return original(path)

    def must_not_reread(path):
        raise AssertionError("Verified private source should not be recomputed by qualification IO")

    monkeypatch.setattr(exporter, "read_source_dataset", checked)
    monkeypatch.setattr(qualification_io, "read_source_dataset", must_not_reread)
    result = exporter.export_inventory_snapshot(source, source.name, qualification, base / "once")
    assert result["publication"] == "published"
    assert len(checks) == 1 and checks[0] != source
    assert not list((base / "once/.staging").iterdir())


@pytest.mark.parametrize(
    "fault", ["source_bytes", "source_extra", "qualification_extra", "explicit_id"]
)
def test_sealing_optimization_does_not_trust_unverified_input(snapshot, fault):
    base, source, qualification, _, _ = snapshot
    changed_source = Path(shutil.copytree(source, base / (fault + "-source")))
    changed_qualification = Path(shutil.copytree(qualification, base / (fault + "-qualification")))
    identifier = source.name
    if fault == "source_bytes":
        path = changed_source / "facts/inventory_ledger.csv"
        path.write_bytes(path.read_bytes() + b"corruption\n")
    elif fault == "source_extra":
        (changed_source / "unknown.json").write_text("{}")
    elif fault == "qualification_extra":
        (changed_qualification / "unknown.json").write_text("{}")
    else:
        identifier = "source-sha256-" + "a" * 64
    output = base / (fault + "-rejected")
    with pytest.raises(ValueError):
        exporter.export_inventory_snapshot(
            changed_source, identifier, changed_qualification, output
        )
    assert not (output / identifier).exists()
    assert not list((output / ".staging").iterdir())
