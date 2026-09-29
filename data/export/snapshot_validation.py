"""Offline verification of an exported bundle; never writes into the snapshot."""

from __future__ import annotations

import json
import re
import sqlite3
import stat
import tempfile
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

import pyarrow.parquet as pq

from data.export.hashing import ContentHash
from data.export.parquet import DEFAULT_CHUNK_ROWS, PARTITION_FIELDS, parquet_rows, partition_key
from data.export.schema import table_schema
from data.export.snapshot_contract import (
    CONTRACT_FILES,
    FACT_TABLES,
    MANIFEST_NAME,
    TRUTH_TABLES,
    FileReference,
    LogicalTable,
    SnapshotManifest,
    TableArtifact,
)
from data.generator.configuration import resolve_generation_config
from data.generator.identity import file_sha256, json_sha256
from data.generator.manifest_v2 import (
    MANIFEST_V2_FILENAME,
    SourceManifestV2,
    config_from_parameters,
    unique_keys,
    watermark_metadata,
)


def safe_file(root: Path, relative: str) -> Path:
    name = PurePosixPath(relative)
    if (
        not relative
        or "\\" in relative
        or name.is_absolute()
        or any(part in {".", ".."} for part in relative.split("/"))
        or name.as_posix() != relative
    ):
        msg = "Unsafe snapshot/source file path."
        raise ValueError(msg)
    path = root / relative
    for part in (path, *path.parents):
        if part.is_symlink():
            msg = "Symlinks are forbidden in snapshot/source paths."
            raise ValueError(msg)
    if not stat.S_ISREG(path.stat().st_mode):
        msg = "Snapshot/source artifact must be a regular file."
        raise ValueError(msg)
    return path


def read_json(path: Path, *, max_bytes: int = 4 * 1024 * 1024) -> dict:
    if path.stat().st_size > max_bytes:
        msg = "JSON metadata exceeds its byte limit."
        raise ValueError(msg)
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_keys)


def reference(root: Path, path: Path) -> dict:
    return {
        "path": path.relative_to(root).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": file_sha256(path),
    }


def check_reference(root: Path, ref: FileReference) -> Path:
    path = safe_file(root, ref.path)
    if path.stat().st_size != ref.bytes or file_sha256(path) != ref.sha256:
        msg = "Snapshot byte checksum or size mismatch."
        raise ValueError(msg)
    return path


def logical_tables(source: SourceManifestV2, *, include_truth: bool) -> list[dict]:
    allowed = FACT_TABLES + (TRUTH_TABLES if include_truth else ())
    profile = source.descriptor.resolved_parameters.profile
    return [
        {
            **{
                key: artifact.model_dump()[key]
                for key in (
                    "table",
                    "data_class",
                    "row_count",
                    "content_sha256",
                    "grain",
                    "date_range",
                    "field_ranges",
                )
            },
            "schema": [
                {"name": f.name, "type": str(f.type), "nullable": f.nullable}
                for f in table_schema(artifact.table, profile)
            ],
        }
        for artifact in source.artifacts
        if artifact.table in allowed
    ]


def check_source_metadata(source: SourceManifestV2) -> None:
    descriptor = source.descriptor.model_dump()
    if source.schema_version != "2.6.0" or source.descriptor.schema_version != "2.6.0":
        msg = "Snapshot requires the separated, versioned source contract 2.6.0."
        raise ValueError(msg)
    if source.dataset_id != "source-sha256-" + json_sha256(descriptor):
        msg = "Invalid source identity."
        raise ValueError(msg)
    config = config_from_parameters(source.requested_parameters.model_dump())
    effective = resolve_generation_config(config)
    if effective.parameters() != source.descriptor.resolved_parameters.model_dump():
        msg = "Requested/effective source configuration mismatch."
        raise ValueError(msg)
    provenance = source.provenance.model_dump()
    for kind in ("code", "dependency"):
        if (
            json_sha256(provenance[kind + "_files"]) != provenance[kind + "_sha256"]
            or provenance[kind + "_sha256"] != descriptor[kind + "_sha256"]
        ):
            msg = "Source provenance differs from identity."
            raise ValueError(msg)
    if provenance["python_version"] != descriptor["python_version"]:
        msg = "Source Python provenance mismatch."
        raise ValueError(msg)
    if {k: v.model_dump() for k, v in source.watermarks.items()} != watermark_metadata(
        effective.end_date, config.profile, source.schema_version
    ):
        msg = "Source watermarks mismatch."
        raise ValueError(msg)
    if not source.source_ready or source.inventory_ready:
        msg = "Source readiness must qualify forecasting input without inventory."
        raise ValueError(msg)
    names = [artifact.table for artifact in source.artifacts]
    if len(set(names)) != len(names) or set(names) != set(source.descriptor.tables):
        msg = "Source artifacts require every identity table exactly once."
        raise ValueError(msg)
    for artifact in source.artifacts:
        identity = source.descriptor.tables[artifact.table].model_dump()
        if any(artifact.model_dump()[key] != value for key, value in identity.items()):
            msg = "Source artifact disagrees with its identity."
            raise ValueError(msg)


