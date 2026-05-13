# RetailOps Demand Forecast Random Forest Model Card

## Model

- Name: `retailops-demand-random-forest`
- Version: `random-forest-v1`
- Type: `sklearn_random_forest_regressor`
- Lifecycle scope: local trained ML model, not production serving

## Data

The model uses the RetailOps demand forecast feature dataset generated from
deterministic synthetic retail data. The feature grain is:

```text
date + product_id + store_id + channel
```

The target is:

```text
units_sold
```

## Features

The training workflow uses calendar, product, store, channel, pricing,
promotion, inventory, and historical demand features. Historical demand features
include lag and rolling-window statistics computed only from rows before the
row being predicted.

## Evaluation

Evaluation uses a time-based holdout split. Older rows train the model and the
latest holdout window evaluates it. The trained model is compared with the
existing moving-average baseline on WAPE, MAE, RMSE, MAPE, and bias.

The model is marked `candidate` only when the trained model beats the
moving-average baseline on WAPE. Otherwise it is marked `rejected`.

## Limitations

- Data is synthetic and local-first.
- The model is not exposed as an online inference service.
- The workflow does not include automated approval, rollback, or retraining.
- The holdout backtest uses known historical lag values and is not a production
  multi-step forecasting simulation.

## Next Improvements

- Add a CI gate that runs the trained model workflow on a bounded profile.
- Add richer feature validation before training.
- Add lineage reports across feature, model, evaluation, inference, and drift
  artifacts.
- Introduce production serving only after deployment, rollback, and monitoring
  controls exist.
