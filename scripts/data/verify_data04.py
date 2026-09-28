# ruff: noqa: INP001 - CLI follows the existing scripts/data namespace layout
from __future__ import annotations

import argparse
import copy
import csv
import json
import resource
import sys
import time
from collections import Counter
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from scripts.data.verify_data01 import legacy_checks, require
from scripts.data.verify_data02 import run_case as dimension_case

from data.generator.business_calendar import utc_midnight
from data.generator.common import deterministic_uuid, money
from data.generator.configuration import DatasetGenerationConfig
from data.generator.csv_writer import source_table_order
from data.generator.manifest_v2 import load_source_manifest_v2
from data.generator.price_resolver import PriceResolver
from data.generator.pricing_schema import PRICING_COLUMNS
from ml.features.demand_forecast import FEATURE_COLUMNS
from ml.features.identity import load_feature_identity_manifest


def run_case(root: Path, name: str, config: DatasetGenerationConfig) -> dict:
    case = dimension_case(root, name, config)
    output = root / name
    tables = {}
    for table in source_table_order(config.profile):
        with (output / (table + ".csv")).open(newline="", encoding="utf-8") as stream:
            tables[table] = list(csv.DictReader(stream))
    pricing = json.loads((output / "pricing_report.json").read_text(encoding="utf-8"))
    require(
        pricing["status"] == "passed" and pricing["price_coverage_percent"] == 100,
        "Pricing gate failed.",
    )
    require(
        json.loads((output / "quality_report.json").read_text(encoding="utf-8"))["status"]
        == "passed",
        "Legacy structural checks failed.",
    )
    promotions = {r["id"]: r for r in tables["promotion_plans"]}
    counts = Counter(
        promotions[r["promotion_plan_id"]]["promotion_type"]
        for r in tables["sale_price_references"]
        if r["promotion_plan_id"]
    )
    baseline = next(r for r in tables["price_plans"] if r["scope"] == "global")
    pair = tables["channel_assignments"][0]
    start = date.fromisoformat(case["resolved_parameters"]["start_date"])
    target = (start + timedelta(days=3)).isoformat()
    cutoff = utc_midnight(start + timedelta(days=1))
    resolver = PriceResolver(tables)
    before = resolver.resolve(
        baseline["product_id"], pair["selling_location_id"], pair["channel"], target, cutoff
    )
    corrected = copy.deepcopy(tables)
    revision = dict(
        baseline,
        id=deterministic_uuid("acceptance_revision", name),
        version="99",
        price=money(Decimal(baseline["price"]) * Decimal("1.07")),
        known_at=utc_midnight(start + timedelta(days=2)),
        available_at=utc_midnight(start + timedelta(days=2)),
    )
    corrected["price_plans"].append(revision)
    after_append = PriceResolver(corrected).resolve(
        baseline["product_id"], pair["selling_location_id"], pair["channel"], target, cutoff
    )
    require(before == after_append, "Late revision rewrote earlier plan knowledge.")
    later = PriceResolver(corrected).resolve(
        baseline["product_id"],
        pair["selling_location_id"],
        pair["channel"],
        target,
        revision["available_at"],
    )
    require(later.price_plan_id == revision["id"], "Known revision was not selected.")
    end = date.fromisoformat(case["resolved_parameters"]["end_date"])
    future = resolver.resolve(
        baseline["product_id"],
        pair["selling_location_id"],
        pair["channel"],
        (end + timedelta(days=14)).isoformat(),
        utc_midnight(end - timedelta(days=1)),
    )
    return {
        **case,
        "pricing_report": pricing,
        "pricing_table_counts": {key: len(tables[key]) for key in PRICING_COLUMNS},
        "applied_promotion_type_counts": dict(sorted(counts.items())),
        "nonpromoted_product_count": len(
            {r["id"] for r in tables["products"]} - {r["product_id"] for r in promotions.values()}
        ),
        "known_plan_checks": {
            "late_revision_preserves_earlier_quote": True,
            "later_cutoff_selects_revision": True,
            "future_plan_known_before_target": True,
            "future_price_plan_id": future.price_plan_id,
        },
    }


def historical_checks(root: Path, repo_root: Path) -> dict:
    result = {}
    for version, filename in (
        ("2.0.0", "source_manifest_v2_0.zip"),
        ("2.1.0", "source_manifest_v2_1.zip"),
    ):
        output = root / ("historical-" + version)
        output.mkdir()
        with ZipFile(repo_root / "services/api/tests/fixtures" / filename) as fixture:
            for name in fixture.namelist():
                require(Path(name).name == name, "Fixture has a nested path.")
                (output / name).write_bytes(fixture.read(name))
        original_source = json.loads(
            (output / "dataset_manifest.v2.json").read_text(encoding="utf-8")
        )
        original_features = json.loads(
            (output / "feature_identity_manifest.json").read_text(encoding="utf-8")
        )
        source = load_source_manifest_v2(output)
        features = load_feature_identity_manifest(output, FEATURE_COLUMNS)
        require(
            source["schema_version"] == version
            and source["dataset_id"] == original_source["dataset_id"]
            and features["dataset_id"] == original_features["dataset_id"]
            and features["descriptor"]["parent_ids"] == [source["dataset_id"]],
            "Historical identity or parent changed.",
        )
        result[version] = {
            "source_id": source["dataset_id"],
            "feature_id": features["dataset_id"],
            "readable_identity_and_parent_unchanged": True,
        }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bounded DATA-04 source/pricing/feature acceptance."
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--require-clean", action="store_true")
    args = parser.parse_args()
    started = time.perf_counter()
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    with TemporaryDirectory(prefix="retailops-data04-") as temporary:
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
                "pricing_report",
            ):
                require(
                    first[key] == second[key],
                    "Repeated source/feature identity, bytes or gates changed.",
                )
        require(
            all(
                cases[0]["applied_promotion_type_counts"].get(kind, 0) > 0
                for kind in ("percentage", "bundle", "clearance", "seasonal")
            ),
            "Smoke does not exercise all promotion types.",
        )
        compatibility = legacy_checks(root, baseline)
        historical = historical_checks(root, Path(__file__).resolve().parents[2])
    if args.require_clean:
        require(
            all(case["code_provenance"]["code_state"] == "clean" for case in cases),
            "Acceptance requires committed generator code.",
        )
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    result = {
        "policy_version": "data04-local-acceptance-1.0.0",
        "status": "passed",
        "cases": cases,
        "repeat_checks": {
            "same_source_feature_ids_and_bytes": True,
            "same_dimensions_pricing_reports": True,
        },
        "legacy_compatibility": compatibility,
        "historical_exports": historical,
        "elapsed_seconds": round(time.perf_counter() - started, 4),
        "process_peak_rss_bytes": peak if sys.platform == "darwin" else peak * 1024,
        "measurement_scope": "single sequential bounded source/features/validation process; no training or full-profile benchmark",
        "limitations": [
            "sparse demand panel",
            "legacy demand formula and baskets",
            "chronology and returns pending",
            "remaining truth separation pending",
            "inventory_ready=false",
            "no remote Required CI in this acceptance",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("DATA-04 acceptance passed; report: " + str(args.output))  # noqa: T201 - CLI result


if __name__ == "__main__":
    main()
