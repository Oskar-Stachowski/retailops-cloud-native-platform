from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from ml.experiments.assessed_run import load_assessed_run
from ml.inference.batch_forecast import (
    BatchInferenceConfig,
    default_batch_output_dir,
    load_verified_batch_manifest,
    run_batch_inference,
)
from ml.metadata.model_registry import (
    MODEL_METADATA_FILENAME,
    default_metadata_output_dir,
)

MODEL_PERFORMANCE_METRICS_FILENAME = "model_performance.prom"
MODEL_PERFORMANCE_SNAPSHOT_FILENAME = "model_performance_snapshot.json"


@dataclass(frozen=True)
class ModelPerformanceMetricsConfig:
    experiment_dir: Path
    output_dir: Path | None = None
    metadata_output_dir: Path | None = None
    inference_output_dir: Path | None = None


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _label(value: object) -> str:
    return str(value).replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _labels(values: dict[str, object]) -> str:
    return ",".join(f'{key}="{_label(value)}"' for key, value in sorted(values.items()))


def _number(value: object) -> str | None:
    if value in (None, ""):
        return None
    try:
        return str(Decimal(str(value)))
    except InvalidOperation:
        return None


def _timestamp_seconds(value: object) -> str | None:
    if not value:
        return None
    raw_value = str(value)
    normalized = raw_value.replace("Z", "+00:00")
    try:
        timestamp = datetime.fromisoformat(normalized).timestamp()
    except ValueError:
        return None
    return str(int(timestamp))


def default_metrics_output_dir(profile: str) -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "data" / "synthetic" / profile / "observability" / "model_performance"


def build_model_performance_snapshot(
    evaluation_report: dict[str, object],
    model_metadata: dict[str, object],
    batch_manifest: dict[str, object],
) -> dict[str, object]:
    metrics = evaluation_report.get("trained_model_metrics")
    if not isinstance(metrics, dict):
        msg = "assessed RF metrics must be a dictionary."
        raise TypeError(msg)
    for key, metadata_key in (
        ("experiment_id", "experiment_id"),
        ("run_id", "run_id"),
        ("model_id", "model_id"),
        ("feature_dataset_id", "feature_dataset_id"),
    ):
        if not (evaluation_report[key] == model_metadata[metadata_key] == batch_manifest[key]):
            msg = f"Performance identity mismatch: {key}."
            raise ValueError(msg)
    if not (
        evaluation_report["model_status"]
        == model_metadata["status"]
        == batch_manifest["model_status"]
    ):
        msg = "Performance model status mismatch."
        raise ValueError(msg)
    if not (
        evaluation_report["model_name"]
        == model_metadata["model_name"]
        == batch_manifest["model_name"]
        and evaluation_report["model_version"]
        == model_metadata["model_version"]
        == batch_manifest["model_version"]
    ):
        msg = "Performance model family mismatch."
        raise ValueError(msg)
    if model_metadata["source_run_manifest_sha256"] != batch_manifest["source_run_manifest_sha256"]:
        msg = "Performance source run manifest mismatch."
        raise ValueError(msg)
    final_fold = next(
        fold for fold in evaluation_report["temporal_protocol"]["folds"] if fold["split"] == "test"
    )

    return {
        "snapshot_name": "retailops-demand-model-performance",
        "model_name": evaluation_report["model_name"],
        "model_version": evaluation_report["model_version"],
        "model_status": model_metadata["status"],
        "experiment_id": evaluation_report["experiment_id"],
        "run_id": evaluation_report["run_id"],
        "model_id": evaluation_report["model_id"],
        "profile": evaluation_report["profile"],
        "feature_dataset_id": evaluation_report["feature_dataset_id"],
        "evaluation": {
            "type": evaluation_report["evaluation_type"],
            "status": metrics["status"],
            "evaluated_rows": metrics["evaluated_rows"],
            "mape_evaluated_rows": metrics["mape_evaluated_rows"],
            "mape_coverage": metrics["mape_coverage"],
            "zero_actual_rows": metrics["zero_actual_rows"],
            "zero_actual_overforecast_units": metrics["zero_actual_overforecast_units"],
            "skipped_rows": final_fold["eligible_rows"] - final_fold["evaluated_rows"],
            "mae": metrics["mae"],
            "rmse": metrics["rmse"],
            "mape": metrics["mape"],
            "bias": metrics["bias"],
            "wape": metrics["wape"],
            "feature_row_count": evaluation_report["feature_row_count"],
            "evaluation_date_start": final_fold["target_start"],
            "evaluation_date_end": final_fold["target_end"],
        },
        "batch_inference": {
            "run_key": batch_manifest["run_key"],
            "batch_prediction_count": batch_manifest["batch_prediction_count"],
            "api_forecast_count": batch_manifest["api_forecast_count"],
            "forecast_date_start": batch_manifest["forecast_date_start"],
            "forecast_date_end": batch_manifest["forecast_date_end"],
        },
        "artifacts": {
            "metadata_model_id": model_metadata["model_id"],
            "metadata_output_dir": batch_manifest["metadata_output_dir"],
            "source_run_manifest_sha256": batch_manifest["source_run_manifest_sha256"],
        },
        "generated_at": batch_manifest["generated_at"],
    }


