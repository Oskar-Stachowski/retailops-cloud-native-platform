from __future__ import annotations

from data.generator.common import deterministic_uuid, money, utc_datetime
from data.generator.scenarios import CHANNELS, REGIONS


def _quantity_for(product: dict[str, str], sale_index: int) -> int:
    normal_daily_sales = int(product["normal_daily_sales"])
    scenario = product["scenario"]

    if scenario == "sales_drop":
        multiplier = 0.18 if sale_index == 0 else 0.12
        return max(1, int(normal_daily_sales * multiplier))

    if scenario == "stockout_risk":
        multiplier = 1.55 if sale_index == 0 else 1.35
        return int(normal_daily_sales * multiplier)

    if scenario == "stale_inventory":
        multiplier = 0.35 if sale_index == 0 else 0.25
        return max(1, int(normal_daily_sales * multiplier))

    multiplier = 1.05 if sale_index == 0 else 0.85
    return int(normal_daily_sales * multiplier)


def generate_sales(products: list[dict[str, str]]) -> list[dict[str, str]]:
    sales: list[dict[str, str]] = []

    for product_index, product in enumerate(products):
        base_price = float(product["base_price"])

        for sale_index in range(2):
            natural_key = f"{product['sku']}-{sale_index + 1}"
            channel = CHANNELS[(product_index + sale_index) % len(CHANNELS)]
            region_index = (product_index * 2 + sale_index) % len(REGIONS)
            region = REGIONS[region_index]
            quantity = _quantity_for(product, sale_index)
            price_multiplier = 0.97 if sale_index == 1 else 1.0
            sold_at = utc_datetime(
                days_offset=-(sale_index + product_index % 3),
                hours_offset=sale_index * 4,
            )
            total_amount = quantity * base_price * price_multiplier

            sales.append(
                {
                    "id": deterministic_uuid("sale", natural_key),
                    "product_id": product["id"],
                    "quantity": str(quantity),
                    "unit_price": money(base_price * price_multiplier),
                    "total_amount": str(total_amount),
                    "currency": "PLN",
                    "channel": channel,
                    "region": region,
                    "sold_at": sold_at,
                    "order_reference": (
                        f"ORD-{product['sku']}-{sale_index + 1:03d}"
                    ),
                }
            )

    return sales
