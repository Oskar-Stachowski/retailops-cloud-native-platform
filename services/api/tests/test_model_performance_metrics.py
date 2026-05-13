from __future__ import annotations

import json

from data.generator.main import DatasetGenerationConfig
from ml.observability.model_performance_metrics import (
    MODEL_PERFORMANCE_METRICS_FILENAME,
    MODEL_PERFORMANCE_SNAPSHOT_FILENAME,
    ModelPerformanceMetricsConfig,
    build_model_performance_snapshot,
    generate_model_performance_metrics,
    render_model_performance_metrics,
)


def test_model_performance_metrics_render_prometheus_text() -> None:
    evaluation_report = {
        "model_name": "retailops-demand-baseline",
        "model_version": "v1",
        "evaluation_type": "rolling_holdout_backtest",
        "profile": "small",
        "feature_dataset_id": "dataset-1",
        "feature_row_count": 100,
        "skipped_rows": 2,
        "evaluation_date_start": "2026-05-01",
        "evaluation_date_end": "2026-05-07",
        "metrics": {
            "evaluated_rows": 98,
            "mae": "4.2500",
            "rmse": "5.5000",
            "mape": "12.7500",
            "bias": "-0.5000",
            "wape": "10.2500",
        },
    }
    model_metadata = {
        "model_id": "model-1",
        "status": "candidate",
    }
    batch_manifest = {
        "run_key": "v1:dataset-1:batch-inference",
        "batch_prediction_count": 42,
        "api_forecast_count": 7,
        "forecast_date_start": "2026-05-08",
        "forecast_date_end": "2026-05-14",
        "metadata_output_dir": "/tmp/metadata",
        "generated_at": "2026-05-13T10:00:00+00:00",
    }

    snapshot = build_model_performance_snapshot(
        evaluation_report,
        model_metadata,
        batch_manifest,
    )
    metrics_text = render_model_performance_metrics(snapshot)

    assert "# TYPE retailops_model_info gauge" in metrics_text
    assert 'model_status="candidate"' in metrics_text
    assert (
        'retailops_model_evaluation_mae{feature_dataset_id="dataset-1",model_name='
        '"retailops-demand-baseline",model_status="candidate",model_version="v1",profile="small"}'
        " 4.2500"
    ) in metrics_text
    assert "retailops_model_evaluation_mape_percent" in metrics_text
    assert "retailops_model_evaluation_wape_percent" in metrics_text
    assert "retailops_model_api_forecasts_total" in metrics_text
    assert "retailops_model_artifact_generated_timestamp_seconds" in metrics_text


def test_model_performance_metrics_job_writes_snapshot_and_prometheus_artifact(tmp_path) -> None:
    output_dir = tmp_path / "metrics"
    config = ModelPerformanceMetricsConfig(
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
        model_status="candidate",
        output_dir=output_dir,
        metadata_output_dir=tmp_path / "metadata",
        model_output_dir=tmp_path / "model",
        evaluation_output_dir=tmp_path / "evaluation",
        inference_output_dir=tmp_path / "inference",
    )

    snapshot = generate_model_performance_metrics(config)
    written_snapshot = json.loads(
        (output_dir / MODEL_PERFORMANCE_SNAPSHOT_FILENAME).read_text(encoding="utf-8"),
    )
    metrics_text = (output_dir / MODEL_PERFORMANCE_METRICS_FILENAME).read_text(
        encoding="utf-8",
    )

    assert written_snapshot["model_version"] == snapshot["model_version"]
    assert written_snapshot["model_status"] == "candidate"
    assert written_snapshot["evaluation"]["evaluated_rows"] > 0
    assert "retailops_model_evaluation_rmse" in metrics_text
    assert "retailops_model_batch_predictions_total" in metrics_text
