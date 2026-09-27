# RetailOps Demand Forecast Random Forest Model Card

- Model: `retailops-demand-random-forest`
- Version: `random-forest-v3`
- Type: `sklearn_random_forest_regressor`
- Experiment ID: `rf-a2161d63d4f37f978620`
- Run ID: `4d88f7e8e1334360afc0d662b1375b68`
- Model ID: `sha256:571d1b303e2fe1c11b31ea88b79c100d1e6497d3447cd2e995435192a60667ab`
- Status: `rejected`
- Feature dataset: `retailops-demand-forecast-features-small-2026-01-31-2026-04-30-seed42`
- Evaluation method: `fixed_origin_horizon`
- Evaluation scope: `synthetic_fixed_origin_horizon_v1`
- Primary metric: `wape`
- Primary metric improvement: `-7.8678%`
- Admission policy: `retailops-forecast-local-v1`

## Admission Checks

- `protocol`: `passed` — Chronological, disjoint folds and identical scored rows for RF and baseline.
- `coverage`: `passed` — All eligible rows scored in every fold.
- `final_quality`: `failed` — Final-test WAPE improvement is insufficient or undefined.
- `stability`: `passed` — RF beats baseline in enough validation windows.
- `segments`: `failed` — A store or channel segment lacks rows or exceeds the MAE limit.
- `reproduction`: `passed` — Source snapshot and saved model reproduce evaluated final-test predictions.

## Data

The model trains on deterministic RetailOps synthetic demand forecast features.
Three chronological validation windows precede a held-out final test.
Each window forecasts the full horizon from one frozen origin.

## Features

The feature set combines calendar fields, product/store/channel identifiers,
stable product descriptors, and historical lag/rolling sales known at origin.
Realized prices, promotions without known-at timestamps, stockout, inventory,
simulator truth and current product status are excluded.

## Baseline Comparison

- Trained WAPE: `159.8564`
- Baseline WAPE: `148.1966`
- Metric status: `evaluable`
- MAPE coverage: `222/700`
- Overforecast on zero actuals (units): `23621.0000`
- Trained MAE: `58.5029`
- Baseline MAE: `54.2357`

## Top Feature Importances

- `rolling_max_units`: `0.2359`
- `rolling_mean_units`: `0.1824`
- `day_of_week`: `0.1678`
- `horizon_day`: `0.1123`
- `lag_1_units`: `0.0931`
- `lag_7_units`: `0.0695`
- `week_of_year`: `0.0642`
- `product_id=576f0781-3104-5d50-92f3-befe834a6fa6`: `0.0145`
- `month`: `0.0104`
- `training_observation_count`: `0.0094`

## Limitations

- The data is synthetic and local-first.
- The model is trained for offline evaluation, not production online serving.
- The panel's open/active/completeness evidence is a synthetic generator declaration.
- Candidate status permits only further local synthetic validation, not serving or production release.
- There is no automated approval workflow, rollback automation, or retraining scheduler yet.

## Next Improvements

- Add a reusable train/evaluate CI gate.
- Add model card generation into the model registry flow.
- Add production-grade inference only after deployment and rollback controls exist.
