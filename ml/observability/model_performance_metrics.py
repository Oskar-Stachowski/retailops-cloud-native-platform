from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from data.generator.main import DatasetGenerationConfig
from ml.evaluation.baseline_report import (
    EVALUATION_REPORT_FILENAME,
    default_evaluation_output_dir,
)
from ml.inference.batch_forecast import (
    BATCH_MANIFEST_FILENAME,
    DEFAULT_HOLDOUT_DAYS,
    DEFAULT_HORIZON_DAYS,
    DEFAULT_MODEL_STATUS,
    DEFAULT_WINDOW_DAYS,
    BatchInferenceConfig,
    default_batch_output_dir,
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
    metrics = evaluation_report.get("metrics")
    if not isinstance(metrics, dict):
        msg = "evaluation_report metrics must be a dictionary."
        raise TypeError(msg)

    return {
        "snapshot_name": "retailops-demand-model-performance",
        "model_name": evaluation_report["model_name"],
        "model_version": evaluation_report["model_version"],
        "model_status": model_metadata["status"],
        "profile": evaluation_report["profile"],
        "feature_dataset_id": evaluation_report["feature_dataset_id"],
        "evaluation": {
            "type": evaluation_report["evaluation_type"],
            "evaluated_rows": metrics["evaluated_rows"],
            "skipped_rows": evaluation_report["skipped_rows"],
            "mae": metrics["mae"],
            "rmse": metrics["rmse"],
            "mape": metrics["mape"],
            "bias": metrics["bias"],
            "wape": metrics["wape"],
            "feature_row_count": evaluation_report["feature_row_count"],
            "evaluation_date_start": evaluation_report["evaluation_date_start"],
            "evaluation_date_end": evaluation_report["evaluation_date_end"],
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
                    "retailops_model_artifact_generated_timestamp_seconds"
                    f"{{{_labels(run_labels)}}} {generated_at}",
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
    run_batch_inference(
        BatchInferenceConfig(
            dataset=config.dataset,
            window_days=config.window_days,
            horizon_days=config.horizon_days,
            holdout_days=config.holdout_days,
            model_status=config.model_status,
            output_dir=config.inference_output_dir,
            metadata_output_dir=config.metadata_output_dir,
            model_output_dir=config.model_output_dir,
            evaluation_output_dir=config.evaluation_output_dir,
        ),
    )
    metadata_dir = config.metadata_output_dir or default_metadata_output_dir(config.dataset.profile)
    evaluation_dir = config.evaluation_output_dir or default_evaluation_output_dir(
        config.dataset.profile,
    )
    inference_dir = config.inference_output_dir or default_batch_output_dir(config.dataset.profile)

    snapshot = build_model_performance_snapshot(
        _load_json(evaluation_dir / EVALUATION_REPORT_FILENAME),
        _load_json(metadata_dir / MODEL_METADATA_FILENAME),
        _load_json(inference_dir / BATCH_MANIFEST_FILENAME),
    )
    metrics_text = render_model_performance_metrics(snapshot)
    output_dir = config.output_dir or default_metrics_output_dir(config.dataset.profile)
    write_model_performance_artifacts(output_dir, snapshot, metrics_text)
    return snapshot


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate RetailOps model performance metrics for Prometheus textfile ingestion.",
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
    parser.add_argument("--inference-output-dir", type=Path)
    return parser.parse_args()


def config_from_args(args: argparse.Namespace) -> ModelPerformanceMetricsConfig:
    return ModelPerformanceMetricsConfig(
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
        inference_output_dir=args.inference_output_dir,
    )


def main() -> None:
    config = config_from_args(parse_args())
    snapshot = generate_model_performance_metrics(config)
    output_dir = config.output_dir or default_metrics_output_dir(config.dataset.profile)

    print(  # noqa: T201 - CLI output
        "RetailOps model performance metrics generated: "
        f"{snapshot['model_name']} {snapshot['model_version']}",
    )
    print(f"Output directory: {output_dir}")  # noqa: T201 - CLI output


if __name__ == "__main__":
    main()