def qualification(report: dict, required: list[str]) -> None:
    if (
        report.get("policy_version") != "forecast-source-acceptance-1.1.0"
        or report.get("status") != "passed"
        or report.get("source_ready") is not True
        or report.get("inventory_ready") is not False
        or len(report.get("checks", [])) != 46
        or any(
            check.get("status") != "passed" or check.get("severity") != "hard"
            for check in report["checks"]
        )
    ):
        msg = "Source hard gate failed; snapshot publication is blocked."
        raise ValueError(msg)
    if not required or len(set(required)) != len(required):
        msg = "Declare unique required use cases."
        raise ValueError(msg)
    for use_case in required:
        if report.get("readiness", {}).get(use_case, {}).get("status") != "ready":
            msg = f"Required use case {use_case!r} is not ready."
            raise ValueError(msg)


def verify_lineage(manifest: SnapshotManifest) -> list[dict]:
    descriptor = manifest.descriptor.model_dump(by_alias=True)
    source = manifest.source
    check_source_metadata(source)
    if (
        manifest.snapshot_id != "snapshot-sha256-" + json_sha256(descriptor)
        or manifest.source_dataset_id != source.dataset_id
        or descriptor["parent_source_dataset_id"] != source.dataset_id
        or json_sha256(manifest.exporter.code_files) != descriptor["exporter_code_sha256"]
        or manifest.exporter.dependency_sha256 != descriptor["dependency_sha256"]
    ):
        msg = "Snapshot identity/lineage mismatch."
        raise ValueError(msg)
    generated = datetime.fromisoformat(manifest.generated_at)
    if generated.utcoffset() != UTC.utcoffset(generated):
        msg = "Snapshot generation timestamp requires UTC."
        raise ValueError(msg)
    expected = logical_tables(source, include_truth=descriptor["include_evaluation_truth"])
    logical_keys = [field.alias or key for key, field in LogicalTable.model_fields.items()]
    actual = [
        {key: table.model_dump(by_alias=True)[key] for key in logical_keys}
        for table in manifest.tables
    ]
    if actual != expected or descriptor["tables"] != expected:
        msg = "Snapshot must contain the exact allowed tables, classifications and source lineage."
        raise ValueError(msg)
    return expected


def verify_inventory(root: Path, manifest: SnapshotManifest) -> dict[str, FileReference]:
    references = [*manifest.metadata_files, *(f for table in manifest.tables for f in table.files)]
    names = [ref.path for ref in references]
    if len(names) != len(set(names)):
        msg = "Duplicate snapshot file references."
        raise ValueError(msg)
    inventory = set()
    expected_directories = {
        parent.as_posix()
        for name in names
        for parent in PurePosixPath(name).parents
        if parent.as_posix() != "."
    }
    for path in root.rglob("*"):
        if path.is_symlink() or (not path.is_dir() and not stat.S_ISREG(path.stat().st_mode)):
            msg = "Snapshot contains symlinks or special files."
            raise ValueError(msg)
        if path.is_file():
            inventory.add(path.relative_to(root).as_posix())
        elif path.relative_to(root).as_posix() not in expected_directories:
            msg = "Snapshot contains an unreferenced directory."
            raise ValueError(msg)
    if inventory != {*names, MANIFEST_NAME, "manifest.sha256"}:
        msg = "Snapshot has missing or unreferenced artifacts."
        raise ValueError(msg)
    for ref in references:
        check_reference(root, ref)
    return {ref.path: ref for ref in manifest.metadata_files}


def verify_metadata(
    root: Path, manifest: SnapshotManifest, expected: list[dict], metadata: dict[str, FileReference]
) -> None:
    source = manifest.source
    descriptor = manifest.descriptor.model_dump(by_alias=True)
    expected_metadata = {
        "manifests/" + MANIFEST_V2_FILENAME,
        *("reports/" + report.path for report in source.reports),
        *("schemas/" + name for name in CONTRACT_FILES),
        *("schemas/" + table["table"] + ".arrow.json" for table in expected),
    }
    if descriptor["include_evaluation_truth"]:
        expected_metadata.add("schemas/retail_simulation.v1.schema.json")
    if set(metadata) != expected_metadata:
        msg = "Snapshot metadata inventory differs from the contract."
        raise ValueError(msg)
    if read_json(safe_file(root, "manifests/" + MANIFEST_V2_FILENAME)) != source.model_dump():
        msg = "Source manifest copy disagrees with snapshot lineage."
        raise ValueError(msg)
    for report in source.reports:
        ref = metadata["reports/" + report.path]
        if ref.sha256 != report.sha256 or ref.bytes != report.size_bytes:
            msg = "Source report reference mismatch."
            raise ValueError(msg)
    schemas = {
        ref.path: ref.sha256 for ref in manifest.metadata_files if ref.path.startswith("schemas/")
    }
    if schemas != descriptor["schemas"]:
        msg = "Schema fingerprint mismatch."
        raise ValueError(msg)
    source_report_ref = metadata["reports/source_report.json"]
    if source_report_ref.sha256 != descriptor["source_qualification_sha256"]:
        msg = "Qualification fingerprint mismatch."
        raise ValueError(msg)
    qualification(read_json(root / source_report_ref.path), descriptor["required_use_cases"])


