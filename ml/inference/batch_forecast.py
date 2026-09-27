"""Offline batch forecasts from one verified, previously evaluated RF artifact."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from data.generator.common import deterministic_uuid
from ml.evaluation.fixed_origin import _history
from ml.experiments.assessed_run import AssessedRun, load_assessed_run
from ml.experiments.identity import logical_rows_sha256
from ml.features.demand_forecast import forecast_origin_utc
from ml.metadata.model_registry import default_metadata_output_dir
from ml.metadata.verified_rf import persist_verified_rf_metadata
from ml.models.random_forest_forecast import (
    MODEL_NAME,
    MODEL_VERSION,
    _quantity,
    build_training_features,
)

BATCH_PREDICTIONS_FILENAME = "batch_predictions.csv"
API_FORECASTS_FILENAME = "api_forecasts.csv"
BATCH_MANIFEST_FILENAME = "batch_inference_manifest.json"
FORECAST_METHOD = "retailops-random-forest-demand-model"
BATCH_PREDICTION_COLUMNS = [
    "experiment_id",
    "run_id",
    "model_id",
    "feature_dataset_id",
    "origin",
    "forecast_date",
    "horizon_day",
    "product_id",
    "store_id",
    "channel",
    "predicted_units",
    "history_rows",
    "generated_at",
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
    experiment_dir: Path
    output_dir: Path | None = None
    metadata_output_dir: Path | None = None


def default_batch_output_dir(profile: str) -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "data" / "synthetic" / profile / "inference" / "demand_random_forest"


def _future_target(last_row: dict[str, object], target_date: date) -> dict[str, object]:
    return {
        "date": target_date.isoformat(),
        "day_of_week": target_date.isoweekday(),
        "is_weekend": target_date.isoweekday() in {6, 7},
        "week_of_year": target_date.isocalendar().week,
        "month": target_date.month,
        "product_id": last_row["product_id"],
        "store_id": last_row["store_id"],
        "channel": last_row["channel"],
        "category": last_row["category"],
        "brand": last_row["brand"],
    }


def build_batch_predictions(run: AssessedRun) -> list[dict[str, object]]:
    if not run.panel:
        msg = "Assessed daily panel is empty."
        raise ValueError(msg)
    last_date = max(date.fromisoformat(str(row["date"])) for row in run.panel)
    origin = last_date + timedelta(days=1)
    horizon_days = int(run.metrics["horizon_days"])
    window_days = int(run.metrics["window_days"])
    min_history = int(run.inputs["model"]["min_history_observations"])
    if horizon_days <= 0 or window_days <= 0 or min_history <= 0:
        msg = "Invalid assessed forecast configuration."
        raise ValueError(msg)
    by_series: dict[tuple[str, str, str], list[dict[str, object]]] = defaultdict(list)
    for row in run.panel:
        key = (str(row["product_id"]), str(row["store_id"]), str(row["channel"]))
        by_series[key].append(row)
    generated_at = datetime.now(UTC).isoformat()
    pending: list[tuple[dict[str, object], int]] = []
    features: list[dict[str, object]] = []
    for series_rows in by_series.values():
        last = max(series_rows, key=lambda row: str(row["date"]))
        if date.fromisoformat(str(last["date"])) != last_date:
            continue
        if (
            last["is_active_assortment"] is not True
            or last["location_open"] is not True
            or last["source_data_complete"] is not True
        ):
            continue
        history = _history(series_rows, origin, window_days)
        if len(history) < min_history:
            continue
        for horizon_day in range(1, horizon_days + 1):
            target = _future_target(last, origin + timedelta(days=horizon_day - 1))
            pending.append((target, len(history)))
            features.append(
                build_training_features(
                    target,
                    history,
                    window_days=window_days,
                    origin=origin,
                ),
            )
    if not features:
        msg = "No eligible forecast series in the assessed panel."
        raise ValueError(msg)
    raw_predictions = run.model.predict(features)
    rows: list[dict[str, object]] = []
    for (target, history_rows), value in zip(pending, raw_predictions, strict=True):
        numeric_value = Decimal(str(value))
        if not numeric_value.is_finite():
            msg = "Assessed model returned a non-finite prediction."
            raise ValueError(msg)
        rows.append(
            {
                "experiment_id": run.metrics["experiment_id"],
                "run_id": run.metrics["run_id"],
                "model_id": run.metrics["model_id"],
                "feature_dataset_id": run.metrics["feature_dataset_id"],
                "origin": forecast_origin_utc(origin).isoformat(),
                "forecast_date": target["date"],
                "horizon_day": (date.fromisoformat(str(target["date"])) - origin).days + 1,
                "product_id": target["product_id"],
                "store_id": target["store_id"],
                "channel": target["channel"],
                "predicted_units": _quantity(numeric_value),
                "history_rows": history_rows,
                "generated_at": generated_at,
            }
        )
    return rows


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
    for (product_id, forecast_date), predictions in sorted(grouped.items()):
        quantity = sum(int(row["predicted_units"]) for row in predictions)
        training_rows = sum(int(row["history_rows"]) for row in predictions)
        model_id = str(predictions[0]["model_id"])
        if any(row["model_id"] != model_id for row in predictions):
            msg = "Cannot aggregate predictions from different model artifacts."
            raise ValueError(msg)
        natural_key = f"{model_id}:{product_id}:{forecast_date}:{quantity}"
        rows.append(
            {
                "id": deterministic_uuid("batch_api_forecast", natural_key),
                "product_id": product_id,
                "forecast_period_start": forecast_date,
                "forecast_period_end": forecast_date,
                "predicted_quantity": f"{Decimal(quantity):.3f}",
                "unit_of_measure": "pcs",
                "generated_at": predictions[0]["generated_at"],
                "method": FORECAST_METHOD,
                "status": "generated",
                "confidence_level": _confidence(training_rows, window_days),
            }
        )
    return rows


def build_batch_inference_manifest(
    run: AssessedRun,
    metadata: dict[str, object],
    batch_predictions: list[dict[str, object]],
    api_forecast_rows: list[dict[str, object]],
    metadata_output_dir: Path,
) -> dict[str, object]:
    if (
        any(
            metadata[key] != run.metrics[key]
            for key in ("model_id", "experiment_id", "run_id", "feature_dataset_id")
        )
        or metadata["source_run_manifest_sha256"] != run.manifest_sha256
    ):
        msg = "Batch metadata identity does not match the assessed artifact."
        raise ValueError(msg)
    dates = [str(row["forecast_date"]) for row in batch_predictions]
    return {
        "run_key": f"{run.metrics['run_id']}:{run.metrics['model_id']}:batch-inference",
        "job_name": "retailops-demand-rf-batch-inference",
        "model_name": MODEL_NAME,
        "model_version": MODEL_VERSION,
        "model_status": metadata["status"],
        "model_id": run.metrics["model_id"],
        "experiment_id": run.metrics["experiment_id"],
        "run_id": run.metrics["run_id"],
        "feature_dataset_id": run.metrics["feature_dataset_id"],
        "source_run_manifest_sha256": run.manifest_sha256,
        "predictions_logical_sha256": logical_rows_sha256(batch_predictions),
        "api_forecasts_logical_sha256": logical_rows_sha256(api_forecast_rows),
        "batch_prediction_count": len(batch_predictions),
        "api_forecast_count": len(api_forecast_rows),
        "forecast_date_start": min(dates),
        "forecast_date_end": max(dates),
        "origin": batch_predictions[0]["origin"],
        "metadata_output_dir": str(metadata_output_dir),
        "generated_at": batch_predictions[0]["generated_at"],
        "artifacts": [BATCH_PREDICTIONS_FILENAME, API_FORECASTS_FILENAME, BATCH_MANIFEST_FILENAME],
    }


def write_batch_inference_artifacts(
    output_dir: Path,
    batch_predictions: list[dict[str, object]],
    api_forecast_rows: list[dict[str, object]],
    manifest: dict[str, object],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / BATCH_PREDICTIONS_FILENAME).open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=BATCH_PREDICTION_COLUMNS)
        writer.writeheader()
        writer.writerows(batch_predictions)
    with (output_dir / API_FORECASTS_FILENAME).open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=API_FORECAST_COLUMNS)
        writer.writeheader()
        writer.writerows(api_forecast_rows)
    (output_dir / BATCH_MANIFEST_FILENAME).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load_verified_batch_manifest(output_dir: Path, run: AssessedRun) -> dict[str, object]:
    manifest = json.loads((output_dir / BATCH_MANIFEST_FILENAME).read_text(encoding="utf-8"))
    with (output_dir / BATCH_PREDICTIONS_FILENAME).open(newline="", encoding="utf-8") as file:
        predictions = list(csv.DictReader(file))
    with (output_dir / API_FORECASTS_FILENAME).open(newline="", encoding="utf-8") as file:
        api_rows = list(csv.DictReader(file))
    for row in predictions:
        for field in ("horizon_day", "predicted_units", "history_rows"):
            row[field] = int(row[field])
    identity = {
        "experiment_id": run.metrics["experiment_id"],
        "run_id": run.metrics["run_id"],
        "model_id": run.metrics["model_id"],
        "feature_dataset_id": run.metrics["feature_dataset_id"],
    }
    if (
        any(manifest.get(key) != value for key, value in identity.items())
        or any(any(row.get(key) != value for key, value in identity.items()) for row in predictions)
        or manifest.get("source_run_manifest_sha256") != run.manifest_sha256
        or manifest.get("batch_prediction_count") != len(predictions)
        or manifest.get("api_forecast_count") != len(api_rows)
        or manifest.get("predictions_logical_sha256") != logical_rows_sha256(predictions)
        or manifest.get("api_forecasts_logical_sha256") != logical_rows_sha256(api_rows)
    ):
        msg = "Batch artifacts do not match the assessed RF experiment."
        raise ValueError(msg)
    return manifest


def run_batch_inference(config: BatchInferenceConfig) -> dict[str, object]:
    run = load_assessed_run(config.experiment_dir)
    output_dir = config.output_dir or default_batch_output_dir(str(run.metrics["profile"]))
    if output_dir.resolve().is_relative_to(run.directory):
        msg = "Batch output must not modify the assessed experiment."
        raise ValueError(msg)
    metadata_output_dir = config.metadata_output_dir or default_metadata_output_dir(
        str(run.metrics["profile"]),
    )
    metadata = persist_verified_rf_metadata(run, metadata_output_dir)
    predictions = build_batch_predictions(run)
    api_rows = build_api_forecast_rows(predictions, window_days=int(run.metrics["window_days"]))
    manifest = build_batch_inference_manifest(
        run,
        metadata,
        predictions,
        api_rows,
        metadata_output_dir,
    )
    write_batch_inference_artifacts(output_dir, predictions, api_rows, manifest)
    load_verified_batch_manifest(output_dir, run)
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Forecast from one assessed RF artifact.")
    parser.add_argument("--experiment-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--metadata-output-dir", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = BatchInferenceConfig(
        experiment_dir=args.experiment_dir,
        output_dir=args.output_dir,
        metadata_output_dir=args.metadata_output_dir,
    )
    manifest = run_batch_inference(config)
    print(  # noqa: T201 - CLI output
        f"RetailOps assessed RF batch generated: {manifest['batch_prediction_count']} predictions",
    )
    print(f"Model ID: {manifest['model_id']}")  # noqa: T201 - CLI output


if __name__ == "__main__":
    main()
