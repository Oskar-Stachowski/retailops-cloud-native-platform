from __future__ import annotations

import argparse
import csv
import json
import shlex
import sys
import uuid
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import joblib
from sklearn.ensemble import RandomForestRegressor
from sklearn.feature_extraction import DictVectorizer
from sklearn.pipeline import Pipeline

from data.generator.main import DatasetGenerationConfig, build_dataset
from data.generator.manifest import GENERATOR_VERSION, build_dataset_manifest
from data.generator.profile_engine import profile_defaults
from ml.experiments.identity import (
    INPUT_MANIFEST_FILENAME,
    RUN_MANIFEST_FILENAME,
    SOURCE_ARCHIVE_FILENAME,
    artifact_checksums,
    canonical_sha256,
    environment_identity,
    file_sha256,
    json_file,
    logical_rows_sha256,
    source_identity,
    write_source_archive,
)
from ml.features.demand_forecast import (
    GRAIN,
    TARGET,
    build_demand_feature_rows,
    observation_known_at_origin,
)
from ml.features.demand_forecast import SCHEMA_VERSION as FEATURE_SCHEMA_VERSION
from ml.models.baseline_forecast import _prediction_value

MODEL_NAME = "retailops-demand-random-forest"
MODEL_VERSION = "random-forest-v2"
MODEL_TYPE = "sklearn_random_forest_regressor"
MODEL_ARTIFACT_FILENAME = "random_forest_model.joblib"
METRICS_FILENAME = "metrics.json"
PREDICTIONS_FILENAME = "predictions.csv"
FEATURE_IMPORTANCE_FILENAME = "feature_importance.csv"
MODEL_METADATA_FILENAME = "model_metadata.json"
MODEL_CARD_FILENAME = "model_card.md"
EVALUATION_SCOPE = "legacy_rolling_holdout_exploratory_only"
DEFAULT_HOLDOUT_DAYS = 7
DEFAULT_WINDOW_DAYS = 28
DEFAULT_HORIZON_DAYS = 7
DEFAULT_N_ESTIMATORS = 80
DEFAULT_RANDOM_STATE = 42
PRIMARY_METRIC = "wape"
SERIES_FIELDS = ["product_id", "store_id", "channel"]
PREDICTION_COLUMNS = [
    "model_name",
    "model_version",
    "dataset_id",
    "forecast_date",
    "product_id",
    "store_id",
    "channel",
    "predicted_units",
    "baseline_predicted_units",
    "actual_units",
    "absolute_error",
    "baseline_absolute_error",
    "squared_error",
    "absolute_percentage_error",
    "baseline_absolute_percentage_error",
]


@dataclass(frozen=True)
class RandomForestForecastConfig:
    dataset: DatasetGenerationConfig = field(
        default_factory=lambda: DatasetGenerationConfig(profile="demo"),
    )
    window_days: int = DEFAULT_WINDOW_DAYS
    horizon_days: int = DEFAULT_HORIZON_DAYS
    holdout_days: int = DEFAULT_HOLDOUT_DAYS
    n_estimators: int = DEFAULT_N_ESTIMATORS
    random_state: int = DEFAULT_RANDOM_STATE
    output_dir: Path | None = None
    output_root: Path | None = None


@dataclass(frozen=True)
class SupervisedExample:
    row: dict[str, object]
    features: dict[str, object]
    target: int
    split: str


def _row_date(row: dict[str, object]) -> date:
    return date.fromisoformat(str(row["date"]))


def _series_key(row: dict[str, object]) -> tuple[str, str, str]:
    return tuple(str(row[field]) for field in SERIES_FIELDS)


def _decimal(value: object) -> Decimal:
    return Decimal(str(value))


def _metric(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))


def _quantity(value: float | Decimal) -> int:
    return max(0, int(Decimal(str(value)).quantize(Decimal(1), rounding=ROUND_HALF_UP)))


def _safe_percentage_error(error: Decimal, actual: Decimal) -> Decimal:
    return error / actual * Decimal(100) if actual > 0 else Decimal(0)


