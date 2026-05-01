from datetime import datetime, timezone
from uuid import UUID

from app.domain.models import Product
from app.services.product_service import ProductService


def make_test_product() -> Product:
    now = datetime.now(timezone.utc)

    return Product(
        id=UUID("85710dbe-1aea-50ac-a155-fb216e12ab97"),
        sku="ELEC-HEAD-001",
        name="Test Product",
        category="Electronics",
        brand="RetailOps",
        status="active",
        created_at=now,
        updated_at=now,
    )


class FakeProductRepository:
    def __init__(self):
        self.requested_sku = None
        self.product = make_test_product()

    def list_products(self) -> list[Product]:
        return [self.product]

    def get_product_by_id(self, product_id) -> Product | None:
        return self.product

    def get_product_by_sku(self, sku) -> Product | None:
        self.requested_sku = sku

        if sku == "ELEC-HEAD-001":
            return self.product

        return None


def test_product_service_lists_products():
    repository = FakeProductRepository()
    service = ProductService(repository)

    products = service.list_products()

    assert len(products) == 1
    assert all(isinstance(product, Product) for product in products)


def test_product_service_normalizes_sku_before_lookup():
    repository = FakeProductRepository()
    service = ProductService(repository)

    product = service.get_product_by_sku("  elec-head-001  ")

    assert isinstance(product, Product)
    assert repository.requested_sku == "ELEC-HEAD-001"


def test_product_service_returns_none_for_empty_sku():
    repository = FakeProductRepository()
    service = ProductService(repository)

    product = service.get_product_by_sku(" ")

    assert product is None
    assert repository.requested_sku is None
