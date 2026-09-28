"""Manual writer scale benchmark; this is not a qualified AI training dataset."""

from __future__ import annotations

import argparse
import csv
import json
import platform
import resource
import sys
import tempfile
import time
from datetime import date, timedelta
from pathlib import Path

from data.export.hashing import ContentHash
from data.export.parquet import DEFAULT_CHUNK_ROWS, csv_chunks, write_table
from data.export.policy import GENERATED_ROOT
from data.generator.csv_writer import source_columns
from data.generator.identity import file_sha256, json_sha256


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Measure bounded Parquet writes at an explicit row count."
    )
    parser.add_argument("--rows", type=int, required=True)
    parser.add_argument("--chunk-rows", type=int, default=DEFAULT_CHUNK_ROWS)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.rows < 1:
        parser.error("Rows must be positive.")
    GENERATED_ROOT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ai03-scale-", dir=GENERATED_ROOT) as temporary:
        base = Path(temporary)
        table = "daily_demand_versions"
        columns = source_columns(table, "ai-smoke")
        source = base / "versions.csv"
        with source.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=columns)
            writer.writeheader()
            for index in range(args.rows):
                day = date(2024, 1, 1) + timedelta(days=index // 4000)
                writer.writerow(
                    {
                        "id": str(index),
                        "observation_id": str(index),
                        "business_date": day.isoformat(),
                        "product_id": "benchmark-product",
                        "selling_location_id": "benchmark-location",
                        "channel": "store",
                        "version": "1",
                        "observed_units": "0",
                        "observation_status": "observed_zero",
                        "available_at": (day + timedelta(days=1)).isoformat() + "T00:00:00Z",
                        "history_policy_version": "observed-quantity-history-1.0.0",
                    }
                )
        with ContentHash(columns, base) as content:
            for rows in csv_chunks(source, columns, args.chunk_rows):
                content.add(rows)
            expected_hash = content.digest()
        artifact = {
            "table": table,
            "data_class": "source_observation",
            "row_count": args.rows,
            "content_sha256": expected_hash,
            "grain": ["observation_id", "version"],
            "date_range": None,
            "field_ranges": {},
        }
        started = time.perf_counter()
        result = write_table(source, base, artifact, "ai-smoke", chunk_rows=args.chunk_rows)
        seconds = time.perf_counter() - started
        peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        report = {
            "kind": "writer_scale_only",
            "qualified_source": False,
            "status": "passed",
            "rows": args.rows,
            "chunk_rows": args.chunk_rows,
            "parity": "passed",
            "write_and_verify_seconds": seconds,
            "rows_per_second": args.rows / seconds,
            "peak_rss_mib": peak_rss / (1024 * 1024 if sys.platform == "darwin" else 1024),
            "csv_bytes": source.stat().st_size,
            "parquet_bytes": sum(f["bytes"] for f in result["files"]),
            "parquet_files": len(result["files"]),
            "content_sha256": expected_hash,
            "python": platform.python_version(),
            "platform": platform.platform(),
            "code_sha256": json_sha256(
                {p.name: file_sha256(p) for p in sorted(Path(__file__).parent.glob("*.py"))}
            ),
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report))  # noqa: T201 - benchmark result


if __name__ == "__main__":
    main()
