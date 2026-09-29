"""AI 03.6: two pinned repositories, two full smoke flows, bounded fresh processes."""

# ruff: noqa: INP001, PLC0415
# Standalone orchestration script; producer dependencies load only in its worker.

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import resource
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROFILES = ("ai-smoke", "ai-temporal-smoke")
MAX_SECONDS = 300
MAX_RSS_MIB = 1024


def git(root: Path, *arguments: str) -> str:
    return subprocess.check_output(  # noqa: S603 - fixed executable, no shell
        [shutil.which("git") or "/usr/bin/git", "-C", str(root), *arguments], text=True
    ).strip()


def pinned(root: Path, revision: str) -> None:
    if len(revision) != 40 or any(c not in "0123456789abcdef" for c in revision):
        msg = "full_git_sha_required"
        raise ValueError(msg)
    if git(root, "rev-parse", "HEAD") != revision or git(root, "status", "--porcelain"):
        msg = "dirty_or_unpinned_repository"
        raise ValueError(msg)


def hashes(root: Path) -> dict[str, str]:
    return {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob("*")
        if p.is_file()
    }


def producer(profile: str, workspace: Path) -> dict:
    # The consumer is a separate interpreter/repository, never an import here.
    from data.export.ai_snapshot import export_snapshot
    from data.export.hashing import ContentHash
    from data.export.parquet import csv_chunks, parquet_rows
    from data.export.schema import table_schema, typed_row
    from data.generator.configuration import DatasetGenerationConfig
    from data.generator.main import generate_demo_dataset
    from data.generator.manifest_v2 import MANIFEST_V2_FILENAME

    started = time.monotonic()
    source = workspace / "csv"
    generate_demo_dataset(
        source, DatasetGenerationConfig(profile=profile, seed=42, end_date=date(2026, 7, 31))
    )
    generated = time.monotonic()
    manifest = json.loads((source / MANIFEST_V2_FILENAME).read_text())
    source_bytes = hashes(source)
    first = export_snapshot(
        source, manifest["dataset_id"], workspace / "snapshots", partition_min_rows=100
    )
    snapshot = Path(first["path"])
    before = hashes(snapshot)
    second = export_snapshot(
        source, manifest["dataset_id"], workspace / "snapshots", partition_min_rows=100
    )
    if (
        second["publication"] != "reused"
        or hashes(snapshot) != before
        or hashes(source) != source_bytes
    ):
        msg = "reexport_changed_immutable_data"
        raise ValueError(msg)
    parity = []
    for table in first["manifest"]["tables"]:
        schema = table_schema(table["table"], profile)
        with (
            ContentHash(schema.names, workspace) as csv_hash,
            ContentHash(schema.names, workspace) as pq_hash,
        ):
            for batch in csv_chunks(source / (table["table"] + ".csv"), schema.names, 8192):
                csv_hash.add([typed_row(row, schema) for row in batch])
            for batch in parquet_rows([snapshot / f["path"] for f in table["files"]], schema, 8192):
                pq_hash.add(batch)
            if (
                csv_hash.rows != pq_hash.rows
                or csv_hash.digest() != pq_hash.digest()
                or pq_hash.digest() != table["content_sha256"]
            ):
                msg = "typed_csv_parquet_values_differ"
                raise ValueError(msg)
        parity.append(
            {
                k: table[k]
                for k in (
                    "table",
                    "row_count",
                    "content_sha256",
                    "grain",
                    "date_range",
                    "field_ranges",
                    "schema",
                )
            }
        )
    report = json.loads((source / "source_report.json").read_text())
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (
        1024**2 if sys.platform == "darwin" else 1024
    )
    return {
        "snapshot_path": str(snapshot),
        "source_dataset_id": manifest["dataset_id"],
        "snapshot_id": first["manifest"]["snapshot_id"],
        "source_commit": manifest["provenance"]["git_commit"],
        "exporter": first["manifest"]["exporter"],
        "source_provenance": manifest["provenance"],
        "source_parameters": manifest["descriptor"]["resolved_parameters"],
        "watermarks": manifest["watermarks"],
        "hard_gates": len(report["checks"]),
        "readiness": report["readiness"],
        "inventory_ready": manifest["inventory_ready"],
        "source_manifest_sha256": source_bytes[MANIFEST_V2_FILENAME],
        "snapshot_manifest_sha256": before["snapshot_manifest.json"],
        "typed_csv_parquet_parity": "passed",
        "logical_tables": parity,
        "idempotent_reexport": True,
        "generation_seconds": generated - started,
        "seconds": time.monotonic() - started,
        "peak_rss_mib": rss,
        "python": platform.python_version(),
    }


def run_worker(command: list[str], cwd: Path, timeout: float) -> dict:
    environment = {**os.environ, "PYTHONPATH": str(cwd / "src") if cwd != ROOT else str(ROOT)}
    result = subprocess.run(  # noqa: S603 - explicit interpreter/script and separate arguments
        command,
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr[-12000:] or result.stdout[-12000:])
    return json.loads(result.stdout)


def identity(run: dict) -> tuple:
    return (
        run["producer"]["source_dataset_id"],
        run["producer"]["snapshot_id"],
        run["consumer"]["curated_dataset_id"],
        run["producer"]["logical_tables"],
        run["consumer"]["logical_tables"],
    )