def _mean(values: list[Decimal]) -> Decimal:
    return sum(values) / Decimal(len(values)) if values else Decimal(0)


def build_training_features(
    row: dict[str, object],
    previous_rows: list[dict[str, object]],
    *,
    window_days: int,
) -> dict[str, object]:
    forecast_date = _row_date(row)
    history = sorted(
        (
            previous_row
            for previous_row in previous_rows
            if observation_known_at_origin(previous_row, forecast_date)
        ),
        key=_row_date,
    )
    recent_rows = history[-window_days:] if window_days > 0 else history
    recent_targets = [_decimal(previous_row[TARGET]) for previous_row in recent_rows]
    lag_1_units = _decimal(history[-1][TARGET]) if history else Decimal(0)
    lag_7_units = _decimal(history[-7][TARGET]) if len(history) >= 7 else lag_1_units

    return {
        "day_of_week": int(row["day_of_week"]),
        "is_weekend": int(bool(row["is_weekend"])),
        "week_of_year": int(row["week_of_year"]),
        "month": int(row["month"]),
        "lag_1_units": float(lag_1_units),
        "lag_7_units": float(lag_7_units),
        "rolling_mean_units": float(_mean(recent_targets)),
        "rolling_min_units": float(min(recent_targets) if recent_targets else Decimal(0)),
        "rolling_max_units": float(max(recent_targets) if recent_targets else Decimal(0)),
        "training_observation_count": len(history),
        "product_id": str(row["product_id"]),
        "store_id": str(row["store_id"]),
        "channel": str(row["channel"]),
        "category": str(row["category"]),
        "brand": str(row["brand"]),
    }


def build_supervised_examples(
    feature_rows: list[dict[str, object]],
    *,
    holdout_days: int,
    window_days: int,
) -> list[SupervisedExample]:
    if holdout_days <= 0:
        msg = "holdout_days must be a positive integer."
        raise ValueError(msg)
    if window_days <= 0:
        msg = "window_days must be a positive integer."
        raise ValueError(msg)
    if not feature_rows:
        return []

    max_feature_date = max(_row_date(row) for row in feature_rows)
    holdout_start = max_feature_date - timedelta(days=holdout_days - 1)
    rows_by_series: dict[tuple[str, str, str], list[dict[str, object]]] = defaultdict(list)
    for row in feature_rows:
        rows_by_series[_series_key(row)].append(row)

    examples: list[SupervisedExample] = []
    for key in sorted(rows_by_series):
        series_rows = sorted(rows_by_series[key], key=_row_date)
        for index, row in enumerate(series_rows):
            previous_rows = series_rows[:index]
            if not previous_rows:
                continue
            split = "test" if _row_date(row) >= holdout_start else "train"
            examples.append(
                SupervisedExample(
                    row=row,
                    features=build_training_features(row, previous_rows, window_days=window_days),
                    target=int(row[TARGET]),
                    split=split,
                ),
            )

    return examples


def build_random_forest_pipeline(
    *,
    n_estimators: int,
    random_state: int,
) -> Pipeline:
    if n_estimators <= 0:
        msg = "n_estimators must be a positive integer."
        raise ValueError(msg)
    return Pipeline(
        steps=[
            ("features", DictVectorizer(sparse=False)),
            (
                "model",
                RandomForestRegressor(
                    n_estimators=n_estimators,
                    random_state=random_state,
                    min_samples_leaf=2,
                    n_jobs=1,
                ),
            ),
        ],
    )


def baseline_prediction_for_row(
    row: dict[str, object],
    series_rows: list[dict[str, object]],
    *,
    window_days: int,
) -> int:
    forecast_date = _row_date(row)
    train_start = forecast_date - timedelta(days=window_days)
    training_rows = [
        candidate
        for candidate in series_rows
        if train_start <= _row_date(candidate)
        and observation_known_at_origin(candidate, forecast_date)
    ]
    if not training_rows:
        training_rows = [
            candidate
            for candidate in series_rows
            if observation_known_at_origin(candidate, forecast_date)
        ]
    return max(0, _prediction_value(training_rows)) if training_rows else 0


