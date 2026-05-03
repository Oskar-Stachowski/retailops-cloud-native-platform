from datetime import datetime
from uuid import UUID

from app.domain.models import Sale
from app.repositories.sales_repository import SalesRepository
from app.services.serialization import make_json_safe


class SalesService:
    """Application service for product-level sales reads."""

    def __init__(self, sales_repository: SalesRepository | None = None):
        self.sales_repository = sales_repository or SalesRepository()

    def list_sales(
        self,
        product_id: UUID | None = None,
        channel: str | None = None,
        currency: str | None = None,
        sold_from: datetime | None = None,
        sold_to: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "sold_at",
        sort_order: str = "desc",
    ) -> list[Sale]:
        return self.sales_repository.list_sales(
            product_id=product_id,
            channel=channel,
            currency=currency,
            sold_from=sold_from,
            sold_to=sold_to,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
        )

    def get_sale_by_id(self, sale_id: UUID) -> Sale | None:
        return self.sales_repository.get_sale_by_id(sale_id)

    def list_sales_response(
        self,
        product_id: UUID | None = None,
        channel: str | None = None,
        currency: str | None = None,
        sold_from: datetime | None = None,
        sold_to: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "sold_at",
        sort_order: str = "desc",
    ) -> dict:
        sales = self.sales_repository.list_sales(
            product_id=product_id,
            channel=channel,
            currency=currency,
            sold_from=sold_from,
            sold_to=sold_to,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        total = self.sales_repository.count_sales(
            product_id=product_id,
            channel=channel,
            currency=currency,
            sold_from=sold_from,
            sold_to=sold_to,
        )

        return {
            "items": [make_json_safe(sale.model_dump()) for sale in sales],
            "pagination": {
                "limit": limit,
                "offset": offset,
                "total": total,
            },
        }

    def get_sale_detail_response(self, sale_id: UUID) -> dict | None:
        sale = self.get_sale_by_id(sale_id)

        if sale is None:
            return None

        return make_json_safe(sale.model_dump())
