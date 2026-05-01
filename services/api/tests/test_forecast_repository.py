import os
from uuid import UUID

import psycopg

from app.domain.models import Forecast
from app.repositories.forecast_repository import ForecastRepository

DATABASE_URL = os.getenv("DATABASE_URL")

EXISTING_PRODUCT_ID = UUID("85710dbe-1aea-50ac-a155-fb216e12ab97")
PRODUCT_ID_WITHOUT_FORECAST = UUID("a24a7f85-d830-55e5-90e4-afb122abd0ce")


def test_forecast_repository_lists_forecasts_for_product():
    assert DATABASE_URL is not None

    with psycopg.connect(DATABASE_URL) as conn:
        repository = ForecastRepository(conn)
        existing_forecasts = repository.list_forecasts_for_product(EXISTING_PRODUCT_ID)
        missing_forecasts = repository.list_forecasts_for_product(PRODUCT_ID_WITHOUT_FORECAST)

    assert len(existing_forecasts) >= 1
    assert all(isinstance(forecast, Forecast) for forecast in existing_forecasts)
    assert missing_forecasts == []


def test_forecast_repository_gets_latest_forecast_for_product():
    assert DATABASE_URL is not None

    with psycopg.connect(DATABASE_URL) as conn:
        repository = ForecastRepository(conn)
        existing_forecast = repository.get_latest_forecast_for_product(EXISTING_PRODUCT_ID)
        missing_forecast = repository.get_latest_forecast_for_product(PRODUCT_ID_WITHOUT_FORECAST)

    assert isinstance(existing_forecast, Forecast)
    assert missing_forecast is None
