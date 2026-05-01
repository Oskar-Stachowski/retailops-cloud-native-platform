from datetime import date, datetime, timezone
from uuid import UUID

from app.domain.models import (
    Forecast,
    ForecastMethod,
    ForecastStatus,
    UnitOfMeasure,
)
from app.services.forecast_service import (
    FORECAST_AVAILABLE,
    FORECAST_MISSING,
    ForecastService,
)


PRODUCT_WITH_FORECAST_ID = UUID("85710dbe-1aea-50ac-a155-fb216e12ab97")
PRODUCT_WITHOUT_FORECAST_ID = UUID("a24a7f85-d830-55e5-90e4-afb122abd0ce")


def make_test_forecast() -> Forecast:
    return Forecast(
        id=UUID("11111111-1111-1111-1111-111111111111"),
        product_id=PRODUCT_WITH_FORECAST_ID,
        forecast_period_start=date(2026, 5, 1),
        forecast_period_end=date(2026, 5, 7),
        predicted_quantity=120.5,
        unit_of_measure=UnitOfMeasure.pcs,
        generated_at=datetime.now(timezone.utc),
        method=ForecastMethod.seeded_demo,
        status=ForecastStatus.generated,
        confidence_level=0.85,
    )


class FakeForecastRepository:
    def __init__(self):
        self.forecast = make_test_forecast()
        self.requested_product_id_for_list = None
        self.requested_product_id_for_latest = None

    def list_forecasts_for_product(
        self,
        product_id: UUID,
    ) -> list[Forecast]:
        self.requested_product_id_for_list = product_id

        if product_id == PRODUCT_WITH_FORECAST_ID:
            return [self.forecast]

        return []

    def get_latest_forecast_for_product(
        self,
        product_id: UUID,
    ) -> Forecast | None:
        self.requested_product_id_for_latest = product_id

        if product_id == PRODUCT_WITH_FORECAST_ID:
            return self.forecast

        return None


def test_forecast_service_lists_forecasts_for_product():
    repository = FakeForecastRepository()
    service = ForecastService(repository)

    forecasts = service.list_forecasts_for_product(PRODUCT_WITH_FORECAST_ID)

    assert len(forecasts) == 1
    assert all(isinstance(forecast, Forecast) for forecast in forecasts)
    assert repository.requested_product_id_for_list == PRODUCT_WITH_FORECAST_ID


def test_forecast_service_returns_empty_list_when_product_has_no_forecasts():
    repository = FakeForecastRepository()
    service = ForecastService(repository)

    forecasts = service.list_forecasts_for_product(PRODUCT_WITHOUT_FORECAST_ID)

    assert forecasts == []
    assert repository.requested_product_id_for_list == PRODUCT_WITHOUT_FORECAST_ID


def test_forecast_service_gets_latest_forecast_for_product():
    repository = FakeForecastRepository()
    service = ForecastService(repository)

    forecast = service.get_latest_forecast_for_product(PRODUCT_WITH_FORECAST_ID)

    assert isinstance(forecast, Forecast)
    assert repository.requested_product_id_for_latest == PRODUCT_WITH_FORECAST_ID


def test_forecast_service_returns_none_when_latest_forecast_is_missing():
    repository = FakeForecastRepository()
    service = ForecastService(repository)

    forecast = service.get_latest_forecast_for_product(
        PRODUCT_WITHOUT_FORECAST_ID
    )

    assert forecast is None
    assert repository.requested_product_id_for_latest == (
        PRODUCT_WITHOUT_FORECAST_ID
    )


def test_forecast_service_returns_available_when_forecast_exists():
    repository = FakeForecastRepository()
    service = ForecastService(repository)

    availability = service.get_forecast_availability_for_product(
        PRODUCT_WITH_FORECAST_ID
    )

    assert availability == FORECAST_AVAILABLE


def test_forecast_service_returns_missing_when_forecast_does_not_exist():
    repository = FakeForecastRepository()
    service = ForecastService(repository)

    availability = service.get_forecast_availability_for_product(
        PRODUCT_WITHOUT_FORECAST_ID
    )

    assert availability == FORECAST_MISSING
