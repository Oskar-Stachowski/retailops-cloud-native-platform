from uuid import UUID

from app.domain.models import Forecast
from app.repositories.forecast_repository import ForecastRepository


FORECAST_AVAILABLE = "available"
FORECAST_MISSING = "missing"


class ForecastService:
    def __init__(self, forecast_repository: ForecastRepository):
        self.forecast_repository = forecast_repository

    def list_forecasts_for_product(self, product_id: UUID) -> list[Forecast]:
        return self.forecast_repository.list_forecasts_for_product(product_id)

    def get_latest_forecast_for_product(self, product_id: UUID) -> Forecast | None:
        return self.forecast_repository.get_latest_forecast_for_product(product_id)

    def get_forecast_availability_for_product(self, product_id: UUID) -> str:
        latest_forecast = (
            self.forecast_repository.get_latest_forecast_for_product(product_id)
        )

        if latest_forecast is None:
            return FORECAST_MISSING

        return FORECAST_AVAILABLE
