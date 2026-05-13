from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from data.generator.common import deterministic_uuid
from data.generator.main import DatasetGenerationConfig
from ml.evaluation.baseline_report import (
    EvaluationConfig,
    default_evaluation_output_dir,
    generate_baseline_evaluation_report,
)
from ml.models.baseline_forecast import (
    BaselineForecastConfig,
    default_model_output_dir,
    train_baseline_forecast_model,
)

MODEL_METADATA_FILENAME = "model_metadata.json"
MODEL_REGISTRY_FILENAME = "model_registry.jsonl"
DEFAULT_MODEL_STATUS = "experimental"
SUPPORTED_MODEL_STATUSES = {
    "experimental",
    "candidate",
    "approved",
    "rejected",
    "retraining_required",
}


@dataclass(frozen=True)
class ModelMetadataConfig:
    dataset: DatasetGenerationConfig = field(
        default_factory=lambda: DatasetGenerationConfig(profile="demo"),
    )
    window_days: int = 28
    horizon_days: int = 7
    holdout_days: int = 7
    status: str = DEFAULT_MODEL_STATUS
    output_dir: Path | None = None
    model_output_dir: Path | None = None
    evaluation_output_dir: Path | None = None


def default_metadata_output_dir(profile: str) -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "data" / "synthetic" / profile / "metadata" / "model_registry"


def _validate_status(status: str) -> None:
    if status not in SUPPORTED_MODEL_STATUSES:
        supported = ", ".join(sorted(SUPPORTED_MODEL_STATUSES))
        msg = f"Unsupported model status '{status}'. Supported statuses: {supported}."
        raise ValueError(msg)


def _metadata_natural_key(
    model_manifest: dict[str, object],
    evaluation_report: dict[str, object],
) -> str:
    return ":".join(
        [
            str(model_manifest["model_name"]),
            str(model_manifest["model_version"]),
            str(model_manifest["feature_dataset_id"]),
            str(evaluation_report["evaluation_type"]),
        ],
    )


def build_model_metadata(
    config: ModelMetadataConfig,
    model_manifest: dict[str, object],
    evaluation_report: dict[str, object],
) -> dict[str, object]:
    _validate_status(config.status)
    natural_key = _metadata_natural_key(model_manifest, evaluation_report)
    model_output_dir = config.model_output_dir or default_model_output_dir(config.dataset.profile)
    evaluation_output_dir = config.evaluation_output_dir or default_evaluation_output_dir(
        config.dataset.profile,
    )

    return {
        "metadata_schema_version": "1.0",
        "model_id": deterministic_uuid("model_metadata", natural_key),
        "model_name": model_manifest["model_name"],
        "model_version": model_manifest["model_version"],
        "model_type": model_manifest["model_type"],
        "status": config.status,
        "profile": config.dataset.profile,
        "seed": config.dataset.seed,
        "feature_dataset_name": model_manifest["feature_dataset_name"],
        "feature_dataset_id": model_manifest["feature_dataset_id"],
        "feature_grain": model_manifest["feature_grain"],
        "target": model_manifest["target"],
        "training": {
            "window_days": config.window_days,
            "horizon_days": config.horizon_days,
            "feature_row_count": model_manifest["feature_row_count"],
            "forecast_row_count": model_manifest["forecast_row_count"],
            "feature_date_start": model_manifest["feature_date_start"],
            "feature_date_end": model_manifest["feature_date_end"],
            "forecast_date_start": model_manifest["forecast_date_start"],
            "forecast_date_end": model_manifest["forecast_date_end"],
            "trained_at": model_manifest["trained_at"],
        },
        "evaluation": {
            "type": evaluation_report["evaluation_type"],
            "holdout_days": config.holdout_days,
            "feature_row_count": evaluation_report["feature_row_count"],
            "evaluated_rows": evaluation_report["metrics"]["evaluated_rows"],
            "skipped_rows": evaluation_report["skipped_rows"],
            "date_start": evaluation_report["evaluation_date_start"],
            "date_end": evaluation_report["evaluation_date_end"],
            "metrics": evaluation_report["metrics"],
            "generated_at": evaluation_report["generated_at"],
        },
        "artifacts": {
            "model_output_dir": str(model_output_dir),
            "model_manifest": str(model_output_dir / "model_manifest.json"),
            "baseline_forecasts": str(model_output_dir / "baseline_forecasts.csv"),
            "evaluation_output_dir": str(evaluation_output_dir),
            "evaluation_report": str(evaluation_output_dir / "evaluation_report.json"),
            "evaluation_summary": str(evaluation_output_dir / "evaluation_summary.md"),
            "backtest_predictions": str(evaluation_output_dir / "backtest_predictions.csv"),
        },
        "created_at": datetime.now(UTC).isoformat(),
    }