def calculate_prediction_metrics(
    predictions: list[dict[str, object]],
    *,
    prediction_field: str,
) -> dict[str, object]:
    if not predictions:
        return {
            "evaluated_rows": 0,
            "mae": "",
            "rmse": "",
            "mape": "",
            "bias": "",
            "wape": "",
        }

    row_count = Decimal(len(predictions))
    absolute_errors: list[Decimal] = []
    squared_errors: list[Decimal] = []
    percentage_errors: list[Decimal] = []
    actual_values: list[Decimal] = []
    predicted_values: list[Decimal] = []

    for row in predictions:
        actual = _decimal(row["actual_units"])
        predicted = _decimal(row[prediction_field])
        error = predicted - actual
        absolute_error = abs(error)
        actual_values.append(actual)
        predicted_values.append(predicted)
        absolute_errors.append(absolute_error)
        squared_errors.append(error * error)
        percentage_errors.append(_safe_percentage_error(absolute_error, actual))

    mae = sum(absolute_errors) / row_count
    rmse = (sum(squared_errors) / row_count).sqrt()
    mape = sum(percentage_errors) / row_count
    bias = (sum(predicted_values) - sum(actual_values)) / row_count
    actual_total = sum(actual_values)
    wape = sum(absolute_errors) / actual_total * Decimal(100) if actual_total > 0 else Decimal(0)

    return {
        "evaluated_rows": len(predictions),
        "mae": _metric(mae),
        "rmse": _metric(rmse),
        "mape": _metric(mape),
        "bias": _metric(bias),
        "wape": _metric(wape),
    }


def model_status_from_metrics(
    trained_metrics: dict[str, object],
    baseline_metrics: dict[str, object],
    *,
    primary_metric: str = PRIMARY_METRIC,
) -> str:
    trained_value = Decimal(str(trained_metrics[primary_metric]))
    baseline_value = Decimal(str(baseline_metrics[primary_metric]))
    return "candidate" if trained_value < baseline_value else "rejected"


def build_predictions(
    model: Pipeline,
    examples: list[SupervisedExample],
    feature_rows: list[dict[str, object]],
    *,
    window_days: int,
) -> list[dict[str, object]]:
    test_examples = [example for example in examples if example.split == "test"]
    if not test_examples:
        return []

    dataset_id = str(feature_rows[0]["dataset_id"]) if feature_rows else ""
    rows_by_series: dict[tuple[str, str, str], list[dict[str, object]]] = defaultdict(list)
    for row in feature_rows:
        rows_by_series[_series_key(row)].append(row)
    for key, rows in rows_by_series.items():
        rows_by_series[key] = sorted(rows, key=_row_date)

    predicted_values = model.predict([example.features for example in test_examples])
    prediction_rows: list[dict[str, object]] = []

    for example, predicted_value in zip(test_examples, predicted_values, strict=True):
        row = example.row
        predicted_units = _quantity(float(predicted_value))
        baseline_predicted_units = baseline_prediction_for_row(
            row,
            rows_by_series[_series_key(row)],
            window_days=window_days,
        )
        actual_units = int(row[TARGET])
        error = Decimal(predicted_units) - Decimal(actual_units)
        baseline_error = Decimal(baseline_predicted_units) - Decimal(actual_units)
        absolute_error = abs(error)
        baseline_absolute_error = abs(baseline_error)

        prediction_rows.append(
            {
                "model_name": MODEL_NAME,
                "model_version": MODEL_VERSION,
                "dataset_id": dataset_id,
                "forecast_date": str(row["date"]),
                "product_id": row["product_id"],
                "store_id": row["store_id"],
                "channel": row["channel"],
                "predicted_units": predicted_units,
                "baseline_predicted_units": baseline_predicted_units,
                "actual_units": actual_units,
                "absolute_error": _metric(absolute_error),
                "baseline_absolute_error": _metric(baseline_absolute_error),
                "squared_error": _metric(error * error),
                "absolute_percentage_error": _metric(
                    _safe_percentage_error(absolute_error, Decimal(actual_units)),
                ),
                "baseline_absolute_percentage_error": _metric(
                    _safe_percentage_error(baseline_absolute_error, Decimal(actual_units)),
                ),
            },
        )

    return prediction_rows


