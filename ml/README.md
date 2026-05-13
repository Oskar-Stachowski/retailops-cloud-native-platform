# ML

Machine learning and MLOps are future platform scope for RetailOps.

There is no implemented training pipeline, inference service, model registry, drift monitor, retraining workflow, or model deployment automation in this directory yet. Current forecasting, stock-risk, anomaly, and recommendation views are based on deterministic demo data and application-level analytics, not an operated ML lifecycle.

## Planned Scope

Future MLOps work should include:

- a versioned demand forecasting feature dataset contract,
- baseline demand forecasting experiments,
- inventory risk scoring model evaluation,
- anomaly detection experiments,
- model metrics and validation reports,
- model versioning and promotion workflow,
- drift monitoring design,
- retraining workflow,
- documentation of model assumptions and limitations.

Do not treat this directory as an implemented MLOps platform until those assets exist and are validated by tests or CI evidence.

## Contracts

Sprint 12 starts with a dataset contract and a local feature-generation job:

- [Demand forecast feature dataset contract](contracts/README.md)
- `contracts/demand_forecast_features.schema.json`
- `contracts/demand_forecast_feature_manifest.schema.json`
- `python -m ml.features.demand_forecast --profile small`
- `python -m ml.models.baseline_forecast --profile small`
- `python -m ml.evaluation.baseline_report --profile small`
- `python -m ml.metadata.model_registry --profile small`

The contract fixes the first forecasting feature grain as `date`, `product_id`,
`store_id`, and `channel`, with `units_sold` as the target. Model training,
inference writes, and drift monitoring remain future commits.

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
