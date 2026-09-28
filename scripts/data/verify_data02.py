# ruff: noqa: INP001 - CLI follows the existing scripts/data namespace layout
from __future__ import annotations

import argparse
import json
import resource
import sys
import time
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from scripts.data.verify_data01 import legacy_checks, require

from data.generator.configuration import DatasetGenerationConfig
from data.generator.main import generate_demo_dataset
from data.generator.manifest_v2 import load_source_manifest_v2
from ml.features.demand_forecast import (
    FEATURE_COLUMNS,
    DemandFeatureGenerationConfig,
    generate_demand_feature_dataset,
)
from ml.features.identity import load_feature_identity_manifest


def run_case(root: Path, name: str, config: DatasetGenerationConfig) -> dict:
    output = root / name
    started = time.perf_counter()
    generate_demo_dataset(output, config)
    source = load_source_manifest_v2(output)
    generate_demand_feature_dataset(
        DemandFeatureGenerationConfig(dataset=config, output_dir=output / "features")
    )
    features = load_feature_identity_manifest(output / "features", FEATURE_COLUMNS)
    require(
        features["descriptor"]["parent_ids"] == [source["dataset_id"]], "Feature parent mismatch."
    )
    dimensions = json.loads((output / "dimensions_report.json").read_text(encoding="utf-8"))
    require(dimensions["status"] == "passed", "Dimension gate failed.")
    return {
        "case": name,
        "source_id": source["dataset_id"],
        "feature_id": features["dataset_id"],
        "source_schema_version": source["schema_version"],
        "versions": source["descriptor"]["versions"],
        "resolved_parameters": source["descriptor"]["resolved_parameters"],
        "code_provenance": source["provenance"],
        "source_artifacts": [
            {key: artifact[key] for key in ("table", "row_count", "sha256", "content_sha256")}
            for artifact in source["artifacts"]
        ],
        "feature_artifact": {
            **features["artifact"],
            "row_count": features["descriptor"]["row_count"],
            "content_sha256": features["descriptor"]["content_sha256"],
        },
        "dimensions_report": dimensions,
        "readiness": source["readiness"],
        "seconds": round(time.perf_counter() - started, 4),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bounded DATA-02 acceptance; generated files stay in temp."
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--require-clean", action="store_true")
    args = parser.parse_args()
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    started = time.perf_counter()
    repo_root = Path(__file__).resolve().parents[2]
    with TemporaryDirectory(prefix="retailops-data02-") as temporary:
        root = Path(temporary)
        cases = [
            run_case(root, profile + "-" + suffix, DatasetGenerationConfig(profile=profile))
            for profile in ("ai-smoke", "ai-temporal-smoke")
            for suffix in ("a", "b")
        ]
        for first, second in ((cases[0], cases[1]), (cases[2], cases[3])):
            for key in (
                "source_id",
                "feature_id",
                "source_artifacts",
                "feature_artifact",
                "dimensions_report",
            ):
                require(first[key] == second[key], "Repeat identity/bytes/gates changed.")
        cases.extend(
            [
                run_case(
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
                ),
                run_case(
                    root,
                    "winter-holidays",
                    DatasetGenerationConfig(
                        profile="ai-smoke",
                        days=15,
                        products=8,
                        stores=3,
                        warehouses=2,
                        end_date=date(2027, 1, 3),
                    ),
                ),
            ]
        )
        compatibility = legacy_checks(root, baseline)
        historical = root / "historical-2.0"
        historical.mkdir()
        with ZipFile(repo_root / "services/api/tests/fixtures/source_manifest_v2_0.zip") as fixture:
            for name in fixture.namelist():
                require(Path(name).name == name, "Fixture contains a nested path.")
                (historical / name).write_bytes(fixture.read(name))
        old = load_source_manifest_v2(historical)
        old_features = load_feature_identity_manifest(historical, FEATURE_COLUMNS)
        require(
            old_features["dataset_id"]
            == "features-sha256-bdb259d15fd67e0af15dbce1465ff480ae93421125bde83231b0bf5730a9db13",
            "Historical feature identity changed.",
        )
        require(
            old_features["descriptor"]["parent_ids"] == [old["dataset_id"]],
            "Historical feature parent changed.",
        )
        require(old["schema_version"] == "2.0.0", "Historical schema changed.")
        require(
            old["dataset_id"]
            == "source-sha256-b4d2a6cf560129ce23374841340e65897a7b09becbe4749e1352c3f150bc1309",
            "Historical identity changed.",
        )
    if args.require_clean:
        require(
            all(case["code_provenance"]["code_state"] == "clean" for case in cases),
            "Acceptance requires committed generator code.",
        )
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    result = {
        "policy_version": "data02-local-acceptance-1.0.0",
        "status": "passed",
        "cases": cases,
        "repeat_checks": {
            "same_source_and_feature_ids": True,
            "same_source_and_feature_bytes": True,
            "same_dimension_reports": True,
        },
        "legacy_compatibility": compatibility,
        "historical_source_2_0": {
            "readable": True,
            "identity_unchanged": True,
            "dataset_id": old["dataset_id"],
            "feature_id": old_features["dataset_id"],
            "feature_identity_and_parent_unchanged": True,
        },
        "elapsed_seconds": round(time.perf_counter() - started, 4),
        "process_peak_rss_bytes": peak if sys.platform == "darwin" else peak * 1024,
        "measurement_scope": "single sequential source/features/validation process; bounded profiles; no training benchmark",
        "limitations": [
            "sparse observation panel",
            "legacy pricing and baskets",
            "inventory_ready=false",
            "truth separation pending",
            "no remote CI in this acceptance",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("DATA-02 acceptance passed; report: " + str(args.output))  # noqa: T201 - CLI result


if __name__ == "__main__":
    main()
