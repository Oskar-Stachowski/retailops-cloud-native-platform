from __future__ import annotations

from data.generator.common import confidence, deterministic_uuid, iso_date
from data.generator.common import utc_datetime
from data.generator.scenarios import UNIT_OF_MEASURE


def _prediction_for(product: dict[str, str]) -> tuple[int, float]:
    normal_daily_sales = int(product["normal_daily_sales"])
    scenario = product["scenario"]

    if scenario == "sales_drop":
        return int(normal_daily_sales * 7 * 0.55), 0.68

    if scenario == "stockout_risk":
        return int(normal_daily_sales * 7 * 1.35), 0.82

    if scenario == "stale_inventory":
        return int(normal_daily_sales * 7 * 0.45), 0.63

    return int(normal_daily_sales * 7 * 0.95), 0.78


def generate_forecasts(products: list[dict[str, str]]) -> list[dict[str, str]]:
    forecasts: list[dict[str, str]] = []

    for index, product in enumerate(products[:6]):
        predicted_quantity, confidence_score = _prediction_for(product)
        natural_key = f"{product['sku']}-weekly-forecast"
        unit_of_measure = UNIT_OF_MEASURE[index % len(UNIT_OF_MEASURE)]

        forecasts.append(
            {
                "id": deterministic_uuid("forecast", natural_key),
                "product_id": product["id"],
                "forecast_period_start": iso_date(days_offset=index + 1),
                "forecast_period_end": iso_date(days_offset=index + 7),
                "predicted_quantity": str(predicted_quantity),
                "unit_of_measure": unit_of_measure,
                "generated_at": utc_datetime(hours_offset=-2),
                "method": "retailops-baseline-demand-model",
                "status": "generated",
                "confidence_level": confidence(confidence_score),
                # "model_version": "0.1.0-demo",
            }
        )

    return forecasts


def forecast_by_product_id(
    forecasts: list[dict[str, str]],
    product_id: str,
) -> dict[str, str] | None:
    return next(
        (
            forecast
            for forecast in forecasts
            if forecast["product_id"] == product_id
        ),
        None,
    )