def build_feature_importance_rows(model: Pipeline) -> list[dict[str, object]]:
    vectorizer = model.named_steps["features"]
    regressor = model.named_steps["model"]
    feature_names = vectorizer.get_feature_names_out()
    importances = regressor.feature_importances_
    rows = [
        {
            "feature": str(feature_name),
            "importance": _metric(Decimal(str(importance))),
        }
        for feature_name, importance in zip(feature_names, importances, strict=True)
    ]
    return sorted(rows, key=lambda row: Decimal(str(row["importance"])), reverse=True)


def default_trained_model_output_root(profile: str) -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "ci-cd" / "reports" / "ml" / "experiments" / profile


def reproduction_command(config: RandomForestForecastConfig) -> str:
    dataset = config.dataset
    output_root = config.output_root or (
        config.output_dir.parent
        if config.output_dir is not None
        else default_trained_model_output_root(dataset.profile)
    )
    args = [
        sys.executable,
        "-m",
        "ml.models.random_forest_forecast",
        "--profile",
        dataset.profile,
        "--seed",
        str(dataset.seed),
        "--window-days",
        str(config.window_days),
        "--horizon-days",
        str(config.horizon_days),
        "--holdout-days",
        str(config.holdout_days),
        "--n-estimators",
        str(config.n_estimators),
        "--random-state",
        str(config.random_state),
    ]
    for name in ("days", "products", "stores", "warehouses"):
        value = getattr(dataset, name)
        if value is not None:
            args.extend((f"--{name}", str(value)))
    args.extend(("--output-root", str(output_root)))
    return shlex.join(args)


def build_experiment_inputs(
    config: RandomForestForecastConfig,
    tables: dict[str, list[dict[str, str]]],
    feature_rows: list[dict[str, object]],
    source: dict[str, object],
    environment: dict[str, object],
) -> dict[str, object]:
    dataset_manifest = build_dataset_manifest(config.dataset, tables)  # type: ignore[arg-type]
    defaults = (
        profile_defaults(config.dataset.profile) if config.dataset.profile != "demo" else None
    )
    effective_config: dict[str, object] = (
        {
            "days": config.dataset.days or defaults.days,
            "products": config.dataset.products or defaults.products,
            "stores": config.dataset.stores or defaults.stores,
            "warehouses": config.dataset.warehouses or defaults.warehouses,
            "seed": config.dataset.seed,
        }
        if defaults is not None
        else {"mode": "fixed_demo_fixture", "seed_effective": False}
    )
    dataset_hashes = {name: logical_rows_sha256(rows) for name, rows in sorted(tables.items())}
    feature_dates = [str(row["date"]) for row in feature_rows]
    pipeline = build_random_forest_pipeline(
        n_estimators=config.n_estimators,
        random_state=config.random_state,
    )
    return {
        "source": source,
        "environment": environment,
        "dataset": {
            "requested_config": asdict(config.dataset),
            "effective_config": effective_config,
            "schema_version": dataset_manifest["schema_version"],
            "generator_version": dataset_manifest["generator_version"],
            "date_start": dataset_manifest["date_start"],
            "date_end": dataset_manifest["date_end"],
            "row_counts": dataset_manifest["row_counts"],
            "table_logical_sha256": dataset_hashes,
            "logical_sha256": canonical_sha256(dataset_hashes),
        },
        "features": {
            "dataset_id": str(feature_rows[0]["dataset_id"]) if feature_rows else "",
            "schema_version": FEATURE_SCHEMA_VERSION,
            "grain": GRAIN,
            "target": TARGET,
            "date_start": min(feature_dates) if feature_dates else "",
            "date_end": max(feature_dates) if feature_dates else "",
            "row_count": len(feature_rows),
            "logical_sha256": logical_rows_sha256(feature_rows),
        },
        "model": {
            "model_name": MODEL_NAME,
            "model_version": MODEL_VERSION,
            "model_type": MODEL_TYPE,
            "n_estimators": config.n_estimators,
            "random_state": config.random_state,
            "min_samples_leaf": 2,
            "n_jobs": 1,
            "estimator_parameters": pipeline.named_steps["model"].get_params(),
            "vectorizer_parameters": pipeline.named_steps["features"].get_params(),
            "window_days": config.window_days,
            "horizon_days": config.horizon_days,
            "holdout_days": config.holdout_days,
        },
        "evaluation_scope": EVALUATION_SCOPE,
        "reproduction_command": reproduction_command(config),
    }


