# ruff: noqa: INP001 - existing scripts/data namespace
from __future__ import annotations

import argparse
import csv
import json
import resource
import sys
import time
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from scripts.data.verify_data01 import legacy_checks, require
from scripts.data.verify_data02 import run_case as source_case

from data.generator.configuration import DatasetGenerationConfig
from data.generator.manifest_v2 import load_source_manifest_v2
from ml.features.identity import load_feature_identity_manifest


def run_case(root: Path, name: str, config: DatasetGenerationConfig) -> dict:
    result = source_case(root, name, config)
    path = root / name
    report = json.loads((path / "demand_report.json").read_text(encoding="utf-8"))
    require(
        report["status"] == "passed" and report["daily_panel_coverage_percent"] == 100,
        "Daily panel gate failed.",
    )
    require(
        json.loads((path / "quality_report.json").read_text(encoding="utf-8"))["status"]
        == "passed",
        "Legacy structural gate failed.",
    )
    with (path / "order_items.csv").open(newline="", encoding="utf-8") as stream:
        items = list(csv.DictReader(stream))
    require(
        len({(r["order_id"], r["product_id"]) for r in items}) == len(items), "Repeated basket SKU."
    )
    features = load_feature_identity_manifest(path / "features")
    require(
        features["descriptor"]["schema_version"] == "3.0" and features["complete_daily_panel"],
        "AI feature contract/coverage failed.",
    )
    return {
        **result,
        "demand_report": report,
        "feature_schema_version": "3.0",
        "basket_line_count": len(items),
        "duplicate_basket_skus": 0,
    }


def historical_checks(root: Path) -> dict:
    result = {}
    repo = Path(__file__).resolve().parents[2]
    for suffix in ("0", "1", "2"):
        directory = root / ("historical-2." + suffix)
        directory.mkdir()
        with ZipFile(
            repo / "services/api/tests/fixtures" / ("source_manifest_v2_" + suffix + ".zip")
        ) as archive:
            for name in archive.namelist():
                require(Path(name).name == name, "Archive has a nested path.")
                (directory / name).write_bytes(archive.read(name))
        original = json.loads((directory / "dataset_manifest.v2.json").read_text(encoding="utf-8"))
        source, features = (
            load_source_manifest_v2(directory),
            load_feature_identity_manifest(directory),
        )
        original_features = json.loads(
            (directory / "feature_identity_manifest.json").read_text(encoding="utf-8")
        )
        require(
            source["dataset_id"] == original["dataset_id"]
            and features["dataset_id"] == original_features["dataset_id"]
            and features["descriptor"]["parent_ids"] == [source["dataset_id"]],
            "Historical IDs/parent changed.",
        )
        result[source["schema_version"]] = {
            "source_id": source["dataset_id"],
            "feature_id": features["dataset_id"],
            "identity_and_parent_unchanged": True,
        }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Bounded AI daily demand/panel/basket acceptance.")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--require-clean", action="store_true")
    args = parser.parse_args()
    started = time.perf_counter()
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    with TemporaryDirectory(prefix="retailops-demand-") as tmp:
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
                "demand_report",
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
            )
        ]
        require(
            len({r["source_id"] for r in contrasts})
            == len({r["feature_id"] for r in contrasts})
            == 3,
            "Seed/size identity collision.",
        )
        compatibility, historical = legacy_checks(root, baseline), historical_checks(root)
    if args.require_clean:
        require(
            all(r["code_provenance"]["code_state"] == "clean" for r in [*cases, *contrasts]),
            "Acceptance requires committed code.",
        )
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    result = {
        "policy_version": "daily-demand-local-acceptance-1.0.0",
        "status": "passed",
        "cases": cases,
        "contrasts": contrasts,
        "repeat_checks": {
            "same_source_feature_ids_and_bytes": True,
            "same_dimensions_demand_reports": True,
        },
        "seed_and_size_change_ids": True,
        "legacy_compatibility": compatibility,
        "historical_exports": historical,
        "elapsed_seconds": round(time.perf_counter() - started, 4),
        "process_peak_rss_bytes": peak if sys.platform == "darwin" else peak * 1024,
        "measurement_scope": "sequential bounded source/features/validation on macOS; no training or full-profile benchmark",
        "limitations": [
            "return windows, tail and reconciliation pending",
            "remaining source truth isolation pending",
            "inventory_ready=false",
            "forecasting/anomaly/stockout/replay not_ready",
            "no remote Required CI in this acceptance",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("Daily demand acceptance passed: " + str(args.output))  # noqa: T201 - CLI output


if __name__ == "__main__":
    main()
