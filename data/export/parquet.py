"""Chunked format conversion; immutable snapshot publication belongs to AI 03.2."""

from __future__ import annotations

import argparse
import csv
import json
import platform
import shutil
import sqlite3
import tempfile
from collections import defaultdict
from contextlib import closing
from pathlib import Path
from typing import TYPE_CHECKING

import pyarrow as pa
import pyarrow.parquet as pq

from data.export.hashing import ContentHash
from data.export.policy import LAYOUT, generated_target
from data.export.schema import FORMAT_VERSION, table_schema, typed_row
from data.generator.identity import canonical_cell, file_sha256, json_sha256, source_data_class
from data.generator.manifest_v2 import MANIFEST_V2_FILENAME, Artifact, SourceManifestV2, unique_keys

if TYPE_CHECKING:
    from collections.abc import Iterator

DEFAULT_CHUNK_ROWS = 8192
MAX_CHUNK_ROWS = 65536
MAX_RECORD_BYTES = 64 * 1024
MAX_CHUNK_BYTES = 8 * 1024 * 1024
PARTITION_MIN_ROWS = 50000
PARTITION_FIELDS = {
    "sales": "sold_at",
    "orders": "ordered_at",
    "returns": "returned_at",
    "return_events": "returned_at",
    "stock_movements": "occurred_at",
    "inventory_snapshots": "recorded_at",
}
CLASS_DIRECTORIES = {
    "source_observation": "facts",
    "source_plan": "facts",
    "simulation_truth": "truth",
    "source_operational_output": "operational_outputs",
}


def csv_chunks(path: Path, columns: list[str], chunk_rows: int) -> Iterator[list[dict]]:
    if not 1 <= chunk_rows <= MAX_CHUNK_ROWS:
        msg = "Invalid CSV chunk bound."
        raise ValueError(msg)
    csv.field_size_limit(MAX_RECORD_BYTES)
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != columns:
            msg = "CSV header does not match source schema."
            raise ValueError(msg)
        chunk = []
        chunk_bytes = 0
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                msg = "Malformed CSV record width."
                raise ValueError(msg)
            row_bytes = sum(len(value.encode("utf-8")) for value in row.values())
            if row_bytes > MAX_RECORD_BYTES:
                msg = "CSV record exceeds the declared byte bound."
                raise ValueError(msg)
            if chunk and chunk_bytes + row_bytes > MAX_CHUNK_BYTES:
                yield chunk
                chunk = []
                chunk_bytes = 0
            chunk.append(row)
            chunk_bytes += row_bytes
            if len(chunk) == chunk_rows:
                yield chunk
                chunk = []
                chunk_bytes = 0
        if chunk:
            yield chunk


def parquet_rows(paths: list[Path], schema: pa.Schema, chunk_rows: int) -> Iterator[list[dict]]:
    for path in paths:
        parquet = pq.ParquetFile(path)
        if not parquet.schema_arrow.equals(schema, check_metadata=True):
            msg = "Parquet schema differs from the declared source types."
            raise ValueError(msg)
        for batch in parquet.iter_batches(batch_size=chunk_rows, use_threads=False):
            yield batch.to_pylist()


def partition_key(
    row: dict, field: str | None, order_dates: sqlite3.Connection | None
) -> str | None:
    if field == "orders.ordered_at":
        order = order_dates.execute(
            "SELECT day FROM dates WHERE id = ?", (row["order_id"],)
        ).fetchone()
        if order is None:
            msg = "Order item is missing its source order date; cannot invent a partition."
            raise ValueError(msg)
        return order[0]
    return row[field].isoformat()[:10] if field else None


