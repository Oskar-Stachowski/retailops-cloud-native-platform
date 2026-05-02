from datetime import date
from uuid import UUID

from app.domain.models import Forecast
from app.repositories.forecast_repository import ForecastRepository
from app.services.serialization import make_json_safe


FORECAST_AVAILABLE = "available"
FORECAST_MISSING = "missing"


class ForecastService:
    """Application service for forecast reads."""

    def __init__(self, forecast_repository: ForecastRepository | None = None):
        self.forecast_repository = forecast_repository or ForecastRepository()

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

    def list_forecasts_response(
        self,
        product_id: UUID | None = None,
        status: str | None = None,
        method: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "forecast_period_start",
        sort_order: str = "asc",
    ) -> dict:
        forecasts = self.forecast_repository.list_forecasts(
            product_id=product_id,
            status=status,
            method=method,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        total = self.forecast_repository.count_forecasts(
            product_id=product_id,
            status=status,
            method=method,
            date_from=date_from,
            date_to=date_to,
        )

        return {
            "items": [
                make_json_safe(forecast.model_dump())
                for forecast in forecasts
            ],
            "pagination": {
                "limit": limit,
                "offset": offset,
                "total": total,
            },
        }

    def get_forecast_detail_response(self, forecast_id: UUID) -> dict | None:
        forecast = self.forecast_repository.get_forecast_by_id(forecast_id)

        if forecast is None:
            return None

        return make_json_safe(forecast.model_dump())
