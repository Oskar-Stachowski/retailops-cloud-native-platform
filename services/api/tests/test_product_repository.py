import os
from uuid import UUID

import psycopg
import pytest

from app.domain.models import Product
from app.repositories.product_repository import ProductRepository

DATABASE_URL = os.getenv("DATABASE_URL")
pytestmark = pytest.mark.integration_db

EXISTING_ID = UUID("85710dbe-1aea-50ac-a155-fb216e12ab97")
NON_EXISTING_ID = UUID("00000000-0000-0000-0000-000000000000")

EXISTING_SKU = "ELEC-HEAD-001"
NON_EXISTING_SKU = "DOES-NOT-EXIST"


def test_product_repository_lists_seeded_products():
    assert DATABASE_URL is not None

    with psycopg.connect(DATABASE_URL) as conn:
        repository = ProductRepository(conn)
        products = repository.list_products()

    assert len(products) == 8
    assert all(isinstance(product, Product) for product in products)


def test_product_repository_gets_product_by_id():
    assert DATABASE_URL is not None

    with psycopg.connect(DATABASE_URL) as conn:
        repository = ProductRepository(conn)
        existing_product = repository.get_product_by_id(EXISTING_ID)
        missing_product = repository.get_product_by_id(NON_EXISTING_ID)

    assert isinstance(existing_product, Product)
    assert missing_product is None


def test_product_repository_gets_product_by_sku():
    assert DATABASE_URL is not None

    with psycopg.connect(DATABASE_URL) as conn:
        repository = ProductRepository(conn)

        existing_product = repository.get_product_by_sku(EXISTING_SKU)
        missing_product = repository.get_product_by_sku(NON_EXISTING_SKU)

    assert isinstance(existing_product, Product)
    assert missing_product is None
