from __future__ import annotations

import csv
import json

import pytest

from data.generator.main import DatasetGenerationConfig, build_dataset
from ml.evaluation.baseline_report import (
    BACKTEST_PREDICTIONS_FILENAME,
    EVALUATION_REPORT_FILENAME,
    EVALUATION_SUMMARY_FILENAME,
    EvaluationConfig,
    build_backtest_predictions,
    build_evaluation_report,
    calculate_metrics,
    generate_baseline_evaluation_report,
)
from ml.features.demand_forecast import build_demand_feature_rows
from ml.models.baseline_forecast import MODEL_NAME, MODEL_VERSION


def test_backtest_predictions_use_prior_rows_only() -> None:
    feature_rows = [
        {
            "dataset_id": "dataset-1",
            "date": "2026-04-01",
            "product_id": "product-1",
            "store_id": "store-1",
            "channel": "store",
            "units_sold": 4,
            "generated_at": "2026-04-04T00:00:00Z",
        },
        {
            "dataset_id": "dataset-1",
            "date": "2026-04-02",
            "product_id": "product-1",
            "store_id": "store-1",
            "channel": "store",
            "units_sold": 6,
            "generated_at": "2026-04-04T00:00:00Z",
        },
        {
            "dataset_id": "dataset-1",
            "date": "2026-04-03",
            "product_id": "product-1",
            "store_id": "store-1",
            "channel": "store",
            "units_sold": 10,
            "generated_at": "2026-04-04T00:00:00Z",
        },
    ]

    predictions, skipped_rows = build_backtest_predictions(
        feature_rows,
        window_days=2,
        holdout_days=1,
    )

    assert skipped_rows == 0
    assert len(predictions) == 1
    assert predictions[0]["forecast_date"] == "2026-04-03"
    assert predictions[0]["predicted_units"] == 5
    assert predictions[0]["actual_units"] == 10
    assert predictions[0]["training_rows"] == 2


@pytest.mark.parametrize("window_days,holdout_days", [(0, 1), (1, 0)])
def test_backtest_rejects_non_positive_options(
    window_days: int,
    holdout_days: int,
) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        build_backtest_predictions(
            [],
            window_days=window_days,
            holdout_days=holdout_days,
        )


def test_evaluation_metrics_include_error_and_bias() -> None:
    metrics = calculate_metrics(
        [
            {
                "predicted_units": 8,
                "actual_units": 10,
                "absolute_error": "2.00",
                "squared_error": "4.00",
                "absolute_percentage_error": "20.0000",
            },
            {
                "predicted_units": 12,
                "actual_units": 10,
                "absolute_error": "2.00",
                "squared_error": "4.00",
                "absolute_percentage_error": "20.0000",
            },
        ],
    )

    assert metrics == {
        "evaluated_rows": 2,
        "mae": "2.0000",
        "rmse": "2.0000",
        "mape": "20.0000",
        "bias": "0.0000",
        "wape": "20.0000",
    }


def test_evaluation_report_describes_model_dataset_and_metrics() -> None:
    config = EvaluationConfig(
        dataset=DatasetGenerationConfig(
            profile="small",
            days=5,
            products=6,
            stores=2,
            warehouses=2,
            seed=42,
        ),
        window_days=7,
        holdout_days=2,
    )
    feature_rows = build_demand_feature_rows(build_dataset(config.dataset), config.dataset)
    predictions, skipped_rows = build_backtest_predictions(
        feature_rows,
        window_days=config.window_days,
        holdout_days=config.holdout_days,
    )
    report = build_evaluation_report(config, feature_rows, predictions, skipped_rows)

    assert report["model_name"] == MODEL_NAME
    assert report["model_version"] == MODEL_VERSION
    assert report["feature_dataset_id"] == feature_rows[0]["dataset_id"]
    assert report["holdout_days"] == 2
    assert report["metrics"]["evaluated_rows"] == len(predictions)
    assert report["evaluation_date_start"] <= report["evaluation_date_end"]


def test_evaluation_job_writes_report_summary_and_predictions(tmp_path) -> None:
    config = EvaluationConfig(
        dataset=DatasetGenerationConfig(
            profile="small",
            days=5,
            products=6,
            stores=2,
            warehouses=2,
            seed=123,
        ),
        window_days=7,
        holdout_days=2,
        output_dir=tmp_path,
    )

    report = generate_baseline_evaluation_report(config)
    predictions = list(
        csv.DictReader((tmp_path / BACKTEST_PREDICTIONS_FILENAME).open(encoding="utf-8")),
    )
    written_report = json.loads(
        (tmp_path / EVALUATION_REPORT_FILENAME).read_text(encoding="utf-8"),
    )
    summary = (tmp_path / EVALUATION_SUMMARY_FILENAME).read_text(encoding="utf-8")

    assert predictions
    assert written_report["model_version"] == MODEL_VERSION
    assert written_report["metrics"] == report["metrics"]
    assert "RetailOps Baseline Forecast Evaluation" in summary
    assert str(report["metrics"]["evaluated_rows"]) in summary
