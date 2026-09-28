from __future__ import annotations

import csv
import hashlib
import json
import zipfile
from decimal import Decimal

import pytest

from data.generator.main import DatasetGenerationConfig, build_dataset
from ml.features.demand_forecast import build_demand_feature_rows
from ml.experiments.identity import (
    INPUT_MANIFEST_FILENAME,
    RUN_MANIFEST_FILENAME,
    SOURCE_ARCHIVE_FILENAME,
    file_sha256,
)
from ml.models.random_forest_forecast import (
    FEATURE_IMPORTANCE_FILENAME,
    METRICS_FILENAME,
    MODEL_ARTIFACT_FILENAME,
    MODEL_CARD_FILENAME,
    MODEL_METADATA_FILENAME,
    PANEL_FILENAME,
    PREDICTIONS_FILENAME,
    RandomForestForecastConfig,
    baseline_prediction_for_row,
    build_metrics_report,
    build_model_metadata,
    build_random_forest_pipeline,
    build_supervised_examples,
    build_training_features,
    calculate_prediction_metrics,
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
    assert "day_of_week" in first_features
    assert "product_id" in first_features
    assert not {"unit_price", "promotion_active", "stockout_flag", "inventory_on_hand"} & first_features.keys()
    assert examples[0].target >= 0


def test_future_outcomes_and_rows_cannot_change_a_frozen_one_step_prediction() -> None:
    dataset = DatasetGenerationConfig(
        profile="small", days=8, products=8, stores=2, warehouses=2, seed=42,
    )
    rows = build_demand_feature_rows(build_dataset(dataset), dataset)
    examples = build_supervised_examples(rows, holdout_days=2, window_days=7)
    train = [example for example in examples if example.split == "train"]
    test = next(example for example in examples if example.split == "test")
    model = build_random_forest_pipeline(n_estimators=8, random_state=42)
    model.fit([example.features for example in train], [example.target for example in train])

    row = test.row
    history = [
        candidate for candidate in rows
        if all(candidate[field] == row[field] for field in ("product_id", "store_id", "channel"))
        and candidate["date"] < row["date"]
    ]
    before = build_training_features(row, history, window_days=7)
    future = {**row, "date": "2099-01-01", "units_sold": 999999}
    changed = {
        **row,
        "units_sold": 999999,
        "unit_price": "0.01",
        "promotion_active": True,
        "stockout_flag": True,
        "inventory_on_hand": 999999,
        "latent_units_demand": 999999,
    }
    after = build_training_features(changed, [*history, future], window_days=7)

    assert before == after
    assert model.predict([before])[0] == model.predict([after])[0]


@pytest.mark.parametrize("versioned", [False, True])
def test_late_historical_sale_is_not_available_to_model_or_baseline(versioned) -> None:
    dataset = DatasetGenerationConfig(
        profile="small", days=8, products=8, stores=2, warehouses=2, seed=42,
    )
    rows = build_demand_feature_rows(build_dataset(dataset), dataset)
    series_by_key: dict[tuple[str, str, str], list[dict[str, object]]] = {}
    for row in rows:
        key = (str(row["product_id"]), str(row["store_id"]), str(row["channel"]))
        series_by_key.setdefault(key, []).append(row)
    series = sorted(
        next(series for series in series_by_key.values() if len(series) >= 3),
        key=lambda row: str(row["date"]),
    )
    target = series[-1]
    history = series[:-1]
    late = {**history[-1], "observation_available_at": "2099-01-01T12:00:00+00:00"}
    if versioned:
        versions = json.loads(str(late["observation_history"]))
        assert len(versions) == 1
        versions[0]["available_at"] = str(late["observation_available_at"])
        late["observation_history"] = json.dumps(versions)
    else:
        late.pop("observation_history")

    model_features = build_training_features(target, [*history[:-1], late], window_days=7)
    known_features = build_training_features(target, history[:-1], window_days=7)

    assert model_features == known_features
    assert baseline_prediction_for_row(target, [*history[:-1], late], window_days=7) == (
        baseline_prediction_for_row(target, history[:-1], window_days=7)
    )


def test_random_forest_report_rejects_zero_denominator() -> None:
    report = build_metrics_report(
        RandomForestForecastConfig(),
        [{"date": "2026-01-01", "dataset_id": "test"}],
        {"folds": [{"split": "test", "training_examples": 1, "coverage": "1.0000"}]},
        [{
            "split": "test", "actual_units": 0, "predicted_units": 100,
            "baseline_predicted_units": 200,
        }],
        [],
    )
    assert report["model_status"] == "rejected"
    assert report["primary_metric_improvement_percent"] is None
    assert report["trained_model_metrics"] == calculate_prediction_metrics(
        [{"actual_units": 0, "predicted_units": 100}], prediction_field="predicted_units",
    )
    assert report["trained_model_metrics"]["wape"] is None


def test_random_forest_training_job_writes_artifacts_and_baseline_comparison(tmp_path) -> None:
    config = RandomForestForecastConfig(
        dataset=DatasetGenerationConfig(
            profile="small",
            days=42,
            products=8,
            stores=2,
            warehouses=2,
            seed=42,
        ),
        window_days=7,
        horizon_days=7,
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
    assert (tmp_path / PANEL_FILENAME).exists()
    assert predictions
    assert feature_importance
    assert metrics["model_name"] == "retailops-demand-random-forest"
    assert metrics["baseline_metrics"]["evaluated_rows"] == metrics["test_row_count"]
    assert metrics["trained_model_metrics"]["evaluated_rows"] == metrics["test_row_count"]
    assert metadata["status"] in {"candidate", "rejected"}
    assert metadata["status"] == metrics_report["model_status"]
    assert metadata["admission_decision"] == metrics["admission_decision"]
    assert {check["check_id"] for check in metrics["admission_decision"]["checks"]} == {
        "protocol", "coverage", "final_quality", "stability", "segments", "reproduction",
    }
    assert next(
        check for check in metrics["admission_decision"]["checks"]
        if check["check_id"] == "reproduction"
    )["status"] == "passed"
    assert Decimal(str(metrics["trained_model_metrics"]["wape"])) >= 0
    assert "Baseline Comparison" in model_card
    inputs = json.loads((tmp_path / INPUT_MANIFEST_FILENAME).read_text(encoding="utf-8"))
    manifest = json.loads((tmp_path / RUN_MANIFEST_FILENAME).read_text(encoding="utf-8"))
    assert metrics["experiment_id"] == manifest["experiment_id"]
    assert metadata["model_id"] == manifest["model_id"]
    assert metrics["evaluation_scope"] == "synthetic_fixed_origin_horizon_v1"
    assert [fold["split"] for fold in metrics["temporal_protocol"]["folds"]] == [
        "validation_1", "validation_2", "validation_3", "test",
    ]
    assert {row["horizon_day"] for row in predictions} == {str(day) for day in range(1, 8)}
    assert inputs["dataset"]["effective_config"]["days"] == 42
    assert inputs["model"]["n_estimators"] == 12
    assert inputs["features"]["row_count"] == metrics["feature_row_count"]
    assert inputs["features"]["panel_row_count"] == metrics["temporal_protocol"]["panel_rows"]
    assert manifest["panel_logical_sha256"] == inputs["features"]["panel_logical_sha256"]
    assert inputs["source"]["git_commit"]
    assert "ml/policy/forecast_admission_v1.json" in inputs["source"]["source_files_sha256"]
    assert inputs["environment"]["dependencies"]["scikit-learn"]
    assert manifest["model_id"] == "sha256:" + file_sha256(tmp_path / MODEL_ARTIFACT_FILENAME)
    for name, checksum in manifest["artifact_sha256"].items():
        assert checksum == file_sha256(tmp_path / name)
    with zipfile.ZipFile(tmp_path / SOURCE_ARCHIVE_FILENAME) as archive:
        assert "ml/models/random_forest_forecast.py" in archive.namelist()
        for name, checksum in inputs["source"]["source_files_sha256"].items():
            assert hashlib.sha256(archive.read(name)).hexdigest() == checksum

    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        train_random_forest_forecast_model(config)

    tampered = {**metrics_report, "model_status": "candidate" if metadata["status"] != "candidate" else "rejected"}
    with pytest.raises(ValueError, match="admission decision"):
        build_model_metadata(tampered)


def test_random_forest_run_identity_is_unique_and_experiment_identity_tracks_inputs(tmp_path) -> None:
    dataset = DatasetGenerationConfig(
        profile="small", days=42, products=8, stores=2, warehouses=2, seed=42,
    )
    config = RandomForestForecastConfig(
        dataset=dataset, window_days=7, horizon_days=7, n_estimators=12,
        output_root=tmp_path,
    )
    first = train_random_forest_forecast_model(config)
    repeated = train_random_forest_forecast_model(config)
    changed = train_random_forest_forecast_model(
        RandomForestForecastConfig(
            dataset=dataset, window_days=7, horizon_days=7, n_estimators=20,
            output_root=tmp_path,
        ),
    )

    assert first["experiment_id"] == repeated["experiment_id"]
    assert first["experiment_id"] != changed["experiment_id"]
    assert len({first["run_id"], repeated["run_id"], changed["run_id"]}) == 3
    assert len({first["output_dir"], repeated["output_dir"], changed["output_dir"]}) == 3
    first_manifest = json.loads(
        (tmp_path / first["run_id"] / RUN_MANIFEST_FILENAME).read_text(encoding="utf-8"),
    )
    repeated_manifest = json.loads(
        (tmp_path / repeated["run_id"] / RUN_MANIFEST_FILENAME).read_text(encoding="utf-8"),
    )
    assert first_manifest["predictions_logical_sha256"] == repeated_manifest[
        "predictions_logical_sha256"
    ]
