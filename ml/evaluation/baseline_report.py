from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from data.generator.main import DatasetGenerationConfig, build_dataset
from data.generator.manifest import GENERATOR_VERSION
from ml.features.demand_forecast import GRAIN, TARGET, build_demand_feature_rows
from ml.models.baseline_forecast import (
    MODEL_NAME,
    MODEL_VERSION,
    _prediction_value,
)

DEFAULT_HOLDOUT_DAYS = 7
EVALUATION_REPORT_FILENAME = "evaluation_report.json"
EVALUATION_SUMMARY_FILENAME = "evaluation_summary.md"
BACKTEST_PREDICTIONS_FILENAME = "backtest_predictions.csv"
BACKTEST_COLUMNS = [
    "model_name",
    "model_version",
    "dataset_id",
    "forecast_date",
    "product_id",
    "store_id",
    "channel",
    "predicted_units",
    "actual_units",
    "absolute_error",
    "squared_error",
    "absolute_percentage_error",
    "training_rows",
    "baseline_window_days",
]
SERIES_FIELDS = ["product_id", "store_id", "channel"]


@dataclass(frozen=True)
class EvaluationConfig:
    dataset: DatasetGenerationConfig = field(
        default_factory=lambda: DatasetGenerationConfig(profile="demo"),
    )
    window_days: int = 28
    holdout_days: int = DEFAULT_HOLDOUT_DAYS
    output_dir: Path | None = None


def _row_date(row: dict[str, object]) -> date:
    return date.fromisoformat(str(row["date"]))


def _series_key(row: dict[str, object]) -> tuple[str, str, str]:
    return tuple(str(row[field]) for field in SERIES_FIELDS)


def _target(row: dict[str, object]) -> Decimal:
    return Decimal(str(row[TARGET]))


def _metric(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))


def _moneyish(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def build_backtest_predictions(
    feature_rows: list[dict[str, object]],
    *,
    window_days: int,
    holdout_days: int,
) -> tuple[list[dict[str, object]], int]:
    if window_days <= 0:
        msg = "window_days must be a positive integer."
        raise ValueError(msg)
    if holdout_days <= 0:
        msg = "holdout_days must be a positive integer."
        raise ValueError(msg)
    if not feature_rows:
        return [], 0

    rows_by_series: dict[tuple[str, str, str], list[dict[str, object]]] = defaultdict(list)
    for row in feature_rows:
        rows_by_series[_series_key(row)].append(row)

    dataset_id = str(feature_rows[0]["dataset_id"])
    max_feature_date = max(_row_date(row) for row in feature_rows)
    holdout_start = max_feature_date - timedelta(days=holdout_days - 1)
    predictions: list[dict[str, object]] = []
    skipped_rows = 0

    for key in sorted(rows_by_series):
        product_id, store_id, channel = key
        series_rows = sorted(rows_by_series[key], key=_row_date)
        holdout_rows = [row for row in series_rows if _row_date(row) >= holdout_start]

        for holdout_row in holdout_rows:
            forecast_date = _row_date(holdout_row)
            train_start = forecast_date - timedelta(days=window_days)
            training_rows = [
                row for row in series_rows if train_start <= _row_date(row) < forecast_date
            ]
            if not training_rows:
                skipped_rows += 1
                continue

            predicted_units = Decimal(_prediction_value(training_rows))
            actual_units = _target(holdout_row)
            error = predicted_units - actual_units
            absolute_error = abs(error)
            squared_error = error * error
            absolute_percentage_error = (
                absolute_error / actual_units * Decimal("100") if actual_units > 0 else Decimal("0")
            )

            predictions.append(
                {
                    "model_name": MODEL_NAME,
                    "model_version": MODEL_VERSION,
                    "dataset_id": dataset_id,
                    "forecast_date": forecast_date.isoformat(),
                    "product_id": product_id,
                    "store_id": store_id,
                    "channel": channel,
                    "predicted_units": int(predicted_units),
                    "actual_units": int(actual_units),
                    "absolute_error": _moneyish(absolute_error),
                    "squared_error": _moneyish(squared_error),
                    "absolute_percentage_error": _metric(absolute_percentage_error),
                    "training_rows": len(training_rows),
                    "baseline_window_days": window_days,
                },
            )

    return predictions, skipped_rows


def calculate_metrics(predictions: list[dict[str, object]]) -> dict[str, object]:
    if not predictions:
        return {
            "evaluated_rows": 0,
            "mae": "",
            "rmse": "",
            "mape": "",
            "bias": "",
            "wape": "",
        }

    row_count = Decimal(len(predictions))
    absolute_errors = [Decimal(str(row["absolute_error"])) for row in predictions]
    squared_errors = [Decimal(str(row["squared_error"])) for row in predictions]
    actual_units = [Decimal(str(row["actual_units"])) for row in predictions]
    predicted_units = [Decimal(str(row["predicted_units"])) for row in predictions]
    percentage_errors = [Decimal(str(row["absolute_percentage_error"])) for row in predictions]

    mae = sum(absolute_errors) / row_count
    rmse = (sum(squared_errors) / row_count).sqrt()
    mape = sum(percentage_errors) / row_count
    bias = (sum(predicted_units) - sum(actual_units)) / row_count
    wape = (
        sum(absolute_errors) / sum(actual_units) * Decimal("100")
        if sum(actual_units) > 0
        else Decimal("0")
    )

    return {
        "evaluated_rows": len(predictions),
        "mae": _metric(mae),
        "rmse": _metric(rmse),
        "mape": _metric(mape),
        "bias": _metric(bias),
        "wape": _metric(wape),
    }


def build_evaluation_report(
    config: EvaluationConfig,
    feature_rows: list[dict[str, object]],
    predictions: list[dict[str, object]],
    skipped_rows: int,
) -> dict[str, object]:
    feature_dates = [str(row["date"]) for row in feature_rows]
    prediction_dates = [str(row["forecast_date"]) for row in predictions]
    dataset_id = str(feature_rows[0]["dataset_id"]) if feature_rows else ""
    metrics = calculate_metrics(predictions)

    return {
        "report_name": "retailops-demand-baseline-evaluation",
        "model_name": MODEL_NAME,
        "model_version": MODEL_VERSION,
        "evaluation_type": "rolling_holdout_backtest",
        "profile": config.dataset.profile,
        "seed": config.dataset.seed,
        "feature_dataset_id": dataset_id,
        "feature_grain": GRAIN,
        "target": TARGET,
        "window_days": config.window_days,
        "holdout_days": config.holdout_days,
        "feature_row_count": len(feature_rows),
        "skipped_rows": skipped_rows,
        "metrics": metrics,
        "feature_date_start": min(feature_dates) if feature_dates else "",
        "feature_date_end": max(feature_dates) if feature_dates else "",
        "evaluation_date_start": min(prediction_dates) if prediction_dates else "",
        "evaluation_date_end": max(prediction_dates) if prediction_dates else "",
        "generator_version": GENERATOR_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "artifacts": [
            EVALUATION_REPORT_FILENAME,
            EVALUATION_SUMMARY_FILENAME,
            BACKTEST_PREDICTIONS_FILENAME,
        ],
    }


def build_evaluation_summary(report: dict[str, object]) -> str:
    metrics = report["metrics"]
    if not isinstance(metrics, dict):
        msg = "metrics must be a dictionary."
        raise TypeError(msg)

    return "\n".join(
        [
            "# RetailOps Baseline Forecast Evaluation",
            "",
            f"- Model: `{report['model_name']}`",
            f"- Version: `{report['model_version']}`",
            f"- Feature dataset: `{report['feature_dataset_id']}`",
            f"- Evaluation window: `{report['evaluation_date_start']}` to `{report['evaluation_date_end']}`",
            f"- Evaluated rows: `{metrics['evaluated_rows']}`",
            f"- Skipped rows: `{report['skipped_rows']}`",
            f"- MAE: `{metrics['mae']}`",
            f"- RMSE: `{metrics['rmse']}`",
            f"- MAPE: `{metrics['mape']}`",
            f"- Bias: `{metrics['bias']}`",
            f"- WAPE: `{metrics['wape']}`",
            "",
            "This report is a deterministic local baseline evaluation artifact. It is not a model promotion decision.",
            "",
        ],
    )


def default_evaluation_output_dir(profile: str) -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "data" / "synthetic" / profile / "reports" / "demand_baseline"


def write_evaluation_artifacts(
    output_dir: Path,
    report: dict[str, object],
    predictions: list[dict[str, object]],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / BACKTEST_PREDICTIONS_FILENAME).open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(file, fieldnames=BACKTEST_COLUMNS)
        writer.writeheader()
        writer.writerows(predictions)

    (output_dir / EVALUATION_REPORT_FILENAME).write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / EVALUATION_SUMMARY_FILENAME).write_text(
        build_evaluation_summary(report),
        encoding="utf-8",
    )


