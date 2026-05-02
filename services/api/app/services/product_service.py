from uuid import UUID

from app.domain.models import Product
from app.repositories.product_repository import ProductRepository
from app.services.serialization import make_json_safe


class ProductService:
    """Application service for product reads.

    Existing domain-oriented methods still return Product models. New API
    contract methods return JSON-safe dictionaries with stable list/detail
    response shapes.
    """

    def __init__(self, product_repository: ProductRepository | None = None):
        self.product_repository = product_repository or ProductRepository()

    def list_products(self) -> list[Product]:
        return self.product_repository.list_products()

    def get_product_by_id(self, product_id: UUID) -> Product | None:
        return self.product_repository.get_product_by_id(product_id)

    def get_product_by_sku(self, sku: str) -> Product | None:
        normalized_sku = sku.strip().upper()

        if not normalized_sku:
            return None

        return self.product_repository.get_product_by_sku(normalized_sku)

    def list_products_response(
        self,
        category: str | None = None,
        status: str | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "sku",
        sort_order: str = "asc",
    ) -> dict:
        products = self.product_repository.list_products(
            category=category,
            status=status,
            search=search,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        total = self.product_repository.count_products(
            category=category,
            status=status,
            search=search,
        )

        return {
            "items": [
                make_json_safe(product.model_dump())
                for product in products
            ],
            "pagination": {
                "limit": limit,
                "offset": offset,
                "total": total,
            },
        }

    def get_product_detail_response(self, product_id: UUID) -> dict | None:
        product = self.get_product_by_id(product_id)

        if product is None:
            return None

        return make_json_safe(product.model_dump())