def build_metrics_report(
    config: RandomForestForecastConfig,
    feature_rows: list[dict[str, object]],
    examples: list[SupervisedExample],
    predictions: list[dict[str, object]],
    feature_importance_rows: list[dict[str, object]],
) -> dict[str, object]:
    trained_metrics = calculate_prediction_metrics(predictions, prediction_field="predicted_units")
    baseline_metrics = calculate_prediction_metrics(
        predictions,
        prediction_field="baseline_predicted_units",
    )
    model_status = model_status_from_metrics(trained_metrics, baseline_metrics)
    baseline_primary = Decimal(str(baseline_metrics[PRIMARY_METRIC]))
    trained_primary = Decimal(str(trained_metrics[PRIMARY_METRIC]))
    improvement = (
        (baseline_primary - trained_primary) / baseline_primary * Decimal(100)
        if baseline_primary > 0
        else Decimal(0)
    )

    train_count = sum(1 for example in examples if example.split == "train")
    test_count = sum(1 for example in examples if example.split == "test")
    feature_dates = [str(row["date"]) for row in feature_rows]

    return {
        "report_name": "retailops-trained-demand-forecast-evaluation",
        "model_name": MODEL_NAME,
        "model_version": MODEL_VERSION,
        "model_type": MODEL_TYPE,
        "model_status": model_status,
        "primary_metric": PRIMARY_METRIC,
        "primary_metric_improvement_percent": _metric(improvement),
        "baseline_model_name": "retailops-demand-baseline-moving-average",
        "evaluation_type": "legacy_rolling_holdout",
        "evaluation_scope": EVALUATION_SCOPE,
        "profile": config.dataset.profile,
        "seed": config.dataset.seed,
        "random_state": config.random_state,
        "n_estimators": config.n_estimators,
        "window_days": config.window_days,
        "holdout_days": config.holdout_days,
        "feature_dataset_id": str(feature_rows[0]["dataset_id"]) if feature_rows else "",
        "feature_grain": GRAIN,
        "target": TARGET,
        "feature_row_count": len(feature_rows),
        "training_row_count": train_count,
        "test_row_count": test_count,
        "trained_model_metrics": trained_metrics,
        "baseline_metrics": baseline_metrics,
        "top_features": feature_importance_rows[:10],
        "feature_date_start": min(feature_dates) if feature_dates else "",
        "feature_date_end": max(feature_dates) if feature_dates else "",
        "generator_version": GENERATOR_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "artifacts": [
            MODEL_ARTIFACT_FILENAME,
            METRICS_FILENAME,
            PREDICTIONS_FILENAME,
            FEATURE_IMPORTANCE_FILENAME,
            MODEL_METADATA_FILENAME,
            MODEL_CARD_FILENAME,
        ],
    }