def generate_baseline_evaluation_report(config: EvaluationConfig) -> dict[str, object]:
    tables = build_dataset(config.dataset)
    feature_rows = build_demand_feature_rows(tables, config.dataset)
    predictions, skipped_rows = build_backtest_predictions(
        feature_rows,
        window_days=config.window_days,
        holdout_days=config.holdout_days,
    )
    report = build_evaluation_report(config, feature_rows, predictions, skipped_rows)
    output_dir = config.output_dir or default_evaluation_output_dir(config.dataset.profile)
    write_evaluation_artifacts(output_dir, report, predictions)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate RetailOps baseline forecast evaluation report.",
    )
    parser.add_argument("--profile", choices=("demo", "small", "medium", "large"), default="demo")
    parser.add_argument("--days", type=int)
    parser.add_argument("--products", type=int)
    parser.add_argument("--stores", type=int)
    parser.add_argument("--warehouses", type=int)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--window-days", type=int, default=28)
    parser.add_argument("--holdout-days", type=int, default=DEFAULT_HOLDOUT_DAYS)
    parser.add_argument("--output-dir", type=Path)
    return parser.parse_args()


def config_from_args(args: argparse.Namespace) -> EvaluationConfig:
    return EvaluationConfig(
        dataset=DatasetGenerationConfig(
            profile=args.profile,
            days=args.days,
            products=args.products,
            stores=args.stores,
            warehouses=args.warehouses,
            seed=args.seed,
        ),
        window_days=args.window_days,
        holdout_days=args.holdout_days,
        output_dir=args.output_dir,
    )


def main() -> None:
    config = config_from_args(parse_args())
    report = generate_baseline_evaluation_report(config)
    output_dir = config.output_dir or default_evaluation_output_dir(config.dataset.profile)
    metrics = report["metrics"]
    evaluated_rows = metrics["evaluated_rows"] if isinstance(metrics, dict) else 0

    print(  # noqa: T201 - CLI output
        f"RetailOps baseline evaluation generated: {evaluated_rows} evaluated rows",
    )
    print(f"Output directory: {output_dir}")  # noqa: T201 - CLI output


if __name__ == "__main__":
    main()
