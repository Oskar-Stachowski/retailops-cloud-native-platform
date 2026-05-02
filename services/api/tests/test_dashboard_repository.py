import os

import pytest

from app.repositories.analytics_repository import AnalyticsRepository
from app.repositories.dashboard_repository import DashboardRepository

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL is required for repository integration smoke tests",
)


def test_dashboard_repository_reads_summary_from_database():
    repository = DashboardRepository()

    summary = repository.get_summary()

    assert "products_count" in summary
    assert "forecasts_count" in summary
    assert "open_work_items_count" in summary
    assert isinstance(summary["products_count"], int)


def test_dashboard_repository_reads_sales_trend_from_database():
    repository = DashboardRepository()

    trend = repository.get_sales_trend(days=14)

    assert isinstance(trend, list)
    if trend:
        assert "date" in trend[0]
        assert "units_sold" in trend[0]
        assert "revenue" in trend[0]


def test_analytics_repository_reads_inventory_risk_from_database():
    repository = AnalyticsRepository()

    items = repository.get_inventory_risk(limit=10)

    assert isinstance(items, list)
    if items:
        assert "risk_status" in items[0]
        assert items[0]["risk_status"] in {
            "normal",
            "stockout_risk",
            "overstock_risk",
            "unknown",
        }
