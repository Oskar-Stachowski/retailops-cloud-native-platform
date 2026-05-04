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
    assert "sales_count" in summary
    assert "inventory_snapshots_count" in summary
    assert "forecasts_count" in summary
    assert "anomalies_count" in summary
    assert "recommendations_count" in summary
    assert "open_anomalies_count" in summary
    assert "open_recommendations_count" in summary
    assert "open_work_items_count" in summary
    assert "last_refresh_at" in summary

    assert isinstance(summary["products_count"], int)
    assert isinstance(summary["sales_count"], int)
    assert isinstance(summary["inventory_snapshots_count"], int)
    assert isinstance(summary["forecasts_count"], int)
    assert isinstance(summary["anomalies_count"], int)
    assert isinstance(summary["recommendations_count"], int)
    assert isinstance(summary["open_anomalies_count"], int)
    assert isinstance(summary["open_recommendations_count"], int)
    assert isinstance(summary["open_work_items_count"], int)


def test_dashboard_repository_reads_sales_trend_from_database():
    repository = DashboardRepository()

    trend = repository.get_sales_trend(days=14)

    assert isinstance(trend, list)

    if trend:
        assert "date" in trend[0]
        assert "units_sold" in trend[0]
        assert "revenue" in trend[0]


def test_dashboard_repository_reads_open_alerts_from_database():
    repository = DashboardRepository()

    items = repository.get_open_alerts(limit=10)

    assert isinstance(items, list)
    assert len(items) <= 10

    if items:
        assert "source" in items[0]
        assert items[0]["source"] == "anomaly"


def test_dashboard_repository_reads_top_recommendations_from_database():
    repository = DashboardRepository()

    items = repository.get_top_recommendations(limit=10)

    assert isinstance(items, list)
    assert len(items) <= 10

    if items:
        assert "source" in items[0]
        assert items[0]["source"] == "recommendation"


def test_dashboard_repository_reads_open_work_items_from_database():
    repository = DashboardRepository()

    items = repository.get_open_work_items(limit=10)

    assert isinstance(items, list)
    assert len(items) <= 10

    if items:
        assert "source" in items[0]
        assert items[0]["source"] in {"anomaly", "recommendation"}


def test_dashboard_repository_reads_stock_risk_summary_from_database():
    repository = DashboardRepository()

    summary = repository.get_stock_risk_summary()

    assert "total_risk_items" in summary
    assert "normal_count" in summary
    assert "stockout_risk_count" in summary
    assert "overstock_risk_count" in summary
    assert "unknown_count" in summary

    assert isinstance(summary["total_risk_items"], int)
    assert isinstance(summary["normal_count"], int)
    assert isinstance(summary["stockout_risk_count"], int)
    assert isinstance(summary["overstock_risk_count"], int)
    assert isinstance(summary["unknown_count"], int)


def test_analytics_repository_reads_inventory_risk_from_database():
    repository = AnalyticsRepository()

    items = repository.get_inventory_risk(limit=10)

    assert isinstance(items, list)
    assert len(items) <= 10

    if items:
        assert "risk_status" in items[0]
        assert items[0]["risk_status"] in {
            "normal",
            "stockout_risk",
            "overstock_risk",
            "unknown",
        }
