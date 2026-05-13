from __future__ import annotations

import csv
import json

from data.generator.main import DatasetGenerationConfig, build_dataset
from ml.features.demand_forecast import build_demand_feature_rows
from ml.inference.batch_forecast import (
    API_FORECASTS_FILENAME,
    BATCH_MANIFEST_FILENAME,
    BATCH_PREDICTIONS_FILENAME,
    FORECAST_METHOD,
    BatchInferenceConfig,
    build_api_forecast_rows,
    build_batch_inference_manifest,
    run_batch_inference,
)
from ml.metadata.model_registry import ModelMetadataConfig, generate_and_persist_model_metadata
from ml.models.baseline_forecast import MODEL_VERSION, build_baseline_forecasts


def test_batch_inference_aggregates_series_predictions_to_api_forecasts() -> None:
    predictions = [
        {
            "product_id": "product-1",
            "forecast_date": "2026-05-01",
            "predicted_units": 3,
            "training_rows": 2,
            "trained_at": "2026-04-30T00:00:00Z",
        },
        {
            "product_id": "product-1",
            "forecast_date": "2026-05-01",
            "predicted_units": 4,
            "training_rows": 3,
            "trained_at": "2026-04-30T00:00:00Z",
        },
    ]

    rows = build_api_forecast_rows(predictions, window_days=7)

    assert len(rows) == 1
    assert rows[0]["product_id"] == "product-1"
    assert rows[0]["forecast_period_start"] == "2026-05-01"
    assert rows[0]["forecast_period_end"] == "2026-05-01"
    assert rows[0]["predicted_quantity"] == "7.000"
    assert rows[0]["method"] == FORECAST_METHOD
    assert rows[0]["status"] == "generated"


def test_batch_inference_manifest_links_model_metadata_and_forecast_counts(tmp_path) -> None:
    dataset = DatasetGenerationConfig(
        profile="small",
        days=5,
        products=6,
        stores=2,
        warehouses=2,
        seed=42,
    )
    config = BatchInferenceConfig(
        dataset=dataset,
        window_days=7,
        horizon_days=2,
        holdout_days=2,
        metadata_output_dir=tmp_path / "metadata",
    )
    metadata = generate_and_persist_model_metadata(
        ModelMetadataConfig(
            dataset=dataset,
            window_days=7,
            horizon_days=2,
            holdout_days=2,
            status="candidate",
            output_dir=tmp_path / "metadata",
            model_output_dir=tmp_path / "model",
            evaluation_output_dir=tmp_path / "evaluation",
        ),
    )
    feature_rows = build_demand_feature_rows(build_dataset(dataset), dataset)
    predictions = build_baseline_forecasts(feature_rows, window_days=7, horizon_days=2)
    api_rows = build_api_forecast_rows(predictions, window_days=7)
    manifest = build_batch_inference_manifest(config, metadata, predictions, api_rows)

    assert manifest["model_version"] == MODEL_VERSION
    assert manifest["model_status"] == "candidate"
    assert manifest["feature_dataset_id"] == metadata["feature_dataset_id"]
    assert manifest["batch_prediction_count"] == len(predictions)
    assert manifest["api_forecast_count"] == len(api_rows)
    assert manifest["forecast_date_start"] <= manifest["forecast_date_end"]


def test_batch_inference_job_writes_predictions_api_forecasts_and_manifest(tmp_path) -> None:
    output_dir = tmp_path / "inference"
    config = BatchInferenceConfig(
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
    )

    manifest = run_batch_inference(config)
    batch_predictions = list(
        csv.DictReader((output_dir / BATCH_PREDICTIONS_FILENAME).open(encoding="utf-8")),
    )
    api_forecasts = list(
        csv.DictReader((output_dir / API_FORECASTS_FILENAME).open(encoding="utf-8")),
    )
    written_manifest = json.loads(
        (output_dir / BATCH_MANIFEST_FILENAME).read_text(encoding="utf-8"),
    )

    assert batch_predictions
    assert api_forecasts
    assert len(batch_predictions) == manifest["batch_prediction_count"]
    assert len(api_forecasts) == manifest["api_forecast_count"]
    assert written_manifest["run_key"] == manifest["run_key"]
    assert api_forecasts[0]["method"] == FORECAST_METHOD
