from __future__ import annotations

import json

import pytest

from data.generator.main import DatasetGenerationConfig
from ml.evaluation.baseline_report import EvaluationConfig, generate_baseline_evaluation_report
from ml.metadata.model_registry import (
    DEFAULT_MODEL_STATUS,
    MODEL_METADATA_FILENAME,
    MODEL_REGISTRY_FILENAME,
    ModelMetadataConfig,
    build_model_metadata,
    generate_and_persist_model_metadata,
    persist_model_metadata,
)
from ml.models.baseline_forecast import BaselineForecastConfig, train_baseline_forecast_model


def test_model_metadata_captures_lineage_metrics_and_artifacts(tmp_path) -> None:
    dataset = DatasetGenerationConfig(
        profile="small",
        days=5,
        products=6,
        stores=2,
        warehouses=2,
        seed=42,
    )
    model_output_dir = tmp_path / "model"
    evaluation_output_dir = tmp_path / "evaluation"
    model_manifest = train_baseline_forecast_model(
        BaselineForecastConfig(
            dataset=dataset,
            window_days=7,
            horizon_days=2,
            output_dir=model_output_dir,
        ),
    )
    evaluation_report = generate_baseline_evaluation_report(
        EvaluationConfig(
            dataset=dataset,
            window_days=7,
            holdout_days=2,
            output_dir=evaluation_output_dir,
        ),
    )
    metadata = build_model_metadata(
        ModelMetadataConfig(
            dataset=dataset,
            window_days=7,
            horizon_days=2,
            holdout_days=2,
            status="candidate",
            model_output_dir=model_output_dir,
            evaluation_output_dir=evaluation_output_dir,
        ),
        model_manifest,
        evaluation_report,
    )

    assert metadata["metadata_schema_version"] == "1.0"
    assert metadata["model_id"]
    assert metadata["status"] == "candidate"
    assert metadata["feature_dataset_id"] == model_manifest["feature_dataset_id"]
    assert metadata["evaluation"]["metrics"] == evaluation_report["metrics"]
    assert metadata["training"]["forecast_row_count"] == model_manifest["forecast_row_count"]
    assert metadata["artifacts"]["model_manifest"].endswith("model_manifest.json")
    assert metadata["artifacts"]["evaluation_report"].endswith("evaluation_report.json")


def test_model_metadata_rejects_unknown_status(tmp_path) -> None:
    with pytest.raises(ValueError, match="Unsupported model status"):
        generate_and_persist_model_metadata(
            ModelMetadataConfig(
                dataset=DatasetGenerationConfig(profile="demo"),
                status="production",
                output_dir=tmp_path,
            ),
        )


def test_model_registry_upserts_by_model_version_and_dataset(tmp_path) -> None:
    first = {
        "model_name": "model",
        "model_version": "v1",
        "feature_dataset_id": "dataset-1",
        "status": "experimental",
        "created_at": "2026-05-13T00:00:00Z",
    }
    second = {
        **first,
        "status": "candidate",
        "created_at": "2026-05-13T01:00:00Z",
    }

    persist_model_metadata(tmp_path, first)
    persist_model_metadata(tmp_path, second)

    metadata = json.loads((tmp_path / MODEL_METADATA_FILENAME).read_text(encoding="utf-8"))
    registry_lines = (tmp_path / MODEL_REGISTRY_FILENAME).read_text(encoding="utf-8").splitlines()

    assert metadata["status"] == "candidate"
    assert len(registry_lines) == 1
    assert json.loads(registry_lines[0])["status"] == "candidate"


def test_model_metadata_job_writes_metadata_registry_and_upstream_artifacts(tmp_path) -> None:
    metadata_dir = tmp_path / "metadata"
    model_dir = tmp_path / "model"
    evaluation_dir = tmp_path / "evaluation"
    config = ModelMetadataConfig(
        dataset=DatasetGenerationConfig(
            profile="small",
            days=5,
            products=6,
            stores=2,
            warehouses=2,
            seed=123,
        ),
        window_days=7,
        horizon_days=2,
        holdout_days=2,
        status=DEFAULT_MODEL_STATUS,
        output_dir=metadata_dir,
        model_output_dir=model_dir,
        evaluation_output_dir=evaluation_dir,
    )

    metadata = generate_and_persist_model_metadata(config)
    written_metadata = json.loads(
        (metadata_dir / MODEL_METADATA_FILENAME).read_text(encoding="utf-8"),
    )
    registry_lines = (metadata_dir / MODEL_REGISTRY_FILENAME).read_text(
        encoding="utf-8",
    ).splitlines()

    assert written_metadata["model_id"] == metadata["model_id"]
    assert len(registry_lines) == 1
    assert (model_dir / "model_manifest.json").exists()
    assert (evaluation_dir / "evaluation_report.json").exists()
    assert written_metadata["evaluation"]["evaluated_rows"] > 0
