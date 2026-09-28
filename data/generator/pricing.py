from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from data.generator.common import BASE_DATE, deterministic_uuid, money


def _discount_for(product: dict[str, str], index: int) -> Decimal:
    scenario = product["scenario"]

    if scenario == "sales_drop":
        return Decimal("0.12")

    if scenario == "stockout_risk":
        return Decimal("0.05")

    if scenario == "stale_inventory":
        return Decimal("0.18")

    return Decimal("0.08") if index % 2 == 0 else Decimal("0.10")


def generate_price_history(
    products: list[dict[str, str]],
    base_date: date = BASE_DATE,
) -> list[dict[str, str]]:
    price_history: list[dict[str, str]] = []

    for index, product in enumerate(products):
        base_price = Decimal(product["base_price"])
        previous_price = money(base_price * Decimal("0.94"))
        current_price = money(base_price)
        future_price = money(base_price * Decimal("1.03"))

        price_points = [
            ("previous", previous_price, -60, -31),
            ("current", current_price, -30, 30),
            ("planned", future_price, 31, None),
        ]

        for version, price, valid_from_offset, valid_to_offset in price_points:
            natural_key = f"{product['sku']}-{version}"
            price_history.append(
                {
                    "id": deterministic_uuid("price_history", natural_key),
                    "product_id": product["id"],
                    "price": price,
                    "currency": "PLN",
                    "valid_from": (base_date + timedelta(days=valid_from_offset)).isoformat(),
                    "valid_to": (
                        (base_date + timedelta(days=valid_to_offset)).isoformat()
                        if valid_to_offset is not None
                        else ""
                    ),
                    "price_type": ("regular" if version != "planned" else "planned"),
                    "source": "synthetic_pricing_rules",
                    "created_at": (base_date - timedelta(days=index + 1)).isoformat(),
                },
            )

    return price_history


def generate_promotions(
    products: list[dict[str, str]],
    base_date: date = BASE_DATE,
) -> list[dict[str, str]]:
    promotions: list[dict[str, str]] = []

    for index, product in enumerate(products):
        discount_percent = _discount_for(product, index)
        natural_key = f"{product['sku']}-promo"
        promotions.append(
            {
                "id": deterministic_uuid("promotion", natural_key),
                "promotion_code": f"PROMO-{product['sku']}",
                "product_id": product["id"],
                "name": f"Synthetic promotion for {product['sku']}",
                "promotion_type": "discount",
                "discount_percent": money(discount_percent * Decimal(100)),
                "starts_at": (base_date + timedelta(days=-14 + index % 4)).isoformat(),
                "ends_at": (base_date + timedelta(days=14 + index % 4)).isoformat(),
                "channel": "all",
                "status": "active",
            },
        )

    return promotions
