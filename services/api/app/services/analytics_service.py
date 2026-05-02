"""Service layer for read-only analytics endpoints."""

from app.repositories.analytics_repository import AnalyticsRepository
from app.services.serialization import make_json_safe


class AnalyticsService:
    def __init__(self, repository: AnalyticsRepository | None = None) -> None:
        self.repository = repository or AnalyticsRepository()

    def get_product_performance(self, limit: int = 50) -> dict:
        safe_limit = min(max(limit, 1), 200)
        items = self.repository.get_product_performance(limit=safe_limit)
        return make_json_safe({"items": items, "limit": safe_limit})

    def get_inventory_risk(self, limit: int = 50) -> dict:
        safe_limit = min(max(limit, 1), 200)
        items = self.repository.get_inventory_risk(limit=safe_limit)
        return make_json_safe({"items": items, "limit": safe_limit})


analytics_service = AnalyticsService()
