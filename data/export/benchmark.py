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

from data.export.parquet import DEFAULT_CHUNK_ROWS, convert
from data.export.policy import GENERATED_ROOT, ROOT, fixture_budget
from data.generator.configuration import DatasetGenerationConfig
from data.generator.main import generate_demo_dataset

POLICY_VERSION = "ai03-format-budget-1.0.0"
MAX_SECONDS = 300
MAX_RSS_MIB = 1024


def measure(profile: str, chunk_rows: int) -> dict:
    GENERATED_ROOT.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="ai03-benchmark-", dir=GENERATED_ROOT) as temporary:
        base = Path(temporary)
        source = base / "csv"
        generate_demo_dataset(source, DatasetGenerationConfig(profile=profile, seed=42))
        generated = time.perf_counter()
        result = convert(source, base / "parquet", chunk_rows=chunk_rows)
        finished = time.perf_counter()
        tables = result["tables"]
        rows = sum(table["row_count"] for table in tables)
        peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return {
            "profile": profile,
            "writer": result["writer"],
            "source_dataset_id": result["source_dataset_id"],
            "source_commit": result["source_commit"],
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
    args = parser.parse_args()
    if args.worker:
        print(json.dumps(measure(args.profiles[0], args.chunk_rows)))  # noqa: T201 - worker protocol
        return
    if args.repeats < 2 or args.max_seconds <= 0 or args.max_rss_mib <= 0:
        parser.error("At least two repeats and positive budgets are required.")
    report = {
        "policy_version": POLICY_VERSION,
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
                identity = (result["source_dataset_id"], result["tables"])
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
