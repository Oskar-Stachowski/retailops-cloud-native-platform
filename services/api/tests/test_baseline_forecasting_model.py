from __future__ import annotations

import csv
import json

import pytest

from data.generator.main import DatasetGenerationConfig, build_dataset
from ml.features.demand_forecast import build_demand_feature_rows
from ml.models.baseline_forecast import (
    DEFAULT_HORIZON_DAYS,
    FORECAST_FILENAME,
    MODEL_MANIFEST_FILENAME,
    MODEL_NAME,
    MODEL_VERSION,
    BaselineForecastConfig,
    build_baseline_forecasts,
    build_model_manifest,
    train_baseline_forecast_model,
)


def test_baseline_forecast_builds_expected_horizon_per_series() -> None:
    config = DatasetGenerationConfig(
        profile="small",
        days=5,
        products=6,
        stores=2,
        warehouses=2,
        seed=42,
    )
    feature_rows = build_demand_feature_rows(build_dataset(config), config)
    series_count = {
        (row["product_id"], row["store_id"], row["channel"]) for row in feature_rows
    }
    forecasts = build_baseline_forecasts(feature_rows, horizon_days=3, window_days=7)

    assert len(forecasts) == len(series_count) * 3
    assert {row["model_name"] for row in forecasts} == {MODEL_NAME}
    assert {row["model_version"] for row in forecasts} == {MODEL_VERSION}
    assert all(int(row["predicted_units"]) >= 0 for row in forecasts)
    assert all(int(row["training_rows"]) >= 1 for row in forecasts)


def test_baseline_forecast_uses_recent_window_average() -> None:
    feature_rows = [
        {
            "dataset_id": "dataset-1",
            "date": "2026-04-01",
            "product_id": "product-1",
            "store_id": "store-1",
            "channel": "store",
            "units_sold": 2,
            "generated_at": "2026-04-03T00:00:00Z",
        },
        {
            "dataset_id": "dataset-1",
            "date": "2026-04-02",
            "product_id": "product-1",
            "store_id": "store-1",
            "channel": "store",
            "units_sold": 8,
            "generated_at": "2026-04-03T00:00:00Z",
        },
    ]

    forecasts = build_baseline_forecasts(feature_rows, horizon_days=2, window_days=1)

    assert [row["forecast_date"] for row in forecasts] == ["2026-04-03", "2026-04-04"]
    assert {row["predicted_units"] for row in forecasts} == {8}
    assert {row["training_rows"] for row in forecasts} == {1}


@pytest.mark.parametrize("window_days,horizon_days", [(0, 1), (1, 0)])
def test_baseline_forecast_rejects_non_positive_options(
    window_days: int,
    horizon_days: int,
) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        build_baseline_forecasts(
            [
                {
                    "dataset_id": "dataset-1",
                    "date": "2026-04-01",
                    "product_id": "product-1",
                    "store_id": "store-1",
                    "channel": "store",
                    "units_sold": 2,
                    "generated_at": "2026-04-01T00:00:00Z",
                },
            ],
            window_days=window_days,
            horizon_days=horizon_days,
        )


def test_baseline_model_manifest_describes_training_and_forecast_range() -> None:
    config = BaselineForecastConfig(
        dataset=DatasetGenerationConfig(
            profile="small",
            days=5,
            products=6,
            stores=2,
            warehouses=2,
            seed=123,
        ),
        window_days=7,
        horizon_days=DEFAULT_HORIZON_DAYS,
    )
    feature_rows = build_demand_feature_rows(build_dataset(config.dataset), config.dataset)
    forecast_rows = build_baseline_forecasts(
        feature_rows,
        window_days=config.window_days,
        horizon_days=config.horizon_days,
    )
    manifest = build_model_manifest(config, feature_rows, forecast_rows)

    assert manifest["model_name"] == MODEL_NAME
    assert manifest["model_version"] == MODEL_VERSION
    assert manifest["feature_dataset_id"] == feature_rows[0]["dataset_id"]
    assert manifest["forecast_row_count"] == len(forecast_rows)
    assert manifest["window_days"] == 7
    assert manifest["horizon_days"] == DEFAULT_HORIZON_DAYS
    assert manifest["forecast_date_start"] <= manifest["forecast_date_end"]


def test_baseline_model_job_writes_forecasts_and_manifest(tmp_path) -> None:
    config = BaselineForecastConfig(
        dataset=DatasetGenerationConfig(
            profile="small",
            days=3,
            products=5,
            stores=2,
            warehouses=2,
            seed=42,
        ),
        window_days=7,
        horizon_days=2,
        output_dir=tmp_path,
    )

    manifest = train_baseline_forecast_model(config)
    forecasts = list(csv.DictReader((tmp_path / FORECAST_FILENAME).open(encoding="utf-8")))
    written_manifest = json.loads(
        (tmp_path / MODEL_MANIFEST_FILENAME).read_text(encoding="utf-8"),
    )

    assert forecasts
    assert len(forecasts) == manifest["forecast_row_count"]
    assert written_manifest["model_version"] == MODEL_VERSION
    assert forecasts[0]["dataset_id"] == manifest["feature_dataset_id"]