def enforce(run: dict) -> None:
    if run["seconds"] > MAX_SECONDS or run["peak_rss_mib"] > MAX_RSS_MIB:
        msg = "full_pipeline_budget_exceeded"
        raise ValueError(msg)
    upstream, downstream = run["producer"], run["consumer"]
    if (
        upstream["source_dataset_id"] != downstream["source_dataset_id"]
        or upstream["snapshot_id"] != downstream["snapshot_id"]
    ):
        msg = "cross_repo_lineage_differs"
        raise ValueError(msg)
    if (
        upstream["hard_gates"] != 46
        or upstream["inventory_ready"]
        or downstream["quarantine_rows"]
        or downstream["evaluation_truth_in_curated"]
    ):
        msg = "qualification_quarantine_truth_failed"
        raise ValueError(msg)
    if (
        run["profile"] == "ai-temporal-smoke"
        and downstream["late_correction"]["status"] != "passed"
    ):
        msg = "real_late_correction_not_exercised"
        raise ValueError(msg)


def main() -> None:  # noqa: PLR0915 - sequential acceptance with always-written evidence
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--consumer-root", type=Path)
    parser.add_argument("--consumer-python", type=Path)
    parser.add_argument("--producer-revision")
    parser.add_argument("--consumer-revision")
    parser.add_argument(
        "--output", type=Path, default=ROOT / "ci-cd/reports/data/ai03-cross-repo.json"
    )
    parser.add_argument("--producer-worker", choices=PROFILES, help=argparse.SUPPRESS)
    parser.add_argument("--workspace", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.producer_worker:
        if args.workspace is None:
            parser.error("workspace required")
        print(json.dumps(producer(args.producer_worker, args.workspace)))  # noqa: T201 - worker protocol
        return
    if any(
        v is None
        for v in (
            args.consumer_root,
            args.consumer_python,
            args.producer_revision,
            args.consumer_revision,
        )
    ):
        parser.error("Both repository revisions, consumer root and interpreter are required.")
    consumer = args.consumer_root.resolve()
    pinned(ROOT, args.producer_revision)
    pinned(consumer, args.consumer_revision)
    generated = ROOT / "data/generated"
    generated.mkdir(exist_ok=True)
    report = {
        "policy_version": "ai03-cross-repo-budget-1.0.0",
        "status": "running",
        "pipeline": "generate/recomputed-qualification/export/typed-CSV-Parquet-parity/reexport/import/curated/rebuild/verify/as-of",
        "producer_revision": args.producer_revision,
        "consumer_revision": args.consumer_revision,
        "limits": {"seconds_per_full_run": MAX_SECONDS, "peak_process_rss_mib": MAX_RSS_MIB},
        "resource_scope": "Wall time of both sequential fresh workers including process startup; conservative sum of orchestrator peak RSS and maximum worker RSS (workers do not overlap). Dependency installation excluded.",
        "environment": {"platform": platform.platform(), "architecture": platform.machine()},
        "runs": [],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        for profile in PROFILES:
            previous = None
            for repeat in range(2):
                pinned(ROOT, args.producer_revision)
                pinned(consumer, args.consumer_revision)
                with tempfile.TemporaryDirectory(prefix="ai03-cross-", dir=generated) as temporary:
                    workspace = Path(temporary)
                    started = time.monotonic()
                    upstream = run_worker(
                        [
                            sys.executable,
                            str(Path(__file__).resolve()),
                            "--producer-worker",
                            profile,
                            "--workspace",
                            str(workspace),
                        ],
                        ROOT,
                        MAX_SECONDS,
                    )
                    remaining = MAX_SECONDS - (time.monotonic() - started)
                    if remaining <= 0:
                        msg = "producer_exhausted_full_budget"
                        raise ValueError(msg)
                    downstream = run_worker(
                        [
                            str(args.consumer_python.absolute()),
                            str(consumer / "scripts/check_curated.py"),
                            "--worker",
                            "--snapshot-dir",
                            upstream["snapshot_path"],
                            "--workspace",
                            str(workspace / "consumer"),
                        ],
                        consumer,
                        remaining,
                    )
                    upstream.pop("snapshot_path")
                    result = {
                        "profile": profile,
                        "repeat": repeat + 1,
                        "producer": upstream,
                        "consumer": downstream,
                        "seconds": time.monotonic() - started,
                        "peak_rss_mib": max(upstream["peak_rss_mib"], downstream["peak_rss_mib"])
                        + resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                        / (1024**2 if sys.platform == "darwin" else 1024),
                    }
                    report["runs"].append(result)
                    enforce(result)
                    if (
                        upstream["source_commit"] != args.producer_revision
                        or upstream["exporter"]["git_commit"] != args.producer_revision
                    ):
                        msg = "producer_provenance_differs_from_pin"
                        raise ValueError(msg)
                    if previous is not None and identity(result) != previous:
                        msg = "repeated_typed_identity_changed"
                        raise ValueError(msg)
                    previous = identity(result)
                    print(  # noqa: T201 - CLI progress
                        json.dumps(
                            {
                                "profile": profile,
                                "repeat": repeat + 1,
                                "status": "passed",
                                "seconds": result["seconds"],
                                "peak_rss_mib": result["peak_rss_mib"],
                            }
                        ),
                        flush=True,
                    )
                pinned(ROOT, args.producer_revision)
                pinned(consumer, args.consumer_revision)
        report["status"] = "passed"
    finally:
        if report["status"] != "passed":
            report["status"] = "failed"
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
