from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from data.generator.common import deterministic_uuid
from data.generator.main import DatasetGenerationConfig, build_dataset
from data.generator.manifest import GENERATOR_VERSION
from ml.features.demand_forecast import build_demand_feature_rows
from ml.metadata.model_registry import (
    ModelMetadataConfig,
    default_metadata_output_dir,
    generate_and_persist_model_metadata,
)
from ml.models.baseline_forecast import (
    MODEL_NAME,
    MODEL_VERSION,
    build_baseline_forecasts,
)

BATCH_PREDICTIONS_FILENAME = "batch_predictions.csv"
API_FORECASTS_FILENAME = "api_forecasts.csv"
BATCH_MANIFEST_FILENAME = "batch_inference_manifest.json"
DEFAULT_WINDOW_DAYS = 28
DEFAULT_HORIZON_DAYS = 7
DEFAULT_HOLDOUT_DAYS = 7
DEFAULT_MODEL_STATUS = "candidate"
FORECAST_METHOD = "retailops-baseline-demand-model"
BATCH_PREDICTION_COLUMNS = [
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
API_FORECAST_COLUMNS = [
    "id",
    "product_id",
    "forecast_period_start",
    "forecast_period_end",
    "predicted_quantity",
    "unit_of_measure",
    "generated_at",
    "method",
    "status",
    "confidence_level",
]


@dataclass(frozen=True)
class BatchInferenceConfig:
    dataset: DatasetGenerationConfig = field(
        default_factory=lambda: DatasetGenerationConfig(profile="demo"),
    )
    window_days: int = DEFAULT_WINDOW_DAYS
    horizon_days: int = DEFAULT_HORIZON_DAYS
    holdout_days: int = DEFAULT_HOLDOUT_DAYS
    model_status: str = DEFAULT_MODEL_STATUS
    output_dir: Path | None = None
    metadata_output_dir: Path | None = None
    model_output_dir: Path | None = None
    evaluation_output_dir: Path | None = None


def _decimal(value: object) -> Decimal:
    return Decimal(str(value))


def _quantity(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP))


def _confidence(training_rows: int, window_days: int) -> str:
    coverage = Decimal(training_rows) / Decimal(max(window_days, 1))
    score = min(Decimal("0.9500"), max(Decimal("0.5000"), Decimal("0.6000") + coverage))
    return str(score.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))


def build_api_forecast_rows(
    batch_predictions: list[dict[str, object]],
    *,
    window_days: int,
) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for prediction in batch_predictions:
        grouped[(str(prediction["product_id"]), str(prediction["forecast_date"]))].append(
            prediction,
        )

    rows: list[dict[str, object]] = []
    for key in sorted(grouped):
        product_id, forecast_date = key
        predictions = grouped[key]
        predicted_quantity = sum(_decimal(row["predicted_units"]) for row in predictions)
        training_rows = sum(int(row["training_rows"]) for row in predictions)
        generated_at = max(str(row["trained_at"]) for row in predictions)
        natural_key = f"{MODEL_VERSION}:{product_id}:{forecast_date}:{predicted_quantity}"

        rows.append(
            {
                "id": deterministic_uuid("batch_api_forecast", natural_key),
                "product_id": product_id,
                "forecast_period_start": forecast_date,
                "forecast_period_end": forecast_date,
                "predicted_quantity": _quantity(predicted_quantity),
                "unit_of_measure": "pcs",
                "generated_at": generated_at,
                "method": FORECAST_METHOD,
                "status": "generated",
                "confidence_level": _confidence(training_rows, window_days),
            },
        )

    return rows


def build_batch_inference_manifest(
    config: BatchInferenceConfig,
    metadata: dict[str, object],
    batch_predictions: list[dict[str, object]],
    api_forecast_rows: list[dict[str, object]],
) -> dict[str, object]:
    forecast_dates = [str(row["forecast_date"]) for row in batch_predictions]
    dataset_id = str(metadata["feature_dataset_id"])
    run_key = f"{MODEL_VERSION}:{dataset_id}:batch-inference"

    return {
        "run_key": run_key,
        "job_name": "retailops-demand-batch-inference",
        "model_name": MODEL_NAME,
        "model_version": MODEL_VERSION,
        "model_status": metadata["status"],
        "feature_dataset_id": dataset_id,
        "profile": config.dataset.profile,
        "seed": config.dataset.seed,
        "window_days": config.window_days,
        "horizon_days": config.horizon_days,
        "batch_prediction_count": len(batch_predictions),
        "api_forecast_count": len(api_forecast_rows),
        "forecast_date_start": min(forecast_dates) if forecast_dates else "",
        "forecast_date_end": max(forecast_dates) if forecast_dates else "",
        "metadata_model_id": metadata["model_id"],
        "metadata_output_dir": str(
            config.metadata_output_dir or default_metadata_output_dir(config.dataset.profile),
        ),
        "generator_version": GENERATOR_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "artifacts": [
            BATCH_PREDICTIONS_FILENAME,
            API_FORECASTS_FILENAME,
            BATCH_MANIFEST_FILENAME,
        ],
    }