def write_table(
    source: Path,
    output: Path,
    artifact: dict,
    profile: str,
    *,
    chunk_rows: int = DEFAULT_CHUNK_ROWS,
    partition_min_rows: int = PARTITION_MIN_ROWS,
    order_dates: sqlite3.Connection | None = None,
    truth_directory: str = "truth",
) -> dict:
    if not 1 <= chunk_rows <= MAX_CHUNK_ROWS or partition_min_rows < 1:
        msg = "Invalid chunk or partition bound."
        raise ValueError(msg)
    name = artifact["table"]
    schema = table_schema(name, profile)
    data_class = source_data_class(name, profile)
    if artifact["data_class"] != data_class:
        msg = "Artifact classification disagrees with source schema."
        raise ValueError(msg)
    namespace = (
        truth_directory if data_class == "simulation_truth" else CLASS_DIRECTORIES[data_class]
    )
    if namespace not in {"facts", "truth", "evaluation_truth", "operational_outputs"}:
        msg = "Unsupported artifact namespace."
        raise ValueError(msg)
    directory = output / namespace / name
    directory.mkdir(parents=True, exist_ok=False)
    field = "business_date" if "business_date" in schema.names else PARTITION_FIELDS.get(name)
    partition_field = field if artifact["row_count"] >= partition_min_rows else None
    if name == "order_items" and artifact["row_count"] >= partition_min_rows:
        if order_dates is None:
            msg = "Large order items require the source order date index."
            raise ValueError(msg)
        partition_field = "orders.ordered_at"
    paths = []
    with ContentHash(schema.names, output) as content:
        for index, chunk in enumerate(csv_chunks(source, schema.names, chunk_rows)):
            rows = [typed_row(row, schema) for row in chunk]
            content.add(rows)
            groups = defaultdict(list)
            for row in rows:
                groups[partition_key(row, partition_field, order_dates)].append(row)
            for partition, values in sorted(groups.items()):
                target = directory / ("business_date=" + partition) if partition else directory
                target.mkdir(exist_ok=True)
                path = target / f"part-{index:06d}.parquet"
                pq.write_table(
                    pa.Table.from_pylist(values, schema=schema),
                    path,
                    version="2.6",
                    compression="zstd",
                    row_group_size=chunk_rows,
                    write_page_checksum=True,
                )
                paths.append(path)
        if not paths:
            path = directory / "part-000000.parquet"
            pq.write_table(pa.Table.from_pylist([], schema=schema), path, compression="zstd")
            paths.append(path)
        logical_hash = content.digest()
        if content.rows != artifact["row_count"] or logical_hash != artifact["content_sha256"]:
            msg = "CSV/typed rows disagree with source count or canonical content hash."
            raise ValueError(msg)
    with ContentHash(schema.names, output) as verified:
        for rows in parquet_rows(paths, schema, chunk_rows):
            verified.add(rows)
        if verified.rows != artifact["row_count"] or verified.digest() != logical_hash:
            msg = "CSV/Parquet typed content parity failed."
            raise ValueError(msg)
    return {
        "table": name,
        "data_class": data_class,
        "row_count": artifact["row_count"],
        "content_sha256": logical_hash,
        "grain": artifact["grain"],
        "date_range": artifact["date_range"],
        "field_ranges": artifact["field_ranges"],
        "partition_source_field": partition_field,
        "schema": [{"name": f.name, "type": str(f.type), "nullable": f.nullable} for f in schema],
        "files": [
            {
                "path": p.relative_to(output).as_posix(),
                "bytes": p.stat().st_size,
                "sha256": file_sha256(p),
                "row_count": pq.ParquetFile(p).metadata.num_rows,
            }
            for p in paths
        ],
    }


def direct_source_file(source: Path, name: str) -> Path:
    if Path(name).name != name:
        msg = "Source artifacts must be direct files."
        raise ValueError(msg)
    path = source / name
    if path.is_symlink() or not path.is_file():
        msg = "Source artifact must be a regular file without symlinks."
        raise ValueError(msg)
    return path


def verified_csv(source: Path, artifact: Artifact) -> Path:
    path = direct_source_file(source, artifact.path)
    if (
        artifact.path != artifact.table + ".csv"
        or file_sha256(path) != artifact.sha256
        or path.stat().st_size != artifact.size_bytes
    ):
        msg = "Source CSV path, byte checksum or size disagrees with manifest."
        raise ValueError(msg)
    return path


def write_artifacts(
    manifest: SourceManifestV2,
    source: Path,
    output: Path,
    chunk_rows: int,
    partition_min_rows: int,
    *,
    tables: tuple[str, ...] | None = None,
    truth_directory: str = "truth",
) -> list[dict]:
    profile = manifest.descriptor.resolved_parameters.profile
    artifacts = {artifact.table: artifact for artifact in manifest.artifacts}
    needs_dates = artifacts["order_items"].row_count >= partition_min_rows
    with (
        tempfile.TemporaryDirectory(prefix=".dates-", dir=output) as temporary,
        closing(sqlite3.connect(Path(temporary) / "dates.sqlite")) as dates,
    ):
        dates.execute("PRAGMA cache_size=-2048")
        dates.execute("CREATE TABLE dates (id TEXT PRIMARY KEY, day TEXT NOT NULL)")
        if needs_dates:
            path = verified_csv(source, artifacts["orders"])
            for rows in csv_chunks(path, artifacts["orders"].columns, chunk_rows):
                dates.executemany(
                    "INSERT INTO dates VALUES (?, ?)",
                    (
                        (row["id"], canonical_cell("ordered_at", row["ordered_at"])[:10])
                        for row in rows
                    ),
                )
        return [
            write_table(
                verified_csv(source, artifact),
                output,
                artifact.model_dump(),
                profile,
                chunk_rows=chunk_rows,
                partition_min_rows=partition_min_rows,
                order_dates=dates if needs_dates else None,
                truth_directory=truth_directory,
            )
            for artifact in manifest.artifacts
            if tables is None or artifact.table in tables
        ]