def _metric_block(name: str, help_text: str, metric_type: str, samples: list[str]) -> list[str]:
    return [
        f"# HELP {name} {help_text}",
        f"# TYPE {name} {metric_type}",
        *samples,
    ]


def _sample(name: str, labels: dict[str, object], value: object) -> str | None:
    numeric_value = _number(value)
    if numeric_value is None:
        return None
    return f"{name}{{{_labels(labels)}}} {numeric_value}"


def render_model_performance_metrics(snapshot: dict[str, object]) -> str:
    evaluation = snapshot["evaluation"]
    batch_inference = snapshot["batch_inference"]
    if not isinstance(evaluation, dict) or not isinstance(batch_inference, dict):
        msg = "snapshot evaluation and batch_inference must be dictionaries."
        raise TypeError(msg)

    base_labels = {
        "model_name": snapshot["model_name"],
        "model_version": snapshot["model_version"],
        "model_status": snapshot["model_status"],
        "experiment_id": snapshot["experiment_id"],
        "model_id": snapshot["model_id"],
        "run_id": snapshot["run_id"],
        "profile": snapshot["profile"],
        "feature_dataset_id": snapshot["feature_dataset_id"],
    }
    run_labels = {
        **base_labels,
        "run_key": batch_inference["run_key"],
    }
    lines: list[str] = []

    lines.extend(
        _metric_block(
            "retailops_model_info",
            "RetailOps model identity and lifecycle status.",
            "gauge",
            [f"retailops_model_info{{{_labels(base_labels)}}} 1"],
        ),
    )

    evaluation_metrics = {
        "retailops_model_evaluation_rows": (
            "Rows evaluated by the latest model performance report.",
            "evaluated_rows",
        ),
        "retailops_model_evaluation_skipped_rows": (
            "Rows skipped by the latest model performance report.",
            "skipped_rows",
        ),
        "retailops_model_evaluation_mae": (
            "Mean absolute error for the latest model evaluation.",
            "mae",
        ),
        "retailops_model_evaluation_rmse": (
            "Root mean squared error for the latest model evaluation.",
            "rmse",
        ),
        "retailops_model_evaluation_mape_percent": (
            "Mean absolute percentage error for the latest model evaluation.",
            "mape",
        ),
        "retailops_model_evaluation_mape_coverage": (
            "Fraction of evaluated rows with strictly positive actual units.",
            "mape_coverage",
        ),
        "retailops_model_evaluation_zero_actual_overforecast_units": (
            "Overforecast units on rows with zero actual demand.",
            "zero_actual_overforecast_units",
        ),
        "retailops_model_evaluation_bias": (
            "Average signed forecast bias for the latest model evaluation.",
            "bias",
        ),
        "retailops_model_evaluation_wape_percent": (
            "Weighted absolute percentage error for the latest model evaluation.",
            "wape",
        ),
        "retailops_model_feature_rows": (
            "Feature rows available to the latest model evaluation.",
            "feature_row_count",
        ),
    }
    for metric_name, (help_text, key) in evaluation_metrics.items():
        sample = _sample(metric_name, base_labels, evaluation[key])
        if sample is not None:
            lines.extend(_metric_block(metric_name, help_text, "gauge", [sample]))

    inference_metrics = {
        "retailops_model_batch_predictions_total": (
            "Batch prediction rows emitted by the latest inference run.",
            "batch_prediction_count",
        ),
        "retailops_model_api_forecasts_total": (
            "API-shaped forecast rows emitted by the latest inference run.",
            "api_forecast_count",
        ),
    }
    for metric_name, (help_text, key) in inference_metrics.items():
        sample = _sample(metric_name, run_labels, batch_inference[key])
        if sample is not None:
            lines.extend(_metric_block(metric_name, help_text, "gauge", [sample]))

    generated_at = _timestamp_seconds(snapshot["generated_at"])
    if generated_at is not None:
        lines.extend(
            _metric_block(
                "retailops_model_artifact_generated_timestamp_seconds",
                "Unix timestamp for the latest generated model performance artifact.",
                "gauge",
                [
                    (
                        "retailops_model_artifact_generated_timestamp_seconds"
                        f"{{{_labels(run_labels)}}} {generated_at}"
                    ),
                ],
            ),
        )

    return "\n".join(lines) + "\n"