def build_model_metadata(metrics_report: dict[str, object]) -> dict[str, object]:
    return {
        "model_name": metrics_report["model_name"],
        "model_version": metrics_report["model_version"],
        "model_type": metrics_report["model_type"],
        "experiment_id": metrics_report["experiment_id"],
        "run_id": metrics_report["run_id"],
        "model_id": metrics_report["model_id"],
        "evaluation_scope": metrics_report["evaluation_scope"],
        "status": metrics_report["model_status"],
        "primary_metric": metrics_report["primary_metric"],
        "primary_metric_improvement_percent": metrics_report["primary_metric_improvement_percent"],
        "feature_dataset_id": metrics_report["feature_dataset_id"],
        "training_row_count": metrics_report["training_row_count"],
        "test_row_count": metrics_report["test_row_count"],
        "trained_model_metrics": metrics_report["trained_model_metrics"],
        "baseline_metrics": metrics_report["baseline_metrics"],
        "artifacts": {
            "model": MODEL_ARTIFACT_FILENAME,
            "metrics": METRICS_FILENAME,
            "predictions": PREDICTIONS_FILENAME,
            "feature_importance": FEATURE_IMPORTANCE_FILENAME,
            "model_card": MODEL_CARD_FILENAME,
        },
        "created_at": metrics_report["generated_at"],
    }


def build_model_card(metrics_report: dict[str, object]) -> str:
    trained_metrics = metrics_report["trained_model_metrics"]
    baseline_metrics = metrics_report["baseline_metrics"]
    top_features = metrics_report["top_features"]
    if not isinstance(trained_metrics, dict) or not isinstance(baseline_metrics, dict):
        msg = "metrics must be dictionaries."
        raise TypeError(msg)
    if not isinstance(top_features, list):
        msg = "top_features must be a list."
        raise TypeError(msg)

    feature_lines = [
        f"- `{row['feature']}`: `{row['importance']}`"
        for row in top_features[:10]
        if isinstance(row, dict)
    ]

    return "\n".join(
        [
            "# RetailOps Demand Forecast Random Forest Model Card",
            "",
            f"- Model: `{metrics_report['model_name']}`",
            f"- Version: `{metrics_report['model_version']}`",
            f"- Type: `{metrics_report['model_type']}`",
            f"- Experiment ID: `{metrics_report['experiment_id']}`",
            f"- Run ID: `{metrics_report['run_id']}`",
            f"- Model ID: `{metrics_report['model_id']}`",
            f"- Status: `{metrics_report['model_status']}`",
            f"- Feature dataset: `{metrics_report['feature_dataset_id']}`",
            f"- Evaluation method: `{metrics_report['evaluation_type']}`",
            f"- Evaluation scope: `{metrics_report['evaluation_scope']}`",
            f"- Primary metric: `{metrics_report['primary_metric']}`",
            f"- Primary metric improvement: `{metrics_report['primary_metric_improvement_percent']}%`",
            "",
            "## Data",
            "",
            "The model trains on deterministic RetailOps synthetic demand forecast features.",
            "The split is time-based: older rows are used for training and the latest holdout",
            "window is used for evaluation.",
            "",
            "## Features",
            "",
            "The feature set combines calendar fields, product/store/channel identifiers,",
            "stable product descriptors, and historical lag/rolling sales known at origin.",
            "Realized prices, promotions without known-at timestamps, stockout, inventory,",
            "simulator truth and current product status are excluded.",
            "",
            "## Baseline Comparison",
            "",
            f"- Trained WAPE: `{trained_metrics['wape']}`",
            f"- Baseline WAPE: `{baseline_metrics['wape']}`",
            f"- Trained MAE: `{trained_metrics['mae']}`",
            f"- Baseline MAE: `{baseline_metrics['mae']}`",
            "",
            "## Top Feature Importances",
            "",
            *(feature_lines or ["- No feature importances available."]),
            "",
            "## Limitations",
            "",
            "- The data is synthetic and local-first.",
            "- The model is trained for offline evaluation, not production online serving.",
            "- Holdout evaluation uses known historical lag values in a rolling backtest.",
            "- Candidate status in this legacy protocol does not admit the model for use.",
            "- There is no automated approval workflow, rollback automation, or retraining scheduler yet.",
            "",
            "## Next Improvements",
            "",
            "- Add a reusable train/evaluate CI gate.",
            "- Add model card generation into the model registry flow.",
            "- Add production-grade inference only after deployment and rollback controls exist.",
            "",
        ],
    )


