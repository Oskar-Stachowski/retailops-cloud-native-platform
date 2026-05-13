from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from data.generator.common import deterministic_uuid
from data.generator.main import DatasetGenerationConfig, build_dataset
from data.generator.manifest import GENERATOR_VERSION
from ml.features.demand_forecast import (
    DATASET_NAME as FEATURE_DATASET_NAME,
)
from ml.features.demand_forecast import (
    GRAIN,
    TARGET,
    build_demand_feature_rows,
)

MODEL_NAME = "retailops-demand-baseline-moving-average"
MODEL_VERSION = "baseline-moving-average-v1"
FORECAST_FILENAME = "baseline_forecasts.csv"
MODEL_MANIFEST_FILENAME = "model_manifest.json"
DEFAULT_WINDOW_DAYS = 28
DEFAULT_HORIZON_DAYS = 7
SERIES_FIELDS = ["product_id", "store_id", "channel"]
FORECAST_COLUMNS = [
    "forecast_id",
    "model_name",
    "model_version",
    "dataset_id",
    "schema_version",
    "forecast_date",
    "product_id",
    "store_id",
    "channel",
    "predicted_units",
    "baseline_window_days",
    "training_rows",
    "feature_date_start",
    "feature_date_end",
    "trained_at",
]


@dataclass(frozen=True)
class BaselineForecastConfig:
    dataset: DatasetGenerationConfig = field(
        default_factory=lambda: DatasetGenerationConfig(profile="demo"),
    )
    window_days: int = DEFAULT_WINDOW_DAYS
    horizon_days: int = DEFAULT_HORIZON_DAYS
    output_dir: Path | None = None


def _row_date(row: dict[str, object]) -> date:
    return date.fromisoformat(str(row["date"]))


def _series_key(row: dict[str, object]) -> tuple[str, str, str]:
    return tuple(str(row[field]) for field in SERIES_FIELDS)


