from __future__ import annotations

from decimal import Decimal

from data.generator.common import deterministic_uuid, money, utc_datetime


def _warehouse_id_by_code(
    warehouses: list[dict[str, str]],
) -> dict[str, str]:
    return {warehouse["warehouse_code"]: warehouse["id"] for warehouse in warehouses}


def generate_stock_movements(
    inventory_snapshots: list[dict[str, str]],
    sales: list[dict[str, str]],
    warehouses: list[dict[str, str]],
) -> list[dict[str, str]]:
    warehouse_ids = _warehouse_id_by_code(warehouses)
    stock_movements: list[dict[str, str]] = []

    for snapshot in inventory_snapshots:
        warehouse_code = snapshot["warehouse_code"]
        natural_key = f"initial-{snapshot['product_id']}-{warehouse_code}"
        stock_movements.append(
            {
                "id": deterministic_uuid("stock_movement", natural_key),
                "product_id": snapshot["product_id"],
                "warehouse_id": warehouse_ids[warehouse_code],
                "warehouse_code": warehouse_code,
                "movement_type": "initial_stock",
                "quantity": snapshot["stock_quantity"],
                "unit_of_measure": snapshot["unit_of_measure"],
                "source_reference": snapshot["id"],
                "occurred_at": snapshot["recorded_at"],
                "created_at": snapshot["created_at"],
            },
        )

    warehouse_codes = list(warehouse_ids.keys())
    for index, sale in enumerate(sales):
        warehouse_code = warehouse_codes[index % len(warehouse_codes)]
        natural_key = f"sale-{sale['id']}"
        stock_movements.append(
            {
                "id": deterministic_uuid("stock_movement", natural_key),
                "product_id": sale["product_id"],
                "warehouse_id": warehouse_ids[warehouse_code],
                "warehouse_code": warehouse_code,
                "movement_type": "sale",
                "quantity": f"-{sale['quantity']}",
                "unit_of_measure": "pcs",
                "source_reference": sale["order_reference"],
                "occurred_at": sale["sold_at"],
                "created_at": sale["sold_at"],
            },
        )

    return stock_movements


def generate_returns(
    order_items: list[dict[str, str]],
    orders: list[dict[str, str]],
) -> list[dict[str, str]]:
    order_by_id = {order["id"]: order for order in orders}
    returns: list[dict[str, str]] = []

    for index, order_item in enumerate(order_items):
        if index % 5 != 0:
            continue

        order = order_by_id[order_item["order_id"]]
        returned_quantity = max(1, int(order_item["quantity"]) // 4)
        unit_price = Decimal(order_item["unit_price"])
        refund_amount = money(Decimal(returned_quantity) * unit_price)
        natural_key = f"{order['order_reference']}-{order_item['id']}"

        returns.append(
            {
                "id": deterministic_uuid("return", natural_key),
                "order_id": order["id"],
                "order_item_id": order_item["id"],
                "product_id": order_item["product_id"],
                "quantity": str(returned_quantity),
                "refund_amount": refund_amount,
                "currency": order_item["currency"],
                "reason": "customer_return",
                "status": "received",
                "returned_at": utc_datetime(
                    days_offset=1 + index % 3,
                    hours_offset=index,
                ),
            },
        )

    return returns
