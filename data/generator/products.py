from __future__ import annotations

from data.generator.common import deterministic_uuid
from data.generator.scenarios import PRODUCT_BLUEPRINTS


def generate_products() -> list[dict[str, str]]:
    products: list[dict[str, str]] = []

    for item in PRODUCT_BLUEPRINTS:
        sku = str(item["sku"])
        products.append(
            {
                "id": deterministic_uuid("product", sku),
                "sku": sku,
                "name": str(item["name"]),
                "category": str(item["category"]),
                "brand": str(item["brand"]),
                "status": "active",
                "base_price": str(item["base_price"]),
                "normal_daily_sales": str(item["normal_daily_sales"]),
                "scenario": str(item["scenario"]),
            }
        )

    return products


def product_by_sku(products: list[dict[str, str]], sku: str) -> dict[str, str]:
    return next(product for product in products if product["sku"] == sku)
