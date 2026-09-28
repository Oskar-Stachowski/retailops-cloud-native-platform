# ruff: noqa: INP001 - existing scripts/data namespace
from __future__ import annotations

import argparse
import json
import os
import resource
import subprocess
import sys
import time
from dataclasses import replace
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.data.verify_data01 import legacy_checks, require
from scripts.data.verify_data03 import run_case as chronology_case
from scripts.data.verify_demand_panel import historical_checks

from data.generator.configuration import DatasetGenerationConfig
from data.generator.feature_admission import admit_feature_source
from ml.features.isolated_runtime import (
    ISOLATION_VERSION,
    WORKER_IMAGE,
    _run,
    verify_runtime_isolation,
)


def run_case(root: Path, name: str, config: DatasetGenerationConfig) -> dict:
    result = chronology_case(root, name, config)
    output = root / name
    reports = {
        kind: json.loads((output / (kind + "_report.json")).read_text(encoding="utf-8"))
        for kind in ("source", "realism")
    }
    require(reports["source"]["source_ready"], "Final source acceptance failed.")
    return {**result, **reports, "source_ready": True}


def cli_checks(root: Path, source: Path) -> list[dict]:
    features = root / "cli-features"
    commands = [
        [sys.executable, "-m", "data.generator.manifest_v2", "--data-dir", str(source)],
        [
            sys.executable,
            "-m",
            "ml.features.demand_forecast",
            "--profile",
            "ai-smoke",
            "--days",
            "5",
            "--products",
            "8",
            "--stores",
            "3",
            "--warehouses",
            "2",
            "--source-dir",
            str(source),
            "--output-dir",
            str(features),
        ],
        [sys.executable, "-m", "ml.features.identity", "--data-dir", str(features)],
    ]
    result = []
    for command in commands:
        process = subprocess.run(command, capture_output=True, text=True, check=False, timeout=60)  # noqa: S603 - fixed CLI
        require(process.returncode == 0, "Passing CLI failed: " + process.stderr)
        result.append({"command": command, "expected_exit": 0, "actual_exit": process.returncode})
    for path, command in (
        (features / "features.csv", commands[2]),
        (source / "sales.csv", commands[0]),
    ):
        original = path.read_bytes()
        path.write_bytes(original + b"corrupted\n")
        try:
            process = subprocess.run(  # noqa: S603 - fixed CLI
                command, capture_output=True, text=True, check=False, timeout=60
            )
            require(process.returncode == 1, "Corrupted artifact was accepted by CLI.")
            result.append(
                {
                    "command": command,
                    "negative": "corrupted byte",
                    "expected_exit": 1,
                    "actual_exit": process.returncode,
                }
            )
        finally:
            path.write_bytes(original)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Final bounded source/facts runtime acceptance.")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--require-clean", action="store_true")
    args = parser.parse_args()
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    started = time.perf_counter()
    with TemporaryDirectory(prefix="retailops-data05-") as tmp:
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
                "source",
                "realism",
                "watermarks",
            ):
                require(first[field] == second[field], "Repeat IDs/bytes/reports changed.")
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
            replace(bounded, days=7, stores=8, end_date=date(2026, 4, 1)),
        )
        source = root / "contrast-base"
        os.environ["RETAILOPS_TRUTH_CANARY"] = "private-source-not-a-feature"
        isolation = verify_runtime_isolation(source)
        require(all(isolation.values()), "Actual worker isolation failed.")
        facts, _ = admit_feature_source(source, bounded)
        negatives = {}
        for name in ("daily_demand_truth", "inventory_snapshots"):
            bad = {**facts, "tables": {**facts["tables"], name: []}}
            try:
                _run(bad, "ml.features.worker")
            except RuntimeError as error:
                require(
                    "Feature input rejected" in str(error),
                    "Negative runtime failed for another reason.",
                )
                negatives[name] = "rejected_by_isolated_worker"
            else:
                msg = "Truth/inventory reached the feature runtime."
                raise ValueError(msg)
        compatibility, historical = legacy_checks(root, baseline), historical_checks(root)
        cli = cli_checks(root, source)
    if args.require_clean:
        require(
            all(r["code_provenance"]["code_state"] == "clean" for r in [*cases, *contrasts, dst]),
            "Acceptance requires committed source code.",
        )
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    result = {
        "policy_version": "data05-local-acceptance-1.0.0",
        "status": "passed",
        "cases": cases,
        "contrasts": contrasts,
        "dst_case": dst,
        "repeat_checks": {"same_source_feature_ids_bytes_reports": True},
        "seed_size_date_change_ids": True,
        "legacy_compatibility": compatibility,
        "historical_exports": historical,
        "cli": cli,
        "runtime": {
            "policy_version": ISOLATION_VERSION,
            "image": WORKER_IMAGE,
            "probes": isolation,
            "negative_inputs": negatives,
            "supervisor": "trusted source owner validates and projects facts; only worker is the isolated runtime",
        },
        "elapsed_seconds": round(time.perf_counter() - started, 4),
        "process_peak_rss_bytes": peak if sys.platform == "darwin" else peak * 1024,
        "measurement_scope": "sequential bounded supervisor; container RSS not measured, worker memory limit 256 MiB",
        "limitations": [
            "inventory_ready=false",
            "forecasting/anomaly/stockout/replay not_ready",
            "no training/full-profile benchmark",
            "no remote Required CI in this acceptance",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("DATA-05 acceptance passed: " + str(args.output))  # noqa: T201 - CLI result


if __name__ == "__main__":
    main()
