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

Sprint 12 starts with a dataset contract only:

- [Demand forecast feature dataset contract](contracts/README.md)
- `contracts/demand_forecast_features.schema.json`
- `contracts/demand_forecast_feature_manifest.schema.json`

The contract fixes the first forecasting feature grain as `date`, `product_id`,
`store_id`, and `channel`, with `units_sold` as the target. Feature generation,
model training, inference writes, and drift monitoring remain future commits.