def convert(
    source: Path,
    output: Path,
    *,
    chunk_rows: int = DEFAULT_CHUNK_ROWS,
    partition_min_rows: int = PARTITION_MIN_ROWS,
) -> dict:
    output = generated_target(output)
    if output.exists():
        msg = "Format output already exists; choose a new directory or explicitly clean it up."
        raise ValueError(msg)
    source = source.resolve(strict=True)
    manifest_file = direct_source_file(source, MANIFEST_V2_FILENAME)
    if manifest_file.stat().st_size > 1024 * 1024:
        msg = "Source manifest exceeds 1 MiB."
        raise ValueError(msg)
    payload = json.loads(manifest_file.read_text(encoding="utf-8"), object_pairs_hook=unique_keys)
    manifest = SourceManifestV2.model_validate(payload)
    profile = manifest.descriptor.resolved_parameters.profile
    if manifest.schema_version != "2.6.0" or not profile.startswith("ai-"):
        msg = "Parquet conversion requires separated AI source 2.6; demo/archives remain CSV."
        raise ValueError(msg)
    if manifest.dataset_id != "source-sha256-" + json_sha256(payload["descriptor"]):
        msg = "Source dataset identity disagrees with descriptor."
        raise ValueError(msg)
    if (
        len(manifest.artifacts) != len(manifest.descriptor.tables)
        or {a.table for a in manifest.artifacts} != set(manifest.descriptor.tables)
        or manifest.schema_version != manifest.descriptor.schema_version
    ):
        msg = "Source manifest requires exactly one artifact per declared table."
        raise ValueError(msg)
    for artifact in manifest.artifacts:
        identity = {
            key: artifact.model_dump()[key]
            for key in ("row_count", "columns", "content_sha256", "data_class")
        }
        if identity != manifest.descriptor.tables[artifact.table].model_dump():
            msg = "Artifact metadata disagrees with the source identity."
            raise ValueError(msg)
    output.mkdir(parents=True)
    for name in LAYOUT:
        (output / name).mkdir()
    result = {
        "format_version": FORMAT_VERSION,
        "status": "format_only",
        "snapshot_ready": False,
        "source_dataset_id": manifest.dataset_id,
        "source_commit": manifest.provenance.git_commit,
        "source_schema_version": manifest.schema_version,
        "chunk_rows": chunk_rows,
        "partition_min_rows": partition_min_rows,
        "max_chunk_bytes": MAX_CHUNK_BYTES,
        "max_record_bytes": MAX_RECORD_BYTES,
        "writer": {
            "pyarrow": pa.__version__,
            "python": platform.python_version(),
            "compression": "zstd",
            "code_sha256": json_sha256(
                {p.name: file_sha256(p) for p in sorted(Path(__file__).parent.glob("*.py"))}
            ),
            "dependency_sha256": file_sha256(
                Path(__file__).parents[1] / "requirements-parquet.txt"
            ),
        },
        "tables": [],
        "reports": [],
        "source_manifest_sha256": file_sha256(manifest_file),
    }
    result["tables"] = write_artifacts(manifest, source, output, chunk_rows, partition_min_rows)
    for report in manifest.reports:
        path = direct_source_file(source, report.path)
        if file_sha256(path) != report.sha256:
            msg = "Source report checksum disagrees with manifest."
            raise ValueError(msg)
        directory = "manifests" if path.name == "dataset_manifest.json" else "reports"
        target = output / directory / path.name
        shutil.copyfile(path, target)
        result["reports"].append(
            {"path": target.relative_to(output).as_posix(), "sha256": report.sha256}
        )
    shutil.copyfile(manifest_file, output / "manifests" / MANIFEST_V2_FILENAME)
    (output / "manifests/format.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert AI source CSV to typed Parquet (format only)."
    )
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--chunk-rows", type=int, default=DEFAULT_CHUNK_ROWS)
    parser.add_argument("--partition-min-rows", type=int, default=PARTITION_MIN_ROWS)
    args = parser.parse_args()
    result = convert(
        args.source_dir,
        args.output_dir,
        chunk_rows=args.chunk_rows,
        partition_min_rows=args.partition_min_rows,
    )
    print(  # noqa: T201 - CLI result
        json.dumps(
            {
                "source_dataset_id": result["source_dataset_id"],
                "tables": len(result["tables"]),
                "snapshot_ready": False,
            }
        )
    )


if __name__ == "__main__":
    main()