def default_batch_output_dir(profile: str) -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "data" / "synthetic" / profile / "inference" / "demand_baseline"


def write_batch_inference_artifacts(
    output_dir: Path,
    batch_predictions: list[dict[str, object]],
    api_forecast_rows: list[dict[str, object]],
    manifest: dict[str, object],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / BATCH_PREDICTIONS_FILENAME).open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(file, fieldnames=BATCH_PREDICTION_COLUMNS)
        writer.writeheader()
        writer.writerows(batch_predictions)

    with (output_dir / API_FORECASTS_FILENAME).open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(file, fieldnames=API_FORECAST_COLUMNS)
        writer.writeheader()
        writer.writerows(api_forecast_rows)

    (output_dir / BATCH_MANIFEST_FILENAME).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def run_batch_inference(config: BatchInferenceConfig) -> dict[str, object]:
    metadata = generate_and_persist_model_metadata(
        ModelMetadataConfig(
            dataset=config.dataset,
            window_days=config.window_days,
            horizon_days=config.horizon_days,
            holdout_days=config.holdout_days,
            status=config.model_status,
            output_dir=config.metadata_output_dir,
            model_output_dir=config.model_output_dir,
            evaluation_output_dir=config.evaluation_output_dir,
        ),
    )
    tables = build_dataset(config.dataset)
    feature_rows = build_demand_feature_rows(tables, config.dataset)
    batch_predictions = build_baseline_forecasts(
        feature_rows,
        window_days=config.window_days,
        horizon_days=config.horizon_days,
    )
    api_forecast_rows = build_api_forecast_rows(
        batch_predictions,
        window_days=config.window_days,
    )
    manifest = build_batch_inference_manifest(
        config,
        metadata,
        batch_predictions,
        api_forecast_rows,
    )
    output_dir = config.output_dir or default_batch_output_dir(config.dataset.profile)
    write_batch_inference_artifacts(output_dir, batch_predictions, api_forecast_rows, manifest)
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run RetailOps batch demand forecast inference.",
    )
    parser.add_argument("--profile", choices=("demo", "small", "medium", "large"), default="demo")
    parser.add_argument("--days", type=int)
    parser.add_argument("--products", type=int)
    parser.add_argument("--stores", type=int)
    parser.add_argument("--warehouses", type=int)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--window-days", type=int, default=DEFAULT_WINDOW_DAYS)
    parser.add_argument("--horizon-days", type=int, default=DEFAULT_HORIZON_DAYS)
    parser.add_argument("--holdout-days", type=int, default=DEFAULT_HOLDOUT_DAYS)
    parser.add_argument("--model-status", default=DEFAULT_MODEL_STATUS)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--metadata-output-dir", type=Path)
    parser.add_argument("--model-output-dir", type=Path)
    parser.add_argument("--evaluation-output-dir", type=Path)
    return parser.parse_args()


def config_from_args(args: argparse.Namespace) -> BatchInferenceConfig:
    return BatchInferenceConfig(
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
        holdout_days=args.holdout_days,
        model_status=args.model_status,
        output_dir=args.output_dir,
        metadata_output_dir=args.metadata_output_dir,
        model_output_dir=args.model_output_dir,
        evaluation_output_dir=args.evaluation_output_dir,
    )


def main() -> None:
    config = config_from_args(parse_args())
    manifest = run_batch_inference(config)
    output_dir = config.output_dir or default_batch_output_dir(config.dataset.profile)

    print(  # noqa: T201 - CLI output
        f"RetailOps batch inference generated: {manifest['api_forecast_count']} API forecasts",
    )
    print(f"Output directory: {output_dir}")  # noqa: T201 - CLI output


if __name__ == "__main__":
    main()
