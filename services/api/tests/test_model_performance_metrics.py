from __future__ import annotations

import json

import pytest

from ml.observability.model_performance_metrics import (
    MODEL_PERFORMANCE_METRICS_FILENAME,
    MODEL_PERFORMANCE_SNAPSHOT_FILENAME,
    ModelPerformanceMetricsConfig,
    build_model_performance_snapshot,
    generate_model_performance_metrics,
    render_model_performance_metrics,
)


def _reports() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    evaluation_report = {
        "model_name": "retailops-demand-random-forest",
        "model_version": "random-forest-v3",
        "model_status": "rejected",
        "experiment_id": "rf-1",
        "run_id": "run-1",
        "model_id": "sha256:model",
        "evaluation_type": "fixed_origin_horizon",
        "profile": "small",
        "feature_dataset_id": "dataset-1",
        "feature_row_count": 100,
        "temporal_protocol": {"folds": [{
            "split": "test", "eligible_rows": 100, "evaluated_rows": 98,
            "target_start": "2026-05-01", "target_end": "2026-05-07",
        }]},
        "trained_model_metrics": {
            "status": "evaluable", "evaluated_rows": 98,
            "mape_evaluated_rows": 80, "mape_coverage": "0.8163",
            "zero_actual_rows": 18, "zero_actual_overforecast_units": "42.0000",
            "mae": "4.2500", "rmse": "5.5000", "mape": "12.7500",
            "bias": "-0.5000", "wape": "10.2500",
        },
    }
    model_metadata = {
        "model_name": "retailops-demand-random-forest",
        "model_version": "random-forest-v3",
        "model_id": "sha256:model", "experiment_id": "rf-1", "run_id": "run-1",
        "feature_dataset_id": "dataset-1", "status": "rejected",
        "source_run_manifest_sha256": "manifest-hash",
    }
    batch_manifest = {
        "model_name": "retailops-demand-random-forest",
        "model_version": "random-forest-v3",
        "run_key": "run-1:sha256:model:batch-inference",
        "model_id": "sha256:model", "experiment_id": "rf-1", "run_id": "run-1",
        "feature_dataset_id": "dataset-1", "model_status": "rejected",
        "source_run_manifest_sha256": "manifest-hash",
        "batch_prediction_count": 42, "api_forecast_count": 7,
        "forecast_date_start": "2026-05-08", "forecast_date_end": "2026-05-14",
        "metadata_output_dir": "/tmp/metadata", "generated_at": "2026-05-13T10:00:00+00:00",
    }
    return evaluation_report, model_metadata, batch_manifest


def test_model_performance_metrics_render_assessed_rf_identity() -> None:
    snapshot = build_model_performance_snapshot(*_reports())
    metrics_text = render_model_performance_metrics(snapshot)
    assert snapshot["model_id"] == "sha256:model"
    assert snapshot["experiment_id"] == "rf-1"
    assert snapshot["evaluation"]["skipped_rows"] == 2
    assert 'model_status="rejected"' in metrics_text
    assert 'experiment_id="rf-1"' in metrics_text
    assert 'model_id="sha256:model"' in metrics_text
    assert "retailops_model_evaluation_wape_percent" in metrics_text
    assert "retailops_model_batch_predictions_total" in metrics_text

    snapshot["evaluation"]["wape"] = None
    snapshot["evaluation"]["mape"] = None
    undefined_text = render_model_performance_metrics(snapshot)
    assert "retailops_model_evaluation_wape_percent" not in undefined_text
    assert "retailops_model_evaluation_mape_percent" not in undefined_text


def test_performance_snapshot_rejects_mismatched_model_identity() -> None:
    report, metadata, batch = _reports()
    batch["model_id"] = "sha256:wrong"
    with pytest.raises(ValueError, match="model_id"):
        build_model_performance_snapshot(report, metadata, batch)


def test_model_performance_job_reads_assessed_run(assessed_rf_run_dir, tmp_path) -> None:
    output_dir = tmp_path / "metrics"
    snapshot = generate_model_performance_metrics(ModelPerformanceMetricsConfig(
        experiment_dir=assessed_rf_run_dir,
        output_dir=output_dir,
        metadata_output_dir=tmp_path / "metadata",
        inference_output_dir=tmp_path / "inference",
    ))
    written = json.loads((output_dir / MODEL_PERFORMANCE_SNAPSHOT_FILENAME).read_text())
    metrics_text = (output_dir / MODEL_PERFORMANCE_METRICS_FILENAME).read_text()
    assert written == snapshot
    assert snapshot["model_name"] == "retailops-demand-random-forest"
    assert snapshot["model_id"].startswith("sha256:")
    assert snapshot["evaluation"]["evaluated_rows"] > 0
    assert "retailops_model_evaluation_rmse" in metrics_text
