from __future__ import annotations

from data.generator.common import deterministic_uuid


def _store_for_sale(
    sale: dict[str, str],
    stores: list[dict[str, str]],
) -> dict[str, str]:
    matching_stores = [
        store
        for store in stores
        if store["region"] == sale["region"]
        and store["channel"] == sale["channel"]
    ]
    if matching_stores:
        return matching_stores[0]

    region_stores = [
        store for store in stores if store["region"] == sale["region"]
    ]
    if region_stores:
        return region_stores[0]

    return stores[0]


def generate_orders(
    sales: list[dict[str, str]],
    stores: list[dict[str, str]],
) -> list[dict[str, str]]:
    orders: list[dict[str, str]] = []

    for sale in sales:
        order_reference = sale["order_reference"]
        store = _store_for_sale(sale, stores)
        orders.append(
            {
                "id": deterministic_uuid("order", order_reference),
                "order_reference": order_reference,
                "store_id": store["id"],
                "channel": sale["channel"],
                "region": sale["region"],
                "status": "completed",
                "order_total": sale["total_amount"],
                "currency": sale["currency"],
                "ordered_at": sale["sold_at"],
                "created_at": sale["sold_at"],
            }
        )

    return orders


def generate_order_items(
    sales: list[dict[str, str]],
    orders: list[dict[str, str]],
) -> list[dict[str, str]]:
    order_by_reference = {
        order["order_reference"]: order for order in orders
    }
    order_items: list[dict[str, str]] = []

    for sale in sales:
        order = order_by_reference[sale["order_reference"]]
        item_key = f"{sale['order_reference']}-{sale['product_id']}"
        order_items.append(
            {
                "id": deterministic_uuid("order_item", item_key),
                "order_id": order["id"],
                "product_id": sale["product_id"],
                "quantity": sale["quantity"],
                "unit_price": sale["unit_price"],
                "total_amount": sale["total_amount"],
                "currency": sale["currency"],
            }
        )

    return order_items
