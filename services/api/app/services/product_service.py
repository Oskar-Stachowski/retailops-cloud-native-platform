from uuid import UUID

from app.domain.models import Product
from app.repositories.product_repository import ProductRepository


class ProductService:
    def __init__(self, product_repository: ProductRepository):
        self.product_repository = product_repository

    def list_products(self) -> list[Product]:
        return self.product_repository.list_products()

    def get_product_by_id(self, product_id: UUID) -> Product | None:
        return self.product_repository.get_product_by_id(product_id)

    def get_product_by_sku(self, sku: str) -> Product | None:
        normalized_sku = sku.strip().upper()

        if not normalized_sku:
            return None

        return self.product_repository.get_product_by_sku(normalized_sku)
