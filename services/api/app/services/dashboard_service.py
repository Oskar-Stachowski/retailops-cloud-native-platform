"""Service layer for dashboard read models.

The service keeps FastAPI handlers thin and gives us one place for response
normalization, small business defaults, and future observability hooks.
"""

from app.repositories.dashboard_repository import DashboardRepository
from app.services.serialization import make_json_safe


class DashboardService:
    def __init__(self, repository: DashboardRepository | None = None) -> None:
        self.repository = repository or DashboardRepository()

    def get_summary(self) -> dict:
        summary = self.repository.get_summary()
        return make_json_safe({"summary": summary})

    def get_sales_trend(self, days: int = 14) -> dict:
        safe_days = min(max(days, 1), 90)
        items = self.repository.get_sales_trend(days=safe_days)
        return make_json_safe({"items": items, "days": safe_days})

    def get_open_alerts(self, limit: int = 10) -> dict:
        safe_limit = min(max(limit, 1), 100)
        items = self.repository.get_open_alerts(limit=safe_limit)
        return make_json_safe({"items": items, "limit": safe_limit})

    def get_top_recommendations(self, limit: int = 10) -> dict:
        safe_limit = min(max(limit, 1), 100)
        items = self.repository.get_top_recommendations(limit=safe_limit)
        return make_json_safe({"items": items, "limit": safe_limit})


dashboard_service = DashboardService()
