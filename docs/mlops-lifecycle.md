# RetailOps MLOps Lifecycle

## Purpose

This document defines the implemented local MLOps lifecycle for the RetailOps
demand forecasting baseline. It covers feature contracts, baseline model
generation, evaluation, metadata, forecast persistence boundaries, batch
inference, model metrics, drift checks, and promotion expectations.

The lifecycle is intentionally local-first. It provides deterministic artifacts
and CI-testable contracts before any production model serving, managed feature
store, or cloud model registry is introduced.

## Scope

Implemented in Sprint 12:

- demand forecast feature dataset contract,
- deterministic demand feature generation job,
- moving-average baseline forecast model,
- trained RandomForestRegressor demand forecast model,
- rolling holdout evaluation report,
- local model metadata registry artifacts,
- API forecast run persistence for model run lineage,
- batch inference artifact generation,
- Prometheus textfile model performance metrics,
- demand feature drift checks.

Not implemented yet:

- managed feature store,
- online model serving endpoint,
- automated model promotion workflow,
- retraining scheduler,
- cloud model registry,
- production drift alert routing,
- human approval workflow for model promotion.

## Lifecycle Stages

| Stage | Command | Primary artifacts |
| --- | --- | --- |
| Feature contract | n/a | `ml/contracts/*.schema.json` |
| Feature generation | `make ml-features` | `features.csv`, `feature_manifest.json` |
| Baseline model | `make ml-baseline` | `baseline_forecasts.csv`, `model_manifest.json` |
| Trained model | `make ml-trained` | `random_forest_model.joblib`, `metrics.json`, `predictions.csv`, `feature_importance.csv`, `model_metadata.json`, `model_card.md` |
| Evaluation | `make ml-evaluate` | `evaluation_report.json`, `evaluation_summary.md`, `backtest_predictions.csv` |
| Metadata registry | `make ml-metadata` | `model_metadata.json`, `model_registry.jsonl` |
| Batch inference | `make ml-inference` | `batch_predictions.csv`, `api_forecasts.csv`, `batch_inference_manifest.json` |
| Performance metrics | `make ml-metrics` | `model_performance.prom`, `model_performance_snapshot.json` |
| Drift checks | `make ml-drift` | `drift_report.json`, `drift_summary.md` |

Generated artifacts are written under `data/synthetic/<profile>/...` by default
and should not be committed.

## Feature Dataset

The first ML dataset is the demand forecasting feature dataset.

Grain:

```text
date + product_id + store_id + channel
```

Target:

```text
units_sold
```

The contract is versioned in:

- `ml/contracts/demand_forecast_features.schema.json`
- `ml/contracts/demand_forecast_feature_manifest.schema.json`
- `ml/contracts/README.md`

Feature generation uses deterministic synthetic data. The same profile,
parameters, and seed produce the same dataset identity and row contents.

## Baseline Model

The baseline model is a deterministic moving-average benchmark. It is not a
production model and should be treated as the minimum reference point for later
forecasting work.

The baseline job records:

- model name and version,
- feature dataset lineage,
- forecast horizon,
- moving-average window,
- generated forecast rows,
- local model artifacts.

This baseline exists so future models can be compared against a stable,
repeatable reference.

## Trained Model

The trained demand forecasting model uses scikit-learn
`RandomForestRegressor`. It is still local-first, but unlike the moving-average
baseline it learns relationships from engineered features and persists a
reusable `joblib` model artifact.

The trained workflow uses:

- calendar features,
- product, store, and channel identifiers,
- pricing and promotion signals,
- inventory signals,
- lag demand features,
- rolling demand statistics.

Evaluation uses a time-based holdout split, not a random split. The model is
compared against the moving-average baseline on WAPE, MAE, RMSE, MAPE, and
bias. The model metadata status is `candidate` only when RandomForest beats the
baseline on WAPE; otherwise it is `rejected`.

## Evaluation

The evaluation job runs a rolling holdout backtest. The report captures:

- evaluated rows,
- skipped rows,
- MAE,
- RMSE,
- MAPE,
- bias,
- WAPE,
- feature dataset lineage,
- model version,
- evaluation date window.

Evaluation reports are evidence artifacts, not automatic promotion decisions.
Promotion requires a separate review against business expectations and current
drift checks.

## Model Metadata

