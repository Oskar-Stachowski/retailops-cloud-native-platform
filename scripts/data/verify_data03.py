# ruff: noqa: INP001 - existing scripts/data namespace
from __future__ import annotations

import argparse
import csv
import json
import resource
import sys
import time
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.data.verify_data01 import legacy_checks, require
from scripts.data.verify_data02 import run_case as source_case
from scripts.data.verify_demand_panel import historical_checks

from data.generator.configuration import DatasetGenerationConfig
from data.generator.manifest_v2 import load_source_manifest_v2


def run_case(root: Path, name: str, config: DatasetGenerationConfig) -> dict:
    result = source_case(root, name, config)
    output = root / name
    reports = {
        kind: json.loads((output / (kind + "_report.json")).read_text(encoding="utf-8"))
        for kind in ("returns", "demand", "pricing", "quality")
    }
    require(all(r["status"] == "passed" for r in reports.values()), "Source gate failed.")
    with (output / "daily_return_cohorts.csv").open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    totals = {}
    for kind in ("history", "return_tail"):
        selected = [r for r in rows if r["snapshot_kind"] == kind]
        totals[kind] = {
            "cohort_count": len(selected),
            "observed_units": sum(int(r["observed_units"]) for r in selected),
            "return_units": sum(int(r["return_units"]) for r in selected),
            "mature_cohorts": sum(r["return_data_complete"] == "true" for r in selected),
            **{
                field: str(sum((Decimal(r[field]) for r in selected), Decimal(0)))
                for field in ("gross_revenue", "refund_amount", "net_revenue")
            },
        }
    require(
        totals["history"]["observed_units"] == totals["return_tail"]["observed_units"]
        and totals["return_tail"]["mature_cohorts"] == totals["return_tail"]["cohort_count"],
        "Return tail changes sales or loses maturity.",
    )
    source = load_source_manifest_v2(output)
    return {
        **result,
        "reports": reports,
        "watermarks": source["watermarks"],
        "cohort_totals": totals,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Bounded DATA-03 chronology/returns acceptance.")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--require-clean", action="store_true")
    args = parser.parse_args()
    started = time.perf_counter()
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    with TemporaryDirectory(prefix="retailops-data03-") as tmp:
        root = Path(tmp)
        cases = [
            run_case(root, profile + "-" + suffix, DatasetGenerationConfig(profile=profile))
            for profile in ("ai-smoke", "ai-temporal-smoke")
            for suffix in ("a", "b")
        ]
        for first, second in ((cases[0], cases[1]), (cases[2], cases[3])):
            for field in (
                "source_id",
                "feature_id",
                "source_artifacts",
                "feature_artifact",
                "dimensions_report",
                "reports",
                "cohort_totals",
                "watermarks",
            ):
                require(first[field] == second[field], "Repeated IDs, bytes or reports changed.")
        bounded = DatasetGenerationConfig(
            profile="ai-smoke", days=5, products=8, stores=3, warehouses=2
        )
        contrasts = [
            run_case(root, name, config)
            for name, config in (
                ("contrast-base", bounded),
                ("contrast-seed", replace(bounded, seed=43)),
                ("contrast-products", replace(bounded, products=9)),
                ("contrast-dates", replace(bounded, end_date=date(2026, 7, 30))),
            )
        ]
        require(
            len({r["source_id"] for r in contrasts})
            == len({r["feature_id"] for r in contrasts})
            == 4,
            "Seed/size/date identity collision.",
        )
        dst = run_case(
            root,
            "spring-dst-all-channels",
            DatasetGenerationConfig(
                profile="ai-smoke",
                days=7,
                products=8,
                stores=8,
                warehouses=2,
                end_date=date(2026, 4, 1),
            ),
        )
        compatibility, historical = legacy_checks(root, baseline), historical_checks(root)
    if args.require_clean:
        require(
            all(r["code_provenance"]["code_state"] == "clean" for r in [*cases, *contrasts, dst]),
            "Acceptance requires committed code.",
        )
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    result = {
        "policy_version": "data03-local-acceptance-1.0.0",
        "status": "passed",
        "cases": cases,
        "contrasts": contrasts,
        "dst_case": dst,
        "repeat_checks": {
            "same_source_feature_ids_and_bytes": True,
            "same_source_reports_and_watermarks": True,
        },
        "seed_size_date_change_ids": True,
        "legacy_compatibility": compatibility,
        "historical_exports": historical,
        "elapsed_seconds": round(time.perf_counter() - started, 4),
        "process_peak_rss_bytes": peak if sys.platform == "darwin" else peak * 1024,
        "measurement_scope": "sequential bounded source/features/validation on macOS; no training or full-profile benchmark",
        "limitations": [
            "remaining source truth isolation pending",
            "inventory_ready=false",
            "forecasting/anomaly/stockout/replay not_ready",
            "no remote Required CI in this acceptance",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("DATA-03 acceptance passed: " + str(args.output))  # noqa: T201 - CLI result


if __name__ == "__main__":
    main()
