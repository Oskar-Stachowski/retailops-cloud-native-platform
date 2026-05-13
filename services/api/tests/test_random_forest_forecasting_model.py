from __future__ import annotations

import csv
import json
from decimal import Decimal

from data.generator.main import DatasetGenerationConfig, build_dataset
from ml.features.demand_forecast import build_demand_feature_rows
from ml.models.random_forest_forecast import (
    FEATURE_IMPORTANCE_FILENAME,
    METRICS_FILENAME,
    MODEL_ARTIFACT_FILENAME,
    MODEL_CARD_FILENAME,
    MODEL_METADATA_FILENAME,
    PREDICTIONS_FILENAME,
    RandomForestForecastConfig,
    build_supervised_examples,
    model_status_from_metrics,
    train_random_forest_forecast_model,
)


def test_random_forest_supervised_features_include_lag_and_business_signals() -> None:
    dataset = DatasetGenerationConfig(
        profile="small",
        days=5,
        products=6,
        stores=2,
        warehouses=2,
        seed=42,
    )
    feature_rows = build_demand_feature_rows(build_dataset(dataset), dataset)
    examples = build_supervised_examples(feature_rows, holdout_days=2, window_days=7)

    assert examples
    assert {example.split for example in examples} == {"train", "test"}
    first_features = examples[0].features
    assert "lag_1_units" in first_features
    assert "rolling_mean_units" in first_features
    assert "unit_price" in first_features
    assert "promotion_active" in first_features
    assert "product_id" in first_features
    assert examples[0].target >= 0


def test_random_forest_model_status_requires_primary_metric_improvement() -> None:
    assert (
        model_status_from_metrics(
            {"wape": "8.0000"},
            {"wape": "10.0000"},
        )
        == "candidate"
    )
    assert (
        model_status_from_metrics(
            {"wape": "12.0000"},
            {"wape": "10.0000"},
        )
        == "rejected"
    )


def test_random_forest_training_job_writes_artifacts_and_baseline_comparison(tmp_path) -> None:
    config = RandomForestForecastConfig(
        dataset=DatasetGenerationConfig(
            profile="small",
            days=8,
            products=8,
            stores=2,
            warehouses=2,
            seed=42,
        ),
        window_days=7,
        holdout_days=2,
        n_estimators=12,
        random_state=42,
        output_dir=tmp_path,
    )

    metrics_report = train_random_forest_forecast_model(config)
    predictions = list(csv.DictReader((tmp_path / PREDICTIONS_FILENAME).open(encoding="utf-8")))
    metrics = json.loads((tmp_path / METRICS_FILENAME).read_text(encoding="utf-8"))
    metadata = json.loads((tmp_path / MODEL_METADATA_FILENAME).read_text(encoding="utf-8"))
    feature_importance = list(
        csv.DictReader((tmp_path / FEATURE_IMPORTANCE_FILENAME).open(encoding="utf-8")),
    )
    model_card = (tmp_path / MODEL_CARD_FILENAME).read_text(encoding="utf-8")

    assert (tmp_path / MODEL_ARTIFACT_FILENAME).exists()
    assert predictions
    assert feature_importance
    assert metrics["model_name"] == "retailops-demand-random-forest"
    assert metrics["baseline_metrics"]["evaluated_rows"] == metrics["test_row_count"]
    assert metrics["trained_model_metrics"]["evaluated_rows"] == metrics["test_row_count"]
    assert metadata["status"] in {"candidate", "rejected"}
    assert metadata["status"] == metrics_report["model_status"]
    assert Decimal(str(metrics["trained_model_metrics"]["wape"])) >= 0
    assert "Baseline Comparison" in model_card
