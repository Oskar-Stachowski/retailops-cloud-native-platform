from app.repositories.stock_risk_repository import StockRiskRepository
from app.services.serialization import make_json_safe


class StockRiskService:
    """Application service for product-level stock risk reads."""

    def __init__(self, stock_risk_repository: StockRiskRepository | None = None):
        self.stock_risk_repository = stock_risk_repository or StockRiskRepository()

    def list_inventory_risks_response(
        self,
        risk_status: str | None = None,
        category: str | None = None,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "risk_status",
        sort_order: str = "asc",
    ) -> dict:
        items = self.stock_risk_repository.list_inventory_risks(
            risk_status=risk_status,
            category=category,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        total = self.stock_risk_repository.count_inventory_risks(
            risk_status=risk_status,
            category=category,
        )

        return make_json_safe(
            {
                "items": items,
                "pagination": {
                    "limit": limit,
                    "offset": offset,
                    "total": total,
                },
            }
        )