def write_model_performance_artifacts(
    output_dir: Path,
    snapshot: dict[str, object],
    metrics_text: str,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / MODEL_PERFORMANCE_SNAPSHOT_FILENAME).write_text(
        json.dumps(snapshot, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / MODEL_PERFORMANCE_METRICS_FILENAME).write_text(
        metrics_text,
        encoding="utf-8",
    )


def generate_model_performance_metrics(
    config: ModelPerformanceMetricsConfig,
) -> dict[str, object]:
    run = load_assessed_run(config.experiment_dir)
    profile = str(run.metrics["profile"])
    inference_dir = config.inference_output_dir or default_batch_output_dir(profile)
    metadata_dir = config.metadata_output_dir or default_metadata_output_dir(profile)
    output_dir = config.output_dir or default_metrics_output_dir(profile)
    if output_dir.resolve().is_relative_to(run.directory):
        msg = "Metrics output must not modify the assessed experiment."
        raise ValueError(msg)
    run_batch_inference(
        BatchInferenceConfig(
            experiment_dir=config.experiment_dir,
            output_dir=inference_dir,
            metadata_output_dir=metadata_dir,
        ),
    )
    snapshot = build_model_performance_snapshot(
        run.metrics,
        _load_json(metadata_dir / MODEL_METADATA_FILENAME),
        load_verified_batch_manifest(inference_dir, run),
    )
    metrics_text = render_model_performance_metrics(snapshot)
    write_model_performance_artifacts(output_dir, snapshot, metrics_text)
    return snapshot


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate performance metrics from one assessed RF experiment.",
    )
    parser.add_argument("--experiment-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--metadata-output-dir", type=Path)
    parser.add_argument("--inference-output-dir", type=Path)
    return parser.parse_args()


def config_from_args(args: argparse.Namespace) -> ModelPerformanceMetricsConfig:
    return ModelPerformanceMetricsConfig(
        experiment_dir=args.experiment_dir,
        output_dir=args.output_dir,
        metadata_output_dir=args.metadata_output_dir,
        inference_output_dir=args.inference_output_dir,
    )


def main() -> None:
    config = config_from_args(parse_args())
    snapshot = generate_model_performance_metrics(config)
    output_dir = config.output_dir or default_metrics_output_dir(str(snapshot["profile"]))

    print(  # noqa: T201 - CLI output
        "RetailOps model performance metrics generated: "
        f"{snapshot['model_name']} {snapshot['model_version']}",
    )
    print(f"Output directory: {output_dir}")  # noqa: T201 - CLI output


if __name__ == "__main__":
    main()
