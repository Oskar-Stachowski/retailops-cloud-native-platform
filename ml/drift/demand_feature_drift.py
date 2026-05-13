from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path

from data.generator.main import DatasetGenerationConfig, build_dataset
from data.generator.manifest import GENERATOR_VERSION
from ml.features.demand_forecast import (
    DATASET_NAME,
    build_demand_feature_rows,
)

DRIFT_REPORT_FILENAME = "drift_report.json"
DRIFT_SUMMARY_FILENAME = "drift_summary.md"
DEFAULT_REFERENCE_SEED = 42
DEFAULT_CURRENT_SEED = 43
DEFAULT_WARNING_THRESHOLD = Decimal("0.1000")
DEFAULT_FAILURE_THRESHOLD = Decimal("0.2500")
NUMERIC_FEATURES = [
    "units_sold",
    "latent_units_demand",
    "sales_revenue",
    "unit_price",
    "discount_percent",
    "inventory_on_hand",
    "inventory_reserved",
]
CATEGORICAL_FEATURES = [
    "channel",
    "promotion_active",
    "promotion_type",
    "stockout_flag",
    "category",
    "brand",
    "product_status",
    "day_of_week",
    "is_weekend",
    "month",
    "data_quality_status",
]


@dataclass(frozen=True)
class DemandFeatureDriftConfig:
    dataset: DatasetGenerationConfig = field(
        default_factory=lambda: DatasetGenerationConfig(profile="demo"),
    )
    reference_seed: int = DEFAULT_REFERENCE_SEED
    current_seed: int = DEFAULT_CURRENT_SEED
    warning_threshold: Decimal = DEFAULT_WARNING_THRESHOLD
    failure_threshold: Decimal = DEFAULT_FAILURE_THRESHOLD
    output_dir: Path | None = None


def _decimal(value: object) -> Decimal:
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return Decimal("0")


def _metric(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))


def _mean(rows: list[dict[str, object]], feature: str) -> Decimal:
    if not rows:
        return Decimal("0")
    return sum(_decimal(row[feature]) for row in rows) / Decimal(len(rows))


def _relative_change(reference: Decimal, current: Decimal) -> Decimal:
    denominator = abs(reference)
    if denominator == 0:
        return Decimal("0") if current == 0 else Decimal("1")
    return abs(current - reference) / denominator


def _distribution(rows: list[dict[str, object]], feature: str) -> dict[str, Decimal]:
    if not rows:
        return {}
    counts = Counter(str(row[feature]) for row in rows)
    total = Decimal(len(rows))
    return {bucket: Decimal(count) / total for bucket, count in sorted(counts.items())}


def _max_bucket_share_delta(
    reference_distribution: dict[str, Decimal],
    current_distribution: dict[str, Decimal],
) -> Decimal:
    buckets = set(reference_distribution) | set(current_distribution)
    if not buckets:
        return Decimal("0")
    return max(
        abs(
            current_distribution.get(bucket, Decimal("0"))
            - reference_distribution.get(bucket, Decimal("0"))
        )
        for bucket in buckets
    )


def _check_status(score: Decimal, warning_threshold: Decimal, failure_threshold: Decimal) -> str:
    if score >= failure_threshold:
        return "failed"
    if score >= warning_threshold:
        return "warning"
    return "passed"


def _overall_status(checks: list[dict[str, object]]) -> str:
    statuses = {str(check["status"]) for check in checks}
    if "failed" in statuses:
        return "failed"
    if "warning" in statuses:
        return "warning"
    return "passed"


def build_numeric_drift_checks(
    reference_rows: list[dict[str, object]],
    current_rows: list[dict[str, object]],
    *,
    warning_threshold: Decimal,
    failure_threshold: Decimal,
) -> list[dict[str, object]]:
    checks: list[dict[str, object]] = []
    for feature in NUMERIC_FEATURES:
        reference_mean = _mean(reference_rows, feature)
        current_mean = _mean(current_rows, feature)
        score = _relative_change(reference_mean, current_mean)
        checks.append(
            {
                "check_name": f"{feature}_mean_relative_change",
                "check_type": "numeric_mean_drift",
                "feature": feature,
                "reference_mean": _metric(reference_mean),
                "current_mean": _metric(current_mean),
                "score": _metric(score),
                "warning_threshold": _metric(warning_threshold),
                "failure_threshold": _metric(failure_threshold),
                "status": _check_status(score, warning_threshold, failure_threshold),
            },
        )
    return checks


