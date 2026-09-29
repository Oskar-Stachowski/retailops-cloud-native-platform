"""Qualified, immutable local source snapshots for the AI repository."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import platform
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from datetime import UTC, date, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pyarrow as pa

from data.export.atomic import publish_directory, sync_bundle
from data.export.parquet import (
    DEFAULT_CHUNK_ROWS,
    MAX_CHUNK_ROWS,
    PARTITION_MIN_ROWS,
    write_artifacts,
)
from data.export.policy import GENERATED_ROOT, ROOT, generated_target
from data.export.schema import FORMAT_VERSION
from data.export.snapshot_contract import (
    CONTRACT_FILES,
    FACT_TABLES,
    MANIFEST_NAME,
    POLICY_VERSION,
    TRUTH_TABLES,
    USE_CASES,
    SnapshotManifest,
)
from data.export.snapshot_validation import (
    check_source_metadata,
    logical_tables,
    qualification,
    read_json,
    reference,
    safe_file,
    verify_snapshot,
)
from data.generator.configuration import SUPPORTED_PROFILES, DatasetGenerationConfig
from data.generator.identity import file_sha256, json_sha256
from data.generator.main import generate_demo_dataset
from data.generator.manifest_v2 import (
    MANIFEST_V2_FILENAME,
    SourceManifestV2,
    load_source_manifest_v2,
)

if TYPE_CHECKING:
    from collections.abc import Iterator


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def seal_source(source: Path, sealed: Path, dataset_id: str) -> SourceManifestV2:
    """Copy and verify the complete source before gates; writer reads only this copy."""
    payload = read_json(safe_file(source, MANIFEST_V2_FILENAME), max_bytes=1024 * 1024)
    manifest = SourceManifestV2.model_validate(payload)
    check_source_metadata(manifest)
    if manifest.dataset_id != dataset_id:
        msg = "Explicit dataset ID differs from the source manifest."
        raise ValueError(msg)
    sealed.mkdir(mode=0o700)
    names = set()
    for ref in [*manifest.artifacts, *manifest.reports]:
        if Path(ref.path).name != ref.path or ref.path in names:
            msg = "Source artifacts/reports must be unique direct files."
            raise ValueError(msg)
        names.add(ref.path)
        path = safe_file(source, ref.path)
        destination = sealed / ref.path
        # O_NOFOLLOW also closes a last-component symlink race between stat and open.
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as stream, destination.open("xb") as target:
            shutil.copyfileobj(stream, target, length=1024 * 1024)
        if destination.stat().st_size != ref.size_bytes or file_sha256(destination) != ref.sha256:
            msg = "Source changed during sealing or its checksum/size is invalid."
            raise ValueError(msg)
    write_json(sealed / MANIFEST_V2_FILENAME, payload)
    # Recompute dimensions, pricing, demand, returns, truth separation, history,
    # all 46 hard gates and realism. Cached passed flags are insufficient.
    return SourceManifestV2.model_validate(load_source_manifest_v2(sealed))


def exporter_provenance() -> dict:
    files = {
        path.relative_to(ROOT).as_posix(): file_sha256(path)
        for path in sorted((ROOT / "data/export").glob("*.py"))
    }
    executable = shutil.which("git")
    if executable is None:
        msg = "Git is required for exporter provenance."
        raise ValueError(msg)
    commit = subprocess.run(  # noqa: S603 - fixed git executable and arguments, no shell
        [executable, "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    return {
        "git_commit": commit,
        "python_version": platform.python_version(),
        "pyarrow_version": pa.__version__,
        "code_files": files,
        "dependency_sha256": file_sha256(ROOT / "data/requirements-parquet.txt"),
    }


def copy_metadata(
    source: SourceManifestV2, sealed: Path, bundle: Path, *, include_truth: bool
) -> list[dict]:
    for name in ("facts", "reports", "schemas", "manifests"):
        (bundle / name).mkdir()
    if include_truth:
        (bundle / "evaluation_truth").mkdir(mode=0o700)
    for report in source.reports:
        shutil.copyfile(sealed / report.path, bundle / "reports" / report.path)
    shutil.copyfile(sealed / MANIFEST_V2_FILENAME, bundle / "manifests" / MANIFEST_V2_FILENAME)
    schemas = CONTRACT_FILES + (("retail_simulation.v1.schema.json",) if include_truth else ())
    for name in schemas:
        shutil.copyfile(safe_file(ROOT / "data/contracts", name), bundle / "schemas" / name)
    for table in logical_tables(source, include_truth=include_truth):
        write_json(
            bundle / "schemas" / (table["table"] + ".arrow.json"),
            {"table": table["table"], "schema": table["schema"]},
        )
    return [reference(bundle, path) for path in sorted(bundle.rglob("*")) if path.is_file()]


@contextmanager
def publication_lock(root: Path, dataset_id: str) -> Iterator[None]:
    directory = generated_target(root / ".locks")
    directory.mkdir(mode=0o700, exist_ok=True)
    fd = os.open(directory / (dataset_id + ".lock"), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "a") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def export_snapshot(
    source: Path,
    dataset_id: str,
    output_root: Path = GENERATED_ROOT / "snapshots",
    *,
    include_truth: bool = False,
    required_use_cases: tuple[str, ...] = ("forecast_source",),
    chunk_rows: int = DEFAULT_CHUNK_ROWS,
    partition_min_rows: int = PARTITION_MIN_ROWS,
) -> dict:
    """Return the full manifest and published path; identical export is read-only reuse."""
    output_root = generated_target(output_root)
    if not 1 <= chunk_rows <= MAX_CHUNK_ROWS or partition_min_rows < 1:
        msg = "Invalid chunk/partition bounds."
        raise ValueError(msg)
    # Validate the ID before constructing paths/lock names.
    if (
        len(dataset_id) != 78
        or not dataset_id.startswith("source-sha256-")
        or any(character not in "0123456789abcdef" for character in dataset_id[14:])
    ):
        msg = "Expected a canonical explicit source dataset ID."
        raise ValueError(msg)
    if not required_use_cases or any(case not in USE_CASES for case in required_use_cases):
        msg = "Unsupported or empty required use cases."
        raise ValueError(msg)
    destination = generated_target(output_root / dataset_id)
    if source.absolute() == destination or source.absolute().is_relative_to(output_root):
        msg = "Source must be separate from snapshot publication storage."
        raise ValueError(msg)
    staging_root = generated_target(output_root / ".staging")
    staging_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="export-", dir=staging_root) as temporary:
        work = Path(temporary)
        sealed = work / "source"
        source_manifest = seal_source(source, sealed, dataset_id)
        required = sorted(required_use_cases)
        qualification(read_json(sealed / "source_report.json"), required)
        bundle = work / "bundle"
        bundle.mkdir(mode=0o700)
        metadata = copy_metadata(source_manifest, sealed, bundle, include_truth=include_truth)
        provenance = exporter_provenance()
        descriptor = {
            "role": "source_snapshot",
            "identity_version": "1.0.0",
            "policy_version": POLICY_VERSION,
            "format_version": FORMAT_VERSION,
            "parent_source_dataset_id": dataset_id,
            "required_use_cases": required,
            "include_evaluation_truth": include_truth,
            "exporter_code_sha256": json_sha256(provenance["code_files"]),
            "dependency_sha256": provenance["dependency_sha256"],
            "source_qualification_sha256": file_sha256(sealed / "source_report.json"),
            "schemas": {
                ref["path"]: ref["sha256"] for ref in metadata if ref["path"].startswith("schemas/")
            },
            "tables": logical_tables(source_manifest, include_truth=include_truth),
        }
        snapshot_id = "snapshot-sha256-" + json_sha256(descriptor)
        with publication_lock(output_root, dataset_id):
            if destination.exists():
                existing = verify_snapshot(destination, scratch=work)
                if existing["descriptor"] != descriptor:
                    msg = "Immutable snapshot conflict: choose a separate output root for this variant."
                    raise ValueError(msg)
                return {"publication": "reused", "path": str(destination), "manifest": existing}
            tables = write_artifacts(
                source_manifest,
                sealed,
                bundle,
                chunk_rows,
                partition_min_rows,
                tables=FACT_TABLES + (TRUTH_TABLES if include_truth else ()),
                truth_directory="evaluation_truth",
            )
            payload = {
                "schema_version": "1.0.0",
                "snapshot_id": snapshot_id,
                "source_dataset_id": dataset_id,
                "source_repository": "retailops-cloud-native-platform",
                "generated_at": datetime.now(UTC).isoformat(),
                "snapshot_ready": True,
                "descriptor": descriptor,
                "source": source_manifest.model_dump(),
                "exporter": provenance,
                "tables": tables,
                "metadata_files": metadata,
            }
            SnapshotManifest.model_validate(payload)
            write_json(bundle / MANIFEST_NAME, payload)
            (bundle / "manifest.sha256").write_text(
                file_sha256(bundle / MANIFEST_NAME) + "\n", encoding="ascii"
            )
            verified = verify_snapshot(bundle, scratch=work)
            sync_bundle(bundle)
            publish_directory(bundle, destination)
            return {"publication": "published", "path": str(destination), "manifest": verified}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--source-dir", type=Path)
    mode.add_argument("--profile", choices=[p for p in SUPPORTED_PROFILES if p.startswith("ai-")])
    parser.add_argument("--dataset-id")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--end-date", type=date.fromisoformat)
    parser.add_argument("--start-date", type=date.fromisoformat)
    for option in ("days", "products", "stores", "warehouses", "max-daily-rows"):
        parser.add_argument("--" + option, type=int)
    parser.add_argument("--output-root", type=Path, default=GENERATED_ROOT / "snapshots")
    parser.add_argument("--include-evaluation-truth", action="store_true")
    parser.add_argument("--require-use-case", action="append", choices=USE_CASES)
    parser.add_argument("--chunk-rows", type=int, default=DEFAULT_CHUNK_ROWS)
    parser.add_argument("--partition-min-rows", type=int, default=PARTITION_MIN_ROWS)
    args = parser.parse_args()
    options = {
        "include_truth": args.include_evaluation_truth,
        "required_use_cases": tuple(args.require_use_case or ["forecast_source"]),
        "chunk_rows": args.chunk_rows,
        "partition_min_rows": args.partition_min_rows,
    }
    if args.source_dir:
        if not args.dataset_id or any(
            getattr(args, name) is not None
            for name in (
                "seed",
                "end_date",
                "start_date",
                "days",
                "products",
                "stores",
                "warehouses",
                "max_daily_rows",
            )
        ):
            parser.error("Source mode requires --dataset-id and forbids generator configuration.")
        result = export_snapshot(args.source_dir, args.dataset_id, args.output_root, **options)
    else:
        if args.dataset_id or args.seed is None or args.end_date is None:
            parser.error(
                "Generation mode requires explicit --profile, --seed and --end-date; no --dataset-id."
            )
        config = DatasetGenerationConfig(
            **{
                name: getattr(args, name)
                for name in (
                    "profile",
                    "seed",
                    "end_date",
                    "start_date",
                    "days",
                    "products",
                    "stores",
                    "warehouses",
                    "max_daily_rows",
                )
            }
        )
        output_root = generated_target(args.output_root)
        GENERATED_ROOT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="ai03-source-", dir=GENERATED_ROOT) as temporary:
            source = Path(temporary) / "csv"
            generate_demo_dataset(source, config)
            dataset_id = read_json(source / MANIFEST_V2_FILENAME)["dataset_id"]
            result = export_snapshot(source, dataset_id, output_root, **options)
    print(json.dumps(result, indent=2))  # noqa: T201 - CLI returns full manifest


if __name__ == "__main__":
    main()
