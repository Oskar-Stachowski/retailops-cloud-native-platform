# ruff: noqa: INP001 - CLI follows the existing scripts/data namespace layout
from __future__ import annotations

import argparse
import json
import resource
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory

from data.generator.configuration import DatasetGenerationConfig
from data.generator.identity import file_sha256
from data.generator.main import generate_demo_dataset
from data.generator.manifest_v2 import load_source_manifest_v2
from ml.features.demand_forecast import (
    DemandFeatureGenerationConfig,
    generate_demand_feature_dataset,
)
from ml.features.identity import load_feature_identity_manifest


def require(condition: bool, message: str) -> None:  # noqa: FBT001 - assertion condition, not a mode switch
    if not condition:
        raise ValueError(message)


def run_case(root: Path, name: str, config: DatasetGenerationConfig) -> dict[str, object]:
    output = root / name
    started = time.perf_counter()
    generate_demo_dataset(output, config)
    source = load_source_manifest_v2(output)
    generate_demand_feature_dataset(
        DemandFeatureGenerationConfig(dataset=config, output_dir=output / "features", source_dir=output)
    )
    features = load_feature_identity_manifest(output / "features")
    require(
        features["descriptor"]["parent_ids"] == [source["dataset_id"]], "Source lineage mismatch."
    )
    return {
        "case": name,
        "source_id": source["dataset_id"],
        "feature_id": features["dataset_id"],
        "resolved_parameters": source["descriptor"]["resolved_parameters"],
        "code_provenance": source["provenance"],
        "source_artifacts": source["artifacts"],
        "feature_artifact": features["artifact"],
        "watermarks": source["watermarks"],
        "readiness": source["readiness"],
        "seconds": round(time.perf_counter() - started, 4),
    }


def repeated_checks(first: dict, second: dict) -> dict[str, object]:
    require(first["source_id"] == second["source_id"], "Repeated source identity changed.")
    require(first["feature_id"] == second["feature_id"], "Repeated feature identity changed.")
    require(
        first["source_artifacts"] == second["source_artifacts"], "Repeated source bytes changed."
    )
    require(
        first["feature_artifact"] == second["feature_artifact"], "Repeated feature bytes changed."
    )
    return {
        "case": first["case"].removesuffix("-a"),
        "same_source_id": True,
        "same_feature_id": True,
        "same_source_bytes": True,
        "same_feature_bytes": True,
    }


def legacy_checks(root: Path, baseline: dict) -> dict[str, object]:
    outcomes = {}
    for name, config in [
        ("demo", DatasetGenerationConfig()),
        (
            "small",
            DatasetGenerationConfig(profile="small", days=14, products=20, stores=4, warehouses=3),
        ),
    ]:
        output = root / ("legacy-" + name)
        generate_demo_dataset(output, config)
        hashes = {path.name: file_sha256(path) for path in sorted(output.glob("*.csv"))}
        require(hashes == baseline[name], "Legacy CSV byte compatibility failed.")
        outcomes[name + "_csv_count"] = len(hashes)
    repo_root = Path(__file__).resolve().parents[2]
    hashes = {name: file_sha256(repo_root / name) for name in baseline["tracked_demo"]}
    require(hashes == baseline["tracked_demo"], "Tracked demo files changed.")
    outcomes["tracked_demo_files_unchanged"] = len(hashes)
    return outcomes


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bounded DATA-01 acceptance; all generated data stays in temp."
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--require-clean", action="store_true")
    args = parser.parse_args()
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    started = time.perf_counter()
    with TemporaryDirectory(prefix="retailops-data01-") as temporary:
        root = Path(temporary)
        cases = [
            run_case(root, profile + "-" + suffix, DatasetGenerationConfig(profile=profile))
            for profile in ("ai-smoke", "ai-temporal-smoke")
            for suffix in ("a", "b")
        ]
        checks = [repeated_checks(cases[0], cases[1]), repeated_checks(cases[2], cases[3])]
        contrast = [
            run_case(
                root, f"small-{count}", DatasetGenerationConfig(profile="small", products=count)
            )
            for count in (100, 20)
        ]
        require(contrast[0]["source_id"] != contrast[1]["source_id"], "100/20 source collision.")
        require(contrast[0]["feature_id"] != contrast[1]["feature_id"], "100/20 feature collision.")
        compatibility = legacy_checks(root, baseline)
    if args.require_clean:
        require(
            all(case["code_provenance"]["code_state"] == "clean" for case in cases + contrast),
            "Acceptance needs committed generator code.",
        )
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    result = {
        "policy_version": "data01-local-acceptance-1.0.0",
        "status": "passed",
        "cases": cases + contrast,
        "repeat_checks": checks,
        "contrast_100_20": {"different_source_ids": True, "different_feature_ids": True},
        "legacy_compatibility": compatibility,
        "elapsed_seconds": round(time.perf_counter() - started, 4),
        "process_peak_rss_bytes": peak if sys.platform == "darwin" else peak * 1024,
        "measurement_scope": "single sequential acceptance process; source, features, validation; no training or CI benchmark",
        "limitations": [
            "legacy sparse panel and business simulation",
            "inventory_ready=false",
            "AI 03 source readiness not established",
            "no remote Required CI in this acceptance",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("DATA-01 acceptance passed; report: " + str(args.output))  # noqa: T201 - CLI result


if __name__ == "__main__":
    main()
