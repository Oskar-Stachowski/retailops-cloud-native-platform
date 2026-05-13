# RandomForest Demand Forecast Evidence

This folder is a tracked evidence snapshot for the local trained RetailOps
demand forecasting model.

## Validation Command

```bash
PYTHONPATH=. services/api/.venv/bin/python -m ml.models.random_forest_forecast \
  --profile small \
  --window-days 28 \
  --holdout-days 7 \
  --n-estimators 20 \
  --output-dir /private/tmp/retailops-rf-evidence
```

## Result

| Metric | RandomForest | Moving-average baseline |
| --- | ---: | ---: |
| WAPE | `72.1146` | `81.0797` |
| MAE | `175.7245` | `197.5701` |
| RMSE | `401.3852` | `429.1787` |
| MAPE | `75.4369` | `85.4670` |
| Bias | `88.7861` | `98.5247` |

Primary metric: `wape`

Primary metric improvement: `11.0571%`

Model status: `candidate`

## Snapshot Details

| Field | Value |
| --- | --- |
| Model | `retailops-demand-random-forest` |
| Version | `random-forest-v1` |
| Type | `sklearn_random_forest_regressor` |
| Profile | `small` |
| Dataset | `retailops-demand-forecast-features-small-2026-01-31-2026-04-30-seed42` |
| Training rows | `11227` |
| Test rows | `991` |
| Feature rows | `12718` |
| Holdout days | `7` |
| Window days | `28` |
| Estimators | `20` |
| Random state | `42` |

## Files

| File | Purpose |
| --- | --- |
| `random_forest_model.joblib` | Serialized scikit-learn pipeline with `DictVectorizer` and `RandomForestRegressor`. |
| `metrics.json` | Evaluation report and baseline comparison. |
| `predictions.csv` | Time-based holdout predictions with actuals and baseline predictions. |
| `feature_importance.csv` | RandomForest feature importance report. |
| `model_metadata.json` | Local model metadata/status snapshot. |
| `model_card.md` | Generated model card for this version. |
| `checksums.sha256` | SHA-256 checksums for evidence integrity. |

## Interpretation

This is real local ML evidence: the model is trained from RetailOps feature rows
and compared against the moving-average baseline on a time-based holdout split.
It is not a production serving deployment and does not imply MLflow, feature
store, KServe, retraining automation, or cloud model registry maturity.