def build_categorical_drift_checks(
    reference_rows: list[dict[str, object]],
    current_rows: list[dict[str, object]],
    *,
    warning_threshold: Decimal,
    failure_threshold: Decimal,
) -> list[dict[str, object]]:
    checks: list[dict[str, object]] = []
    for feature in CATEGORICAL_FEATURES:
        reference_distribution = _distribution(reference_rows, feature)
        current_distribution = _distribution(current_rows, feature)
        score = _max_bucket_share_delta(reference_distribution, current_distribution)
        checks.append(
            {
                "check_name": f"{feature}_max_bucket_share_delta",
                "check_type": "categorical_distribution_drift",
                "feature": feature,
                "score": _metric(score),
                "warning_threshold": _metric(warning_threshold),
                "failure_threshold": _metric(failure_threshold),
                "status": _check_status(score, warning_threshold, failure_threshold),
                "reference_distribution": {
                    bucket: _metric(share) for bucket, share in reference_distribution.items()
                },
                "current_distribution": {
                    bucket: _metric(share) for bucket, share in current_distribution.items()
                },
            },
        )
    return checks


def build_row_count_drift_check(
    reference_rows: list[dict[str, object]],
    current_rows: list[dict[str, object]],
    *,
    warning_threshold: Decimal,
    failure_threshold: Decimal,
) -> dict[str, object]:
    reference_count = Decimal(len(reference_rows))
    current_count = Decimal(len(current_rows))
    score = _relative_change(reference_count, current_count)
    return {
        "check_name": "row_count_relative_change",
        "check_type": "row_count_drift",
        "feature": "row_count",
        "reference_count": len(reference_rows),
        "current_count": len(current_rows),
        "score": _metric(score),
        "warning_threshold": _metric(warning_threshold),
        "failure_threshold": _metric(failure_threshold),
        "status": _check_status(score, warning_threshold, failure_threshold),
    }


def build_drift_report(
    config: DemandFeatureDriftConfig,
    reference_rows: list[dict[str, object]],
    current_rows: list[dict[str, object]],
) -> dict[str, object]:
    checks = [
        build_row_count_drift_check(
            reference_rows,
            current_rows,
            warning_threshold=config.warning_threshold,
            failure_threshold=config.failure_threshold,
        ),
        *build_numeric_drift_checks(
            reference_rows,
            current_rows,
            warning_threshold=config.warning_threshold,
            failure_threshold=config.failure_threshold,
        ),
        *build_categorical_drift_checks(
            reference_rows,
            current_rows,
            warning_threshold=config.warning_threshold,
            failure_threshold=config.failure_threshold,
        ),
    ]
    reference_dataset_id = str(reference_rows[0]["dataset_id"]) if reference_rows else ""
    current_dataset_id = str(current_rows[0]["dataset_id"]) if current_rows else ""

    return {
        "report_name": "retailops-demand-feature-drift",
        "dataset_name": DATASET_NAME,
        "profile": config.dataset.profile,
        "reference_seed": config.reference_seed,
        "current_seed": config.current_seed,
        "reference_dataset_id": reference_dataset_id,
        "current_dataset_id": current_dataset_id,
        "reference_row_count": len(reference_rows),
        "current_row_count": len(current_rows),
        "warning_threshold": _metric(config.warning_threshold),
        "failure_threshold": _metric(config.failure_threshold),
        "status": _overall_status(checks),
        "check_count": len(checks),
        "failed_check_count": sum(1 for check in checks if check["status"] == "failed"),
        "warning_check_count": sum(1 for check in checks if check["status"] == "warning"),
        "checks": checks,
        "generator_version": GENERATOR_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "artifacts": [DRIFT_REPORT_FILENAME, DRIFT_SUMMARY_FILENAME],
    }


