"""Demand forecast metrics with explicit denominator and coverage semantics."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation


def _metric(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))


def _units(row: dict[str, object], field: str) -> Decimal:
    try:
        value = row[field]
        if isinstance(value, bool) or value is None:
            raise ValueError
        number = Decimal(str(value))
    except (KeyError, InvalidOperation, TypeError, ValueError) as exc:
        msg = f"Invalid {field} in evaluation row."
        raise ValueError(msg) from exc
    if not number.is_finite() or number < 0:
        msg = f"Invalid {field} in evaluation row: expected finite, nonnegative units."
        raise ValueError(msg)
    return number


def calculate_forecast_metrics(
    predictions: list[dict[str, object]],
    *,
    prediction_field: str,
) -> dict[str, object]:
    """Return JSON-safe metrics; MAPE covers only strictly positive actuals."""
    if not predictions:
        return {
            "status": "not_evaluable",
            "evaluated_rows": 0,
            "mape_evaluated_rows": 0,
            "mape_coverage": "0.0000",
            "zero_actual_rows": 0,
            "zero_actual_overforecast_units": "0.0000",
            "mae": None,
            "rmse": None,
            "mape": None,
            "bias": None,
            "wape": None,
        }

    absolute_errors: list[Decimal] = []
    squared_errors: list[Decimal] = []
    signed_errors: list[Decimal] = []
    percentage_errors: list[Decimal] = []
    actual_total = Decimal(0)
    zero_actual_rows = 0
    zero_actual_overforecast = Decimal(0)
    for row in predictions:
        actual = _units(row, "actual_units")
        predicted = _units(row, prediction_field)
        error = predicted - actual
        absolute_error = abs(error)
        actual_total += actual
        signed_errors.append(error)
        absolute_errors.append(absolute_error)
        squared_errors.append(error * error)
        if actual > 0:
            percentage_errors.append(absolute_error / actual * Decimal(100))
        else:
            zero_actual_rows += 1
            zero_actual_overforecast += predicted

    row_count = Decimal(len(predictions))
    mape_count = len(percentage_errors)
    return {
        "status": "evaluable" if actual_total > 0 else "not_evaluable",
        "evaluated_rows": len(predictions),
        "mape_evaluated_rows": mape_count,
        "mape_coverage": _metric(Decimal(mape_count) / row_count),
        "zero_actual_rows": zero_actual_rows,
        "zero_actual_overforecast_units": _metric(zero_actual_overforecast),
        "mae": _metric(sum(absolute_errors) / row_count),
        "rmse": _metric((sum(squared_errors) / row_count).sqrt()),
        "mape": _metric(sum(percentage_errors) / Decimal(mape_count)) if mape_count else None,
        "bias": _metric(sum(signed_errors) / row_count),
        "wape": _metric(sum(absolute_errors) / actual_total * Decimal(100))
        if actual_total > 0
        else None,
    }