def _read_registry(registry_path: Path) -> list[dict[str, object]]:
    if not registry_path.exists():
        return []

    records: list[dict[str, object]] = []
    for line in registry_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def _registry_key(record: dict[str, object]) -> tuple[str, str, str]:
    return (
        str(record["model_name"]),
        str(record["model_version"]),
        str(record["feature_dataset_id"]),
    )


def persist_model_metadata(
    output_dir: Path,
    metadata: dict[str, object],
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = output_dir / MODEL_METADATA_FILENAME
    registry_path = output_dir / MODEL_REGISTRY_FILENAME
    existing_records = _read_registry(registry_path)
    metadata_key = _registry_key(metadata)
    records_by_key = {_registry_key(record): record for record in existing_records}
    records_by_key[metadata_key] = metadata
    records = [records_by_key[key] for key in sorted(records_by_key)]

    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    registry_path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )

    return {
        "metadata": metadata_path,
        "registry": registry_path,
    }


def generate_and_persist_model_metadata(config: ModelMetadataConfig) -> dict[str, object]:
    _validate_status(config.status)
    model_output_dir = config.model_output_dir or default_model_output_dir(config.dataset.profile)
    evaluation_output_dir = config.evaluation_output_dir or default_evaluation_output_dir(
        config.dataset.profile,
    )
    model_manifest = train_baseline_forecast_model(
        BaselineForecastConfig(
            dataset=config.dataset,
            window_days=config.window_days,
            horizon_days=config.horizon_days,
            output_dir=model_output_dir,
        ),
    )
    evaluation_report = generate_baseline_evaluation_report(
        EvaluationConfig(
            dataset=config.dataset,
            window_days=config.window_days,
            holdout_days=config.holdout_days,
            output_dir=evaluation_output_dir,
        ),
    )
    metadata = build_model_metadata(config, model_manifest, evaluation_report)
    output_dir = config.output_dir or default_metadata_output_dir(config.dataset.profile)
    persist_model_metadata(output_dir, metadata)
    return metadata


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Persist RetailOps model metadata to the local model registry.",
    )
    parser.add_argument("--profile", choices=("demo", "small", "medium", "large"), default="demo")
    parser.add_argument("--days", type=int)
    parser.add_argument("--products", type=int)
    parser.add_argument("--stores", type=int)
    parser.add_argument("--warehouses", type=int)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--window-days", type=int, default=28)
    parser.add_argument("--horizon-days", type=int, default=7)
    parser.add_argument("--holdout-days", type=int, default=7)
    parser.add_argument("--status", default=DEFAULT_MODEL_STATUS)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--model-output-dir", type=Path)
    parser.add_argument("--evaluation-output-dir", type=Path)
    return parser.parse_args()


def config_from_args(args: argparse.Namespace) -> ModelMetadataConfig:
    return ModelMetadataConfig(
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
        status=args.status,
        output_dir=args.output_dir,
        model_output_dir=args.model_output_dir,
        evaluation_output_dir=args.evaluation_output_dir,
    )


def main() -> None:
    config = config_from_args(parse_args())
    metadata = generate_and_persist_model_metadata(config)
    output_dir = config.output_dir or default_metadata_output_dir(config.dataset.profile)

    print(  # noqa: T201 - CLI output
        f"RetailOps model metadata persisted: {metadata['model_version']} ({metadata['status']})",
    )
    print(f"Output directory: {output_dir}")  # noqa: T201 - CLI output


if __name__ == "__main__":
    main()