def build_drift_summary(report: dict[str, object]) -> str:
    return "\n".join(
        [
            "# RetailOps Demand Feature Drift",
            "",
            f"- Status: `{report['status']}`",
            f"- Profile: `{report['profile']}`",
            f"- Reference dataset: `{report['reference_dataset_id']}`",
            f"- Current dataset: `{report['current_dataset_id']}`",
            f"- Checks: `{report['check_count']}`",
            f"- Warnings: `{report['warning_check_count']}`",
            f"- Failures: `{report['failed_check_count']}`",
            f"- Warning threshold: `{report['warning_threshold']}`",
            f"- Failure threshold: `{report['failure_threshold']}`",
            "",
            "This report compares deterministic reference and current demand feature distributions.",
            "",
        ],
    )


def default_drift_output_dir(profile: str) -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "data" / "synthetic" / profile / "reports" / "demand_feature_drift"


def write_drift_artifacts(output_dir: Path, report: dict[str, object]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / DRIFT_REPORT_FILENAME).write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / DRIFT_SUMMARY_FILENAME).write_text(
        build_drift_summary(report),
        encoding="utf-8",
    )


def _dataset_config_with_seed(
    config: DatasetGenerationConfig, seed: int
) -> DatasetGenerationConfig:
    return DatasetGenerationConfig(
        profile=config.profile,
        days=config.days,
        products=config.products,
        stores=config.stores,
        warehouses=config.warehouses,
        seed=seed,
    )


def generate_demand_feature_drift_report(config: DemandFeatureDriftConfig) -> dict[str, object]:
    reference_dataset = _dataset_config_with_seed(config.dataset, config.reference_seed)
    current_dataset = _dataset_config_with_seed(config.dataset, config.current_seed)
    reference_rows = build_demand_feature_rows(build_dataset(reference_dataset), reference_dataset)
    current_rows = build_demand_feature_rows(build_dataset(current_dataset), current_dataset)
    report = build_drift_report(config, reference_rows, current_rows)
    output_dir = config.output_dir or default_drift_output_dir(config.dataset.profile)
    write_drift_artifacts(output_dir, report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate RetailOps demand forecast feature drift checks.",
    )
    parser.add_argument("--profile", choices=("demo", "small", "medium", "large"), default="demo")
    parser.add_argument("--days", type=int)
    parser.add_argument("--products", type=int)
    parser.add_argument("--stores", type=int)
    parser.add_argument("--warehouses", type=int)
    parser.add_argument("--reference-seed", type=int, default=DEFAULT_REFERENCE_SEED)
    parser.add_argument("--current-seed", type=int, default=DEFAULT_CURRENT_SEED)
    parser.add_argument("--warning-threshold", type=Decimal, default=DEFAULT_WARNING_THRESHOLD)
    parser.add_argument("--failure-threshold", type=Decimal, default=DEFAULT_FAILURE_THRESHOLD)
    parser.add_argument("--output-dir", type=Path)
    return parser.parse_args()


def config_from_args(args: argparse.Namespace) -> DemandFeatureDriftConfig:
    return DemandFeatureDriftConfig(
        dataset=DatasetGenerationConfig(
            profile=args.profile,
            days=args.days,
            products=args.products,
            stores=args.stores,
            warehouses=args.warehouses,
            seed=args.reference_seed,
        ),
        reference_seed=args.reference_seed,
        current_seed=args.current_seed,
        warning_threshold=args.warning_threshold,
        failure_threshold=args.failure_threshold,
        output_dir=args.output_dir,
    )


def main() -> None:
    config = config_from_args(parse_args())
    report = generate_demand_feature_drift_report(config)
    output_dir = config.output_dir or default_drift_output_dir(config.dataset.profile)

    print(  # noqa: T201 - CLI output
        f"RetailOps demand feature drift generated: {report['status']} "
        f"({report['failed_check_count']} failures, {report['warning_check_count']} warnings)",
    )
    print(f"Output directory: {output_dir}")  # noqa: T201 - CLI output


if __name__ == "__main__":
    main()
