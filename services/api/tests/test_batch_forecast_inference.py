from __future__ import annotations

import csv
import json

import pytest

from app.domain.models import Forecast
from ml.inference.batch_forecast import (
    API_FORECASTS_FILENAME,
    BATCH_MANIFEST_FILENAME,
    BATCH_PREDICTIONS_FILENAME,
    FORECAST_METHOD,
    BatchInferenceConfig,
    build_api_forecast_rows,
    run_batch_inference,
)


def test_batch_inference_aggregates_series_predictions_to_api_forecasts() -> None:
    predictions = [
        {
            "product_id": "product-1", "forecast_date": "2026-05-01",
            "predicted_units": 3, "history_rows": 2,
            "model_id": "sha256:model", "generated_at": "2026-04-30T00:00:00Z",
        },
        {
            "product_id": "product-1", "forecast_date": "2026-05-01",
            "predicted_units": 4, "history_rows": 3,
            "model_id": "sha256:model", "generated_at": "2026-04-30T00:00:00Z",
        },
    ]
    rows = build_api_forecast_rows(predictions, window_days=7)
    assert len(rows) == 1
    assert rows[0]["predicted_quantity"] == "7.000"
    assert rows[0]["method"] == FORECAST_METHOD
    assert rows[0]["status"] == "generated"

    predictions[1]["model_id"] = "sha256:different"
    with pytest.raises(ValueError, match="different model artifacts"):
        build_api_forecast_rows(predictions, window_days=7)


def test_batch_inference_writes_forecasts_from_assessed_rf(assessed_rf_run_dir, tmp_path) -> None:
    output_dir = tmp_path / "inference"
    manifest = run_batch_inference(BatchInferenceConfig(
        experiment_dir=assessed_rf_run_dir,
        output_dir=output_dir,
        metadata_output_dir=tmp_path / "metadata",
    ))
    batch_predictions = list(csv.DictReader((output_dir / BATCH_PREDICTIONS_FILENAME).open()))
    api_forecasts = list(csv.DictReader((output_dir / API_FORECASTS_FILENAME).open()))
    written_manifest = json.loads((output_dir / BATCH_MANIFEST_FILENAME).read_text())
    assert batch_predictions
    assert api_forecasts
    assert len(batch_predictions) == manifest["batch_prediction_count"]
    assert len(api_forecasts) == manifest["api_forecast_count"]
    assert written_manifest == manifest
    assert manifest["model_id"] == batch_predictions[0]["model_id"]
    assert {row["model_id"] for row in batch_predictions} == {manifest["model_id"]}
    assert api_forecasts[0]["method"] == FORECAST_METHOD
    assert len({row["id"] for row in api_forecasts}) == len(api_forecasts)
    assert len({
        (row["product_id"], row["forecast_period_start"])
        for row in api_forecasts
    }) == len(api_forecasts)
    assert all(Forecast.model_validate(row).predicted_quantity >= 0 for row in api_forecasts)
