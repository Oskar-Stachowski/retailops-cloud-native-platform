"""Measure complete smoke generation + Parquet/parity in fresh bounded processes."""

from __future__ import annotations

import argparse
import json
import platform
import resource
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pyarrow as pa

from data.export.ai_snapshot import export_snapshot
from data.export.parquet import DEFAULT_CHUNK_ROWS, convert
from data.export.policy import GENERATED_ROOT, ROOT, fixture_budget
from data.export.snapshot_contract import MANIFEST_NAME
from data.generator.configuration import DatasetGenerationConfig
from data.generator.identity import file_sha256
from data.generator.main import generate_demo_dataset
from data.generator.manifest_v2 import MANIFEST_V2_FILENAME

POLICY_VERSION = "ai03-format-budget-1.0.0"
MAX_SECONDS = 300
MAX_RSS_MIB = 1024


def measure(profile: str, chunk_rows: int, *, snapshot: bool = False) -> dict:
    GENERATED_ROOT.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="ai03-benchmark-", dir=GENERATED_ROOT) as temporary:
        base = Path(temporary)
        source = base / "csv"
        generate_demo_dataset(source, DatasetGenerationConfig(profile=profile, seed=42))
        generated = time.perf_counter()
        publication = None
        if snapshot:
            dataset_id = json.loads((source / MANIFEST_V2_FILENAME).read_text())["dataset_id"]
            source_hashes = {path.name: file_sha256(path) for path in source.iterdir()}
            publication = export_snapshot(
                source, dataset_id, base / "snapshots", chunk_rows=chunk_rows
            )
            result = publication["manifest"]
            first_bytes = {
                path.relative_to(publication["path"]).as_posix(): file_sha256(path)
                for path in Path(publication["path"]).rglob("*")
                if path.is_file()
            }
            repeated = export_snapshot(
                source, dataset_id, base / "snapshots", chunk_rows=chunk_rows
            )
            final_bytes = {
                path.relative_to(publication["path"]).as_posix(): file_sha256(path)
                for path in Path(publication["path"]).rglob("*")
                if path.is_file()
            }
            if (
                repeated["publication"] != "reused"
                or repeated["manifest"] != result
                or first_bytes != final_bytes
                or source_hashes != {path.name: file_sha256(path) for path in source.iterdir()}
            ):
                msg = "Snapshot re-export changed source or published bytes."
                raise ValueError(msg)
        else:
            result = convert(source, base / "parquet", chunk_rows=chunk_rows)
        finished = time.perf_counter()
        tables = result["tables"]
        rows = sum(table["row_count"] for table in tables)
        peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return {
            "profile": profile,
            "writer": result["exporter"] if snapshot else result["writer"],
            "source_dataset_id": result["source_dataset_id"],
            "source_commit": result["source"]["provenance"]["git_commit"]
            if snapshot
            else result["source_commit"],
            "snapshot_id": result.get("snapshot_id"),
            "snapshot_ready": result.get("snapshot_ready", False),
            "idempotent_reexport": "passed" if snapshot else "not_applicable",
            "manifest_sha256": file_sha256(Path(publication["path"]) / MANIFEST_NAME)
            if publication
            else None,
            "seed": 42,
            "end_date": "2026-07-31",
            "rows": rows,
            "table_count": len(tables),
            "generation_csv_seconds": generated - started,
            "parquet_and_parity_seconds": finished - generated,
            "total_seconds": finished - started,
            "rows_per_second": rows / (finished - started),
            "peak_rss_mib": peak_rss / (1024 * 1024 if sys.platform == "darwin" else 1024),
            "csv_bytes": sum(path.stat().st_size for path in source.glob("*.csv")),
            "parquet_bytes": sum(file["bytes"] for table in tables for file in table["files"]),
            "chunk_rows": chunk_rows,
            "parity": "passed",
            "tables": [
                {
                    key: table[key]
                    for key in ("table", "row_count", "content_sha256", "data_class", "date_range")
                }
                for table in tables
            ],
        }


def enforce_limits(result: dict, max_seconds: float, max_rss_mib: float) -> None:
    if result["total_seconds"] > max_seconds or result["peak_rss_mib"] > max_rss_mib:
        msg = "Complete profile exceeded its declared time or RSS budget."
        raise ValueError(msg)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AI 03.1 complete profile performance and repeatability gate."
    )
    parser.add_argument(
        "--profiles",
        nargs="+",
        choices=("ai-smoke", "ai-temporal-smoke"),
        default=["ai-smoke", "ai-temporal-smoke"],
    )
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--chunk-rows", type=int, default=DEFAULT_CHUNK_ROWS)
    parser.add_argument("--max-seconds", type=float, default=MAX_SECONDS)
    parser.add_argument("--max-rss-mib", type=float, default=MAX_RSS_MIB)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "ci-cd/reports/data/ai03-benchmark.json"
    )
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument(
        "--snapshot",
        action="store_true",
        help="Measure qualified immutable export and unchanged re-export.",
    )
    args = parser.parse_args()
    if args.worker:
        print(json.dumps(measure(args.profiles[0], args.chunk_rows, snapshot=args.snapshot)))  # noqa: T201 - worker protocol
        return
    if args.repeats < 2 or args.max_seconds <= 0 or args.max_rss_mib <= 0:
        parser.error("At least two repeats and positive budgets are required.")
    report = {
        "policy_version": "ai03-snapshot-budget-1.0.0" if args.snapshot else POLICY_VERSION,
        "pipeline": "generate/qualify/export/verify/reexport"
        if args.snapshot
        else "generate/format/parity",
        "status": "running",
        "limits": {
            "max_seconds_per_profile": args.max_seconds,
            "max_rss_mib_per_profile": args.max_rss_mib,
        },
        "environment": {
            "python": platform.python_version(),
            "pyarrow": pa.__version__,
            "platform": platform.platform(),
            "architecture": platform.machine(),
        },
        "fixture_budget": fixture_budget(),
        "runs": [],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        for profile in args.profiles:
            previous = None
            for _repeat in range(args.repeats):
                started = time.perf_counter()
                process = subprocess.run(  # noqa: S603 - current interpreter, fixed module, validated profiles, no shell
                    [
                        sys.executable,
                        "-m",
                        "data.export.benchmark",
                        "--worker",
                        "--profiles",
                        profile,
                        "--chunk-rows",
                        str(args.chunk_rows),
                        *(["--snapshot"] if args.snapshot else []),
                    ],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=args.max_seconds,
                )
                result = json.loads(process.stdout)
                result["process_wall_seconds"] = time.perf_counter() - started
                report["runs"].append(result)
                enforce_limits(result, args.max_seconds, args.max_rss_mib)
                identity = (result["source_dataset_id"], result["snapshot_id"], result["tables"])
                if previous is not None and identity != previous:
                    msg = "Repeated profile changed source identity or typed table content."
                    raise ValueError(msg)
                previous = identity
        report["status"] = "passed"
    finally:
        if report["status"] != "passed":
            report["status"] = "failed"
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(  # noqa: T201 - CLI result
        json.dumps(
            {"status": report["status"], "runs": len(report["runs"]), "evidence": str(args.output)}
        )
    )


if __name__ == "__main__":
    main()
