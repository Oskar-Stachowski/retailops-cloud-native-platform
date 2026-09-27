from __future__ import annotations

import pytest

from ml.evaluation.baseline_report import calculate_metrics as baseline_metrics
from ml.evaluation.fixed_origin import _metrics as fold_metrics
from ml.models.random_forest_forecast import (
    calculate_prediction_metrics,
    fixed_prediction_rows,
    model_status_from_metrics,
)


@pytest.mark.parametrize("calculator", [
    baseline_metrics,
    lambda rows: fold_metrics(rows, "predicted_units"),
    lambda rows: calculate_prediction_metrics(rows, prediction_field="predicted_units"),
])
def test_zero_actual_overforecast_is_visible_but_percentage_metrics_are_undefined(calculator) -> None:
    metrics = calculator([{"actual_units": 0, "predicted_units": 100}])
    assert metrics["status"] == "not_evaluable"
    assert metrics["wape"] is None
    assert metrics["mape"] is None
    assert metrics["mape_evaluated_rows"] == 0
    assert metrics["mape_coverage"] == "0.0000"
    assert metrics["zero_actual_rows"] == 1
    assert metrics["zero_actual_overforecast_units"] == "100.0000"
    assert metrics["mae"] == "100.0000"
    assert model_status_from_metrics(metrics, metrics) == "rejected"


@pytest.mark.parametrize("calculator", [
    baseline_metrics,
    lambda rows: fold_metrics(rows, "predicted_units"),
    lambda rows: calculate_prediction_metrics(rows, prediction_field="predicted_units"),
])
def test_mape_counts_only_positive_actuals(calculator) -> None:
    metrics = calculator([
        {"actual_units": 0, "predicted_units": 100},
        {"actual_units": 10, "predicted_units": 8},
    ])
    assert metrics["status"] == "evaluable"
    assert metrics["mape"] == "20.0000"
    assert metrics["mape_evaluated_rows"] == 1
    assert metrics["mape_coverage"] == "0.5000"
    assert metrics["wape"] == "1020.0000"
    assert metrics["mae"] == "51.0000"


@pytest.mark.parametrize("calculator", [
    baseline_metrics,
    lambda rows: fold_metrics(rows, "predicted_units"),
    lambda rows: calculate_prediction_metrics(rows, prediction_field="predicted_units"),
])
def test_empty_evaluation_has_no_successful_metric(calculator) -> None:
    metrics = calculator([])
    assert metrics["status"] == "not_evaluable"
    assert metrics["evaluated_rows"] == 0
    assert metrics["wape"] is None
    assert metrics["mae"] is None
    assert model_status_from_metrics(metrics, metrics) == "rejected"


@pytest.mark.parametrize("actual,predicted", [
    ("NaN", 1), ("Infinity", 1), (-1, 1), (1, "NaN"), (1, -1), (1, None),
])
def test_invalid_evaluation_values_are_rejected(actual: object, predicted: object) -> None:
    with pytest.raises(ValueError, match="Invalid .*units"):
        baseline_metrics([{"actual_units": actual, "predicted_units": predicted}])


def test_zero_actual_has_no_row_percentage_error() -> None:
    row = fixed_prediction_rows([{
        "split": "test", "origin": "2026-01-01", "forecast_date": "2026-01-02",
        "horizon_day": 1, "product_id": "p", "store_id": "s", "channel": "web",
        "actual_units": 0, "predicted_units": 100, "baseline_predicted_units": 0,
    }], "dataset")[0]
    assert row["absolute_percentage_error"] == ""
    assert row["baseline_absolute_percentage_error"] == ""
