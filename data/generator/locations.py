from __future__ import annotations

from data.generator.common import deterministic_uuid
from data.generator.scenarios import STORE_BLUEPRINTS, WAREHOUSE_BLUEPRINTS


def generate_stores() -> list[dict[str, str]]:
    stores: list[dict[str, str]] = []

    for item in STORE_BLUEPRINTS:
        store_code = str(item["store_code"])
        stores.append(
            {
                "id": deterministic_uuid("store", store_code),
                "store_code": store_code,
                "name": str(item["name"]),
                "region": str(item["region"]),
                "country": str(item["country"]),
                "city": str(item["city"]),
                "channel": str(item["channel"]),
                "status": "active",
            },
        )

    return stores


def generate_warehouses() -> list[dict[str, str]]:
    warehouses: list[dict[str, str]] = []

    for item in WAREHOUSE_BLUEPRINTS:
        warehouse_code = str(item["warehouse_code"])
        warehouses.append(
            {
                "id": deterministic_uuid("warehouse", warehouse_code),
                "warehouse_code": warehouse_code,
                "name": str(item["name"]),
                "region": str(item["region"]),
                "country": str(item["country"]),
                "city": str(item["city"]),
                "status": "active",
            },
        )

    return warehouses