def write_trained_model_artifacts(
    output_dir: Path,
    model: Pipeline,
    metrics_report: dict[str, object],
    predictions: list[dict[str, object]],
    feature_importance_rows: list[dict[str, object]],
    experiment_inputs: dict[str, object],
    source_paths: list[Path],
    source_hashes: dict[str, str],
) -> None:
    if output_dir.exists() and any(output_dir.iterdir()):
        msg = f"Output directory is not empty; refusing to overwrite experiment: {output_dir}"
        raise FileExistsError(msg)
    output_dir.mkdir(parents=True, exist_ok=True)
    repo_root = Path(__file__).resolve().parents[2]
    if any(
        file_sha256(path) != source_hashes[path.relative_to(repo_root).as_posix()]
        for path in source_paths
    ):
        msg = "Experiment source changed during training; refusing to publish the run."
        raise RuntimeError(msg)
    write_source_archive(repo_root, source_paths, output_dir / SOURCE_ARCHIVE_FILENAME)
    json_file(output_dir / INPUT_MANIFEST_FILENAME, experiment_inputs)
    joblib.dump(model, output_dir / MODEL_ARTIFACT_FILENAME)
    metrics_report["model_id"] = "sha256:" + file_sha256(output_dir / MODEL_ARTIFACT_FILENAME)
    (output_dir / METRICS_FILENAME).write_text(
        json.dumps(metrics_report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / MODEL_METADATA_FILENAME).write_text(
        json.dumps(build_model_metadata(metrics_report), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / MODEL_CARD_FILENAME).write_text(
        build_model_card(metrics_report),
        encoding="utf-8",
    )

    with (output_dir / PREDICTIONS_FILENAME).open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=PREDICTION_COLUMNS)
        writer.writeheader()
        writer.writerows(predictions)

    with (output_dir / FEATURE_IMPORTANCE_FILENAME).open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(file, fieldnames=["feature", "importance"])
        writer.writeheader()
        writer.writerows(feature_importance_rows)

    artifact_names = [
        MODEL_ARTIFACT_FILENAME,
        METRICS_FILENAME,
        PREDICTIONS_FILENAME,
        FEATURE_IMPORTANCE_FILENAME,
        MODEL_METADATA_FILENAME,
        MODEL_CARD_FILENAME,
        INPUT_MANIFEST_FILENAME,
        SOURCE_ARCHIVE_FILENAME,
    ]
    json_file(
        output_dir / RUN_MANIFEST_FILENAME,
        {
            "experiment_id": metrics_report["experiment_id"],
            "run_id": metrics_report["run_id"],
            "model_id": metrics_report["model_id"],
            "evaluation_scope": EVALUATION_SCOPE,
            "artifact_sha256": artifact_checksums(output_dir, artifact_names),
            "predictions_logical_sha256": logical_rows_sha256(predictions),
        },
    )


def train_random_forest_forecast_model(
    config: RandomForestForecastConfig,
) -> dict[str, object]:
    if config.output_dir is not None and config.output_root is not None:
        msg = "Choose either output_dir or output_root, not both."
        raise ValueError(msg)
    run_id = uuid.uuid4().hex
    output_dir = (
        config.output_dir
        or (config.output_root or default_trained_model_output_root(config.dataset.profile))
        / run_id
    )
    if output_dir.exists() and any(output_dir.iterdir()):
        msg = f"Output directory is not empty; refusing to overwrite experiment: {output_dir}"
        raise FileExistsError(msg)
    repo_root = Path(__file__).resolve().parents[2]
    source, source_paths, source_hashes = source_identity(repo_root)
    environment = environment_identity()
    tables = build_dataset(config.dataset)
    feature_rows = build_demand_feature_rows(tables, config.dataset)
    experiment_inputs = build_experiment_inputs(config, tables, feature_rows, source, environment)
    experiment_id = "rf-" + canonical_sha256(experiment_inputs)[:20]
    examples = build_supervised_examples(
        feature_rows,
        holdout_days=config.holdout_days,
        window_days=config.window_days,
    )
    train_examples = [example for example in examples if example.split == "train"]
    test_examples = [example for example in examples if example.split == "test"]
    if not train_examples:
        msg = "Not enough historical rows to train the random forest model."
        raise ValueError(msg)
    if not test_examples:
        msg = "Not enough holdout rows to evaluate the random forest model."
        raise ValueError(msg)

    model = build_random_forest_pipeline(
        n_estimators=config.n_estimators,
        random_state=config.random_state,
    )
    model.fit(
        [example.features for example in train_examples],
        [example.target for example in train_examples],
    )
    predictions = build_predictions(
        model,
        examples,
        feature_rows,
        window_days=config.window_days,
    )
    feature_importance_rows = build_feature_importance_rows(model)
    metrics_report = build_metrics_report(
        config,
        feature_rows,
        examples,
        predictions,
        feature_importance_rows,
    )
    metrics_report["experiment_id"] = experiment_id
    metrics_report["run_id"] = run_id
    metrics_report["artifacts"] = [
        MODEL_ARTIFACT_FILENAME,
        METRICS_FILENAME,
        PREDICTIONS_FILENAME,
        FEATURE_IMPORTANCE_FILENAME,
        MODEL_METADATA_FILENAME,
        MODEL_CARD_FILENAME,
        INPUT_MANIFEST_FILENAME,
        SOURCE_ARCHIVE_FILENAME,
        RUN_MANIFEST_FILENAME,
    ]
    write_trained_model_artifacts(
        output_dir,
        model,
        metrics_report,
        predictions,
        feature_importance_rows,
        experiment_inputs,
        source_paths,
        source_hashes,
    )
    metrics_report["output_dir"] = str(output_dir)
    return metrics_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train and evaluate RetailOps RandomForest demand forecast model.",
    )
    parser.add_argument("--profile", choices=("demo", "small", "medium", "large"), default="demo")
    parser.add_argument("--days", type=int)
    parser.add_argument("--products", type=int)
    parser.add_argument("--stores", type=int)
    parser.add_argument("--warehouses", type=int)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--window-days", type=int, default=DEFAULT_WINDOW_DAYS)
    parser.add_argument("--horizon-days", type=int, default=DEFAULT_HORIZON_DAYS)
    parser.add_argument("--holdout-days", type=int, default=DEFAULT_HOLDOUT_DAYS)
    parser.add_argument("--n-estimators", type=int, default=DEFAULT_N_ESTIMATORS)
    parser.add_argument("--random-state", type=int, default=DEFAULT_RANDOM_STATE)
    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument("--output-dir", type=Path)
    output_group.add_argument("--output-root", type=Path)
    return parser.parse_args()


def config_from_args(args: argparse.Namespace) -> RandomForestForecastConfig:
    return RandomForestForecastConfig(
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
        n_estimators=args.n_estimators,
        random_state=args.random_state,
        output_dir=args.output_dir,
        output_root=args.output_root,
    )


def main() -> None:
    config = config_from_args(parse_args())
    metrics_report = train_random_forest_forecast_model(config)

    print(  # noqa: T201 - CLI output
        "RetailOps trained demand forecast model generated: "
        f"{metrics_report['model_status']} "
        f"({metrics_report['primary_metric']} improvement "
        f"{metrics_report['primary_metric_improvement_percent']}%)",
    )
    print(f"Experiment ID: {metrics_report['experiment_id']}")  # noqa: T201 - CLI output
    print(f"Run ID: {metrics_report['run_id']}")  # noqa: T201 - CLI output
    print(f"Model ID: {metrics_report['model_id']}")  # noqa: T201 - CLI output
    print(f"Output directory: {metrics_report['output_dir']}")  # noqa: T201 - CLI output


if __name__ == "__main__":
    main()