def _prediction_value(rows: list[dict[str, object]]) -> int:
    total = sum(Decimal(str(row[TARGET])) for row in rows)
    average = total / Decimal(len(rows))
    return int(average.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _trained_at(rows: list[dict[str, object]]) -> str:
    generated_at_values = [str(row["generated_at"]) for row in rows]
    if generated_at_values:
        return max(generated_at_values)
    return datetime.now(UTC).isoformat()


def build_baseline_forecasts(
    feature_rows: list[dict[str, object]],
    *,
    window_days: int = DEFAULT_WINDOW_DAYS,
    horizon_days: int = DEFAULT_HORIZON_DAYS,
) -> list[dict[str, object]]:
    if window_days <= 0:
        msg = "window_days must be a positive integer."
        raise ValueError(msg)
    if horizon_days <= 0:
        msg = "horizon_days must be a positive integer."
        raise ValueError(msg)
    if not feature_rows:
        return []

    rows_by_series: dict[tuple[str, str, str], list[dict[str, object]]] = defaultdict(list)
    for row in feature_rows:
        rows_by_series[_series_key(row)].append(row)

    dataset_id = str(feature_rows[0]["dataset_id"])
    feature_dates = [_row_date(row) for row in feature_rows]
    feature_date_start = min(feature_dates).isoformat()
    feature_date_end_value = max(feature_dates)
    feature_date_end = feature_date_end_value.isoformat()
    trained_at = _trained_at(feature_rows)
    forecast_rows: list[dict[str, object]] = []

    for key in sorted(rows_by_series):
        product_id, store_id, channel = key
        series_rows = sorted(rows_by_series[key], key=_row_date)
        cutoff_start = feature_date_end_value - timedelta(days=window_days - 1)
        window_rows = [row for row in series_rows if _row_date(row) >= cutoff_start]
        if not window_rows:
            window_rows = series_rows[-1:]
        predicted_units = max(0, _prediction_value(window_rows))

        for horizon_offset in range(1, horizon_days + 1):
            forecast_date = (feature_date_end_value + timedelta(days=horizon_offset)).isoformat()
            natural_key = (
                f"{MODEL_VERSION}:{dataset_id}:{product_id}:{store_id}:{channel}:{forecast_date}"
            )
            forecast_rows.append(
                {
                    "forecast_id": deterministic_uuid("baseline_forecast", natural_key),
                    "model_name": MODEL_NAME,
                    "model_version": MODEL_VERSION,
                    "dataset_id": dataset_id,
                    "schema_version": "1.0",
                    "forecast_date": forecast_date,
                    "product_id": product_id,
                    "store_id": store_id,
                    "channel": channel,
                    "predicted_units": predicted_units,
                    "baseline_window_days": window_days,
                    "training_rows": len(window_rows),
                    "feature_date_start": feature_date_start,
                    "feature_date_end": feature_date_end,
                    "trained_at": trained_at,
                },
            )

    return forecast_rows


def build_model_manifest(
    config: BaselineForecastConfig,
    feature_rows: list[dict[str, object]],
    forecast_rows: list[dict[str, object]],
) -> dict[str, object]:
    feature_dates = [str(row["date"]) for row in feature_rows]
    forecast_dates = [str(row["forecast_date"]) for row in forecast_rows]
    dataset_id = str(feature_rows[0]["dataset_id"]) if feature_rows else ""

    return {
        "model_name": MODEL_NAME,
        "model_version": MODEL_VERSION,
        "model_type": "moving_average_baseline",
        "feature_dataset_name": FEATURE_DATASET_NAME,
        "feature_dataset_id": dataset_id,
        "feature_grain": GRAIN,
        "target": TARGET,
        "profile": config.dataset.profile,
        "seed": config.dataset.seed,
        "window_days": config.window_days,
        "horizon_days": config.horizon_days,
        "feature_row_count": len(feature_rows),
        "forecast_row_count": len(forecast_rows),
        "feature_date_start": min(feature_dates) if feature_dates else "",
        "feature_date_end": max(feature_dates) if feature_dates else "",
        "forecast_date_start": min(forecast_dates) if forecast_dates else "",
        "forecast_date_end": max(forecast_dates) if forecast_dates else "",
        "generator_version": GENERATOR_VERSION,
        "trained_at": _trained_at(feature_rows),
        "artifacts": [FORECAST_FILENAME, MODEL_MANIFEST_FILENAME],
    }


def default_model_output_dir(profile: str) -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "data" / "synthetic" / profile / "models" / "demand_baseline"


def write_baseline_artifacts(
    output_dir: Path,
    forecast_rows: list[dict[str, object]],
    manifest: dict[str, object],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / FORECAST_FILENAME).open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=FORECAST_COLUMNS)
        writer.writeheader()
        writer.writerows(forecast_rows)

    (output_dir / MODEL_MANIFEST_FILENAME).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def train_baseline_forecast_model(config: BaselineForecastConfig) -> dict[str, object]:
    tables = build_dataset(config.dataset)
    feature_rows = build_demand_feature_rows(tables, config.dataset)
    forecast_rows = build_baseline_forecasts(
        feature_rows,
        window_days=config.window_days,
        horizon_days=config.horizon_days,
    )
    manifest = build_model_manifest(config, feature_rows, forecast_rows)
    output_dir = config.output_dir or default_model_output_dir(config.dataset.profile)
    write_baseline_artifacts(output_dir, forecast_rows, manifest)
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train RetailOps baseline demand forecasting model.",
    )
    parser.add_argument("--profile", choices=("demo", "small", "medium", "large"), default="demo")
    parser.add_argument("--days", type=int)
    parser.add_argument("--products", type=int)
    parser.add_argument("--stores", type=int)
    parser.add_argument("--warehouses", type=int)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--window-days", type=int, default=DEFAULT_WINDOW_DAYS)
    parser.add_argument("--horizon-days", type=int, default=DEFAULT_HORIZON_DAYS)
    parser.add_argument("--output-dir", type=Path)
    return parser.parse_args()


def config_from_args(args: argparse.Namespace) -> BaselineForecastConfig:
    return BaselineForecastConfig(
        dataset=DatasetGenerationConfig(
            profile=args.profile,
            days=args.days,
            products=args.products,
            stores=args.stores,
            warehouses=args.warehouses,
            seed=args.seed,
        ),
        window_days=args.window_days,
        horizon_days=args.horizon_days,
        output_dir=args.output_dir,
    )


def main() -> None:
    config = config_from_args(parse_args())
    manifest = train_baseline_forecast_model(config)
    output_dir = config.output_dir or default_model_output_dir(config.dataset.profile)

    print(  # noqa: T201 - CLI output
        f"RetailOps baseline forecast generated: {manifest['forecast_row_count']} rows",
    )
    print(f"Output directory: {output_dir}")  # noqa: T201 - CLI output


if __name__ == "__main__":
    main()
