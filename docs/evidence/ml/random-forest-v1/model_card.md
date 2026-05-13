# RetailOps Demand Forecast Random Forest Model Card

- Model: `retailops-demand-random-forest`
- Version: `random-forest-v1`
- Type: `sklearn_random_forest_regressor`
- Status: `candidate`
- Feature dataset: `retailops-demand-forecast-features-small-2026-01-31-2026-04-30-seed42`
- Evaluation method: `time_based_holdout`
- Primary metric: `wape`
- Primary metric improvement: `11.0571%`

## Data

The model trains on deterministic RetailOps synthetic demand forecast features.
The split is time-based: older rows are used for training and the latest holdout
window is used for evaluation.

## Features

The feature set combines calendar fields, product/store/channel identifiers,
pricing and promotion fields, inventory signals, and lag/rolling demand features.

## Baseline Comparison

- Trained WAPE: `72.1146`
- Baseline WAPE: `81.0797`
- Trained MAE: `175.7245`
- Baseline MAE: `197.5701`

## Top Feature Importances

- `unit_price`: `0.3764`
- `rolling_mean_units`: `0.1549`
- `lag_1_units`: `0.1089`
- `lag_7_units`: `0.0977`
- `rolling_max_units`: `0.0683`
- `training_observation_count`: `0.0327`
- `day_of_week`: `0.0303`
- `inventory_on_hand`: `0.0237`
- `rolling_min_units`: `0.0231`
- `stockout_flag`: `0.0125`

## Limitations

- The data is synthetic and local-first.
- The model is trained for offline evaluation, not production online serving.
- Holdout evaluation uses known historical lag values in a rolling backtest.
- There is no automated approval workflow, rollback automation, or retraining scheduler yet.

## Next Improvements

- Add a reusable train/evaluate CI gate.
- Add model card generation into the model registry flow.
- Add production-grade inference only after deployment and rollback controls exist.