The local metadata registry persists the current model version and appends or
updates registry entries by model version and feature dataset.

Supported lifecycle statuses are intentionally narrow:

| Status | Meaning |
| --- | --- |
| `experimental` | Local model artifact generated for exploration. |
| `candidate` | Model has evaluation and metadata and can be used by local batch inference. |
| `rejected` | Model should not be used for downstream inference. |
| `archived` | Historical artifact retained for lineage only. |

There is no `production` status yet because the repository does not have an
automated model approval, deployment, rollback, or runtime serving workflow.

## Forecast Run Persistence

The API persists forecast run metadata separately from generated forecast rows.
This gives the application a place to track:

- run identity,
- model name and version,
- status,
- forecast horizon,
- source dataset,
- execution timestamps,
- summary metrics.

The current ML batch inference job writes API-shaped forecast rows as CSV. A
later import step can connect those artifacts to API persistence without
changing the model job contract.

## Batch Inference

Batch inference regenerates upstream metadata and feature/model artifacts, then
writes:

- granular model predictions,
- API-shaped forecast rows,
- a batch inference manifest.

`api_forecasts.csv` is shaped for compatibility with the API forecast seed
contract. It is still a local artifact, not a live serving path.

## Observability

The model performance metrics job renders Prometheus text exposition format from
local ML artifacts. It includes:

- model identity and status,
- evaluated rows,
- skipped rows,
- MAE,
- RMSE,
- MAPE,
- bias,
- WAPE,
- batch prediction count,
- API forecast count,
- artifact freshness timestamp.

Prometheus alert rules live in
`observability/prometheus/rules/model-alerts.yml`. These rules define local
thresholds for missing metrics, zero-row evaluations, high MAPE/WAPE, missing
forecast output, and stale model metrics.

## Drift Checks

The demand feature drift job compares a deterministic reference dataset with a
current dataset. It checks:

- row-count relative change,
- numeric mean relative change,
- categorical max bucket share delta.

Default thresholds:

| Threshold | Value |
| --- | ---: |
| Warning | `0.1000` |
| Failure | `0.2500` |

The drift report can return `passed`, `warning`, or `failed`. A failed drift
report should block promotion and trigger investigation before any model version
is treated as a candidate for production.

## Recommended Local Review Flow

Run the lifecycle in this order:

```bash
make ml-features
make ml-baseline
make ml-trained
make ml-evaluate
make ml-metadata
make ml-inference
make ml-metrics
make ml-drift
```

Before accepting an ML change, review:

- feature manifest row counts and date range,
- evaluation metrics and skipped rows,
- model metadata status and lineage,
- batch inference forecast counts,
- model performance metrics freshness,
- drift report status,
- tests for touched ML modules.

## Quality Gates

Minimum local gate:

```bash
cd services/api
PYTHONPATH=.:../.. .venv/bin/python -m pytest \
  tests/test_demand_feature_generation.py \
  tests/test_baseline_forecasting_model.py \
  tests/test_baseline_evaluation_report.py \
  tests/test_model_metadata_registry.py \
  tests/test_batch_forecast_inference.py \
  tests/test_model_performance_metrics.py \
  tests/test_demand_feature_drift.py
```

Repository lint and formatting:

```bash
services/api/.venv/bin/python -m ruff check services/api/app services/api/scripts services/api/tests data ml
services/api/.venv/bin/python -m ruff format --check services/api/app services/api/scripts services/api/tests data ml
```

## Promotion Rules

A model can only be considered a local `candidate` when:

- feature generation succeeds,
- evaluation has non-zero evaluated rows,
- model metadata links the feature dataset and evaluation metrics,
- batch inference emits forecast rows,
- model performance metrics are generated,
- drift checks are not `failed`,
- relevant tests and lint pass.

Promotion to a true production status is future work and requires:

- explicit approval workflow,
- runtime deployment target,
- rollback path,
- production observability,
- drift alert routing,
- retraining policy,
- audit trail for model decisions.

## Operational Boundaries

This lifecycle is suitable for deterministic local validation and portfolio
evidence. It is not a managed MLOps platform yet.

Do not use the generated artifacts as production decisions without adding:

- source data governance,
- model explainability expectations,
- model approval controls,
- monitored serving infrastructure,
- rollback and incident runbooks,
- privacy and compliance review.
