from __future__ import annotations

from data.generator.common import deterministic_uuid, utc_datetime
from data.generator.scenarios import WAREHOUSES, UNIT_OF_MEASURE


def _inventory_values(product: dict[str, str]) -> tuple[int, int, int, int]:
    normal_daily_sales = int(product["normal_daily_sales"])
    scenario = product["scenario"]

    reorder_point = max(8, normal_daily_sales * 2)
    safety_stock = max(4, normal_daily_sales)

    if scenario == "stockout_risk":
        on_hand = max(1, int(reorder_point * 0.18))
        return on_hand, 0, reorder_point, safety_stock

    if scenario == "stale_inventory":
        on_hand = int(reorder_point * 9)
        reserved = int(reorder_point * 0.05)
        return on_hand, reserved, reorder_point, safety_stock

    if scenario == "sales_drop":
        on_hand = int(reorder_point * 3)
        reserved = int(reorder_point * 0.2)
        return on_hand, reserved, reorder_point, safety_stock

    on_hand = int(reorder_point * 2.2)
    reserved = int(reorder_point * 0.15)
    return on_hand, reserved, reorder_point, safety_stock


def generate_inventory_snapshots(
    products: list[dict[str, str]],
) -> list[dict[str, str]]:
    snapshots: list[dict[str, str]] = []

    for index, product in enumerate(products):
        values = _inventory_values(product)
        on_hand, reserved, reorder_point, safety_stock = values
        warehouse = WAREHOUSES[index % len(WAREHOUSES)]
        unit_of_measure = UNIT_OF_MEASURE[index % len(UNIT_OF_MEASURE)]
        natural_key = f"{product['sku']}-{warehouse}"

        recorded_at = utc_datetime(hours_offset=-index),
        ingested_at = utc_datetime(
            hours_offset=-index,
            minutes_offset=3,
        ),
        created_at = utc_datetime(
            hours_offset=index,
            minutes_offset=5,
        ),

        snapshots.append(
            {
                "id": deterministic_uuid("inventory_snapshot", natural_key),
                "product_id": product["id"],
                "stock_quantity": str(on_hand),
                # "reversed_quantity": str(reversed),
                "unit_of_measure": unit_of_measure,
                "warehouse_code": warehouse,
                # "reorder_point": str(reorder_point),
                # "safety_stock_quantity": str(safety_stock),
                "recorded_at": recorded_at,
                "ingested_at": ingested_at,
                "created_at": created_at,
            }
        )

    return snapshots
