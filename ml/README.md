# ML

Machine learning and MLOps in RetailOps are implemented as a local-first
forecasting lifecycle foundation. The current scope includes deterministic
feature generation, a moving-average baseline model, evaluation, local metadata
registry artifacts, batch inference outputs, model performance metrics, and
feature drift checks.

This is not a production model serving platform. There is no managed feature
store, cloud model registry, automated retraining scheduler, online inference
service, model approval workflow, or production deployment automation yet.

## Scope

Current local lifecycle assets include:

- a versioned demand forecasting feature dataset contract,
- deterministic demand feature generation,
- baseline demand forecasting,
- model evaluation and validation reports,
- local model metadata registry artifacts,
- batch inference artifacts,
- model performance metrics,
- demand feature drift checks,
- documentation of lifecycle assumptions and limitations.

Future work includes managed feature storage, production serving, automated
promotion, retraining, cloud registry integration, and approval workflows.

See [RetailOps MLOps Lifecycle](../docs/mlops-lifecycle.md) for the operating
model.

## Contracts

Sprint 12 includes a dataset contract and local MLOps jobs:

- [Demand forecast feature dataset contract](contracts/README.md)
- `contracts/demand_forecast_features.schema.json`
- `contracts/demand_forecast_feature_manifest.schema.json`
- `python -m ml.features.demand_forecast --profile small`
- `python -m ml.models.baseline_forecast --profile small`
- `python -m ml.evaluation.baseline_report --profile small`
- `python -m ml.metadata.model_registry --profile small`
- `python -m ml.inference.batch_forecast --profile small`
- `python -m ml.observability.model_performance_metrics --profile small`
- `python -m ml.drift.demand_feature_drift --profile small`

The contract fixes the first forecasting feature grain as `date`, `product_id`,
`store_id`, and `channel`, with `units_sold` as the target. Production model
serving, automated promotion, and retraining remain future work.

The demand feature job writes `features.csv` and `feature_manifest.json` under
`data/synthetic/<profile>/features/demand_forecast/` by default. Generated
feature datasets should stay out of Git.

The baseline forecasting model is a deterministic moving-average benchmark. It
writes `baseline_forecasts.csv` and `model_manifest.json` under
`data/synthetic/<profile>/models/demand_baseline/` by default. It is intended as
a local reference model for later evaluation and model metadata commits, not as
an inference service or promoted model registry entry.

The baseline evaluation job runs a rolling holdout backtest and writes
`evaluation_report.json`, `evaluation_summary.md`, and `backtest_predictions.csv`
under `data/synthetic/<profile>/reports/demand_baseline/` by default. The report
captures MAE, RMSE, MAPE, bias, WAPE, skipped rows, dataset lineage, and model
version.

The model metadata job persists local model registry artifacts:
`model_metadata.json` and `model_registry.jsonl` under
`data/synthetic/<profile>/metadata/model_registry/` by default. The metadata
links model version, status, feature dataset lineage, training window, evaluation
metrics, and local artifact paths. API/database persistence remains a later
commit.

The batch inference job writes `batch_predictions.csv`, `api_forecasts.csv`, and
`batch_inference_manifest.json` under
`data/synthetic/<profile>/inference/demand_baseline/` by default. The
`api_forecasts.csv` artifact is shaped like the API `forecasts` seed contract so
a later import/persistence step can load forecast outputs without retraining.

The model performance metrics job writes `model_performance.prom` and
`model_performance_snapshot.json` under
`data/synthetic/<profile>/observability/model_performance/` by default. The
Prometheus text artifact exposes model identity, evaluation MAE/RMSE/MAPE/WAPE,
forecast bias, evaluated/skipped rows, batch forecast counts, and artifact
freshness for local textfile ingestion or CI evidence.

The demand feature drift job compares deterministic reference and current
feature datasets and writes `drift_report.json` and `drift_summary.md` under
`data/synthetic/<profile>/reports/demand_feature_drift/` by default. The report
checks row-count drift, numeric mean drift, and categorical distribution drift
with configurable warning and failure thresholds.