def verify_table(
    root: Path, table: TableArtifact, profile: str, scratch: Path, dates: sqlite3.Connection
) -> None:
    schema = table_schema(table.table, profile)
    field = (
        "business_date" if "business_date" in schema.names else PARTITION_FIELDS.get(table.table)
    )
    if table.table == "order_items":
        field = "orders.ordered_at"
    if table.partition_source_field not in {None, field}:
        msg = "Partition source field disagrees with source time semantics."
        raise ValueError(msg)
    if read_json(root / f"schemas/{table.table}.arrow.json") != {
        "table": table.table,
        "schema": [c.model_dump() for c in table.column_schema],
    }:
        msg = "Arrow schema file mismatch."
        raise ValueError(msg)
    namespace = "evaluation_truth" if table.data_class == "simulation_truth" else "facts"
    prefix = f"{namespace}/{table.table}/"
    with ContentHash(schema.names, scratch) as content:
        for ref in table.files:
            suffix = ref.path.removeprefix(prefix)
            pattern = (
                r"business_date=(\d{4}-\d{2}-\d{2})/part-\d{6}\.parquet"
                if table.partition_source_field
                else r"part-\d{6}\.parquet"
            )
            match = re.fullmatch(pattern, suffix)
            if not ref.path.startswith(prefix) or not match:
                msg = "Parquet path disagrees with table/classification/partition metadata."
                raise ValueError(msg)
            path = root / ref.path
            if pq.ParquetFile(path).metadata.num_rows != ref.row_count:
                msg = "Parquet physical file count mismatch."
                raise ValueError(msg)
            for rows in parquet_rows([path], schema, DEFAULT_CHUNK_ROWS):
                if table.partition_source_field and any(
                    partition_key(row, table.partition_source_field, dates) != match[1]
                    for row in rows
                ):
                    msg = "Parquet rows disagree with their date partition."
                    raise ValueError(msg)
                content.add(rows)
        if content.rows != table.row_count or content.digest() != table.content_sha256:
            msg = "Snapshot typed logical content mismatch."
            raise ValueError(msg)


def verify_tables(root: Path, manifest: SnapshotManifest, scratch: Path | None) -> None:
    profile = manifest.source.descriptor.resolved_parameters.profile
    with (
        tempfile.TemporaryDirectory(prefix="snapshot-verify-", dir=scratch) as temporary,
        closing(sqlite3.connect(Path(temporary) / "dates.sqlite")) as dates,
    ):
        dates.execute("PRAGMA cache_size=-2048")
        dates.execute("CREATE TABLE dates (id TEXT PRIMARY KEY, day TEXT NOT NULL)")
        if any(t.table == "order_items" and t.partition_source_field for t in manifest.tables):
            orders = next(t for t in manifest.tables if t.table == "orders")
            for rows in parquet_rows(
                [root / f.path for f in orders.files],
                table_schema("orders", profile),
                DEFAULT_CHUNK_ROWS,
            ):
                dates.executemany(
                    "INSERT INTO dates VALUES (?, ?)",
                    ((row["id"], row["ordered_at"].date().isoformat()) for row in rows),
                )
        for table in manifest.tables:
            verify_table(root, table, profile, Path(temporary), dates)


def verify_snapshot(root: Path, *, scratch: Path | None = None) -> dict:
    """Verify versions, lineage, inventory, byte hashes and all typed logical rows."""
    manifest_path = safe_file(root, MANIFEST_NAME)
    checksum = safe_file(root, "manifest.sha256").read_text(encoding="ascii")
    if checksum != file_sha256(manifest_path) + "\n":
        msg = "Manifest checksum mismatch."
        raise ValueError(msg)
    payload = read_json(manifest_path)
    manifest = SnapshotManifest.model_validate(payload)
    expected = verify_lineage(manifest)
    metadata = verify_inventory(root, manifest)
    verify_metadata(root, manifest, expected, metadata)
    verify_tables(root, manifest, scratch)
    return payload
