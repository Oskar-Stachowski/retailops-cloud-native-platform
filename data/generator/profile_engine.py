from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from data.generator.common import (
    BASE_DATETIME,
    deterministic_uuid,
    money,
)
from data.generator.forecasts import generate_forecasts
from data.generator.orders import generate_order_items, generate_orders
from data.generator.pricing import generate_price_history, generate_promotions
from data.generator.stock import generate_returns, generate_stock_movements
from data.generator.users import generate_users


@dataclass(frozen=True)
class SyntheticProfileDefaults:
    days: int
    products: int
    stores: int
    warehouses: int


PROFILE_DEFAULTS: dict[str, SyntheticProfileDefaults] = {
    "small": SyntheticProfileDefaults(
        days=90,
        products=100,
        stores=5,
        warehouses=3,
    ),
    "medium": SyntheticProfileDefaults(
        days=180,
        products=500,
        stores=20,
        warehouses=6,
    ),
    "large": SyntheticProfileDefaults(
        days=365,
        products=1000,
        stores=50,
        warehouses=10,
    ),
}

CATEGORIES = [
    "Electronics",
    "Home Improvement",
    "Grocery",
    "Fashion",
    "Beauty",
    "Sports",
    "Toys",
    "Pet Care",
]
BRANDS = [
    "SoundWave",
    "NordicHome",
    "GreenFarm",
    "UrbanNorth",
    "SkinLab",
    "FitCore",
    "PlayBox",
    "HappyPaws",
]
SCENARIOS = ["normal", "sales_drop", "stockout_risk", "stale_inventory"]
CHANNELS = ["online", "store", "marketplace", "wholesale"]
REGIONS = ["PL-North", "PL-Central", "PL-South", "DE-East"]


def profile_defaults(profile: str) -> SyntheticProfileDefaults:
    return PROFILE_DEFAULTS[profile]


def generate_profile_products(product_count: int) -> list[dict[str, str]]:
    products: list[dict[str, str]] = []

    for index in range(product_count):
        category = CATEGORIES[index % len(CATEGORIES)]
        brand = BRANDS[index % len(BRANDS)]
        scenario = SCENARIOS[index % len(SCENARIOS)]
        sku = f"{category[:4].upper()}-{index + 1:06d}"
        base_price = Decimal("9.99") + Decimal(index % 300) * Decimal("1.75")
        normal_daily_sales = 5 + index % 95

        products.append(
            {
                "id": deterministic_uuid("product", sku),
                "sku": sku,
                "name": f"{category} Product {index + 1:06d}",
                "category": category,
                "brand": brand,
                "status": "active",
                "base_price": money(base_price),
                "normal_daily_sales": str(normal_daily_sales),
                "scenario": scenario,
            }
        )

    return products


def generate_profile_stores(store_count: int) -> list[dict[str, str]]:
    stores: list[dict[str, str]] = []

    for index in range(store_count):
        region = REGIONS[index % len(REGIONS)]
        channel = CHANNELS[index % len(CHANNELS)]
        store_code = f"STORE-{index + 1:04d}"
        stores.append(
            {
                "id": deterministic_uuid("store", store_code),
                "store_code": store_code,
                "name": f"RetailOps Store {index + 1:04d}",
                "region": region,
                "country": region.split("-")[0],
                "city": f"City {index + 1:04d}",
                "channel": channel,
                "status": "active",
            }
        )

    return stores


def generate_profile_warehouses(
    warehouse_count: int,
) -> list[dict[str, str]]:
    warehouses: list[dict[str, str]] = []

    for index in range(warehouse_count):
        region = REGIONS[index % len(REGIONS)]
        warehouse_code = f"WH-{index + 1:04d}"
        warehouses.append(
            {
                "id": deterministic_uuid("warehouse", warehouse_code),
                "warehouse_code": warehouse_code,
                "name": f"RetailOps Warehouse {index + 1:04d}",
                "region": region,
                "country": region.split("-")[0],
                "city": f"Warehouse City {index + 1:04d}",
                "status": "active",
            }
        )

    return warehouses


def _date_at_offset(days_back: int, hours: int = 0) -> str:
    return (BASE_DATETIME - timedelta(days=days_back) + timedelta(hours=hours)).isoformat()


def generate_profile_sales(
    products: list[dict[str, str]],
    stores: list[dict[str, str]],
    days: int,
) -> list[dict[str, str]]:
    sales: list[dict[str, str]] = []

    for day_index in range(days):
        weekend_multiplier = (
            Decimal("1.15") if day_index % 7 in (5, 6) else Decimal("1.00")
        )

        for product_index, product in enumerate(products):
            store = stores[(product_index + day_index) % len(stores)]
            normal_daily_sales = Decimal(product["normal_daily_sales"])
            scenario = product["scenario"]
            scenario_multiplier = Decimal("1.00")

            if scenario == "sales_drop" and day_index < 14:
                scenario_multiplier = Decimal("0.35")
            elif scenario == "stockout_risk" and day_index < 10:
                scenario_multiplier = Decimal("1.45")
            elif scenario == "stale_inventory":
                scenario_multiplier = Decimal("0.60")

            quantity = max(
                1,
                int(
                    normal_daily_sales
                    * weekend_multiplier
                    * scenario_multiplier
                ),
            )
            price_multiplier = (
                Decimal("0.97") if day_index % 11 == 0 else Decimal("1.00")
            )
            unit_price = money(Decimal(product["base_price"]) * price_multiplier)
            total_amount = money(Decimal(quantity) * Decimal(unit_price))
            order_reference = f"ORD-{product['sku']}-{day_index + 1:04d}"

            sales.append(
                {
                    "id": deterministic_uuid("sale", order_reference),
                    "product_id": product["id"],
                    "quantity": str(quantity),
                    "unit_price": unit_price,
                    "total_amount": total_amount,
                    "currency": "PLN",
                    "channel": store["channel"],
                    "region": store["region"],
                    "sold_at": _date_at_offset(day_index, product_index % 12),
                    "order_reference": order_reference,
                }
            )

    return sales


def generate_profile_inventory_snapshots(
    products: list[dict[str, str]],
    warehouses: list[dict[str, str]],
    days: int,
) -> list[dict[str, str]]:
    snapshots: list[dict[str, str]] = []

    for day_index in range(days):
        if day_index % 7 != 0 and day_index != 0:
            continue

        for product_index, product in enumerate(products):
            warehouse = warehouses[
                (product_index + day_index) % len(warehouses)
            ]
            normal_daily_sales = int(product["normal_daily_sales"])
            stock_quantity = max(
                0,
                normal_daily_sales * (7 + product_index % 21) - day_index,
            )
            natural_key = (
                f"{product['sku']}-{warehouse['warehouse_code']}-{day_index}"
            )
            recorded_at = _date_at_offset(day_index, product_index % 8)

            snapshots.append(
                {
                    "id": deterministic_uuid(
                        "inventory_snapshot",
                        natural_key,
                    ),
                    "product_id": product["id"],
                    "stock_quantity": str(stock_quantity),
                    "unit_of_measure": "pcs",
                    "warehouse_code": warehouse["warehouse_code"],
                    "recorded_at": recorded_at,
                    "ingested_at": recorded_at,
                    "created_at": recorded_at,
                }
            )

    return snapshots


def generate_profile_incident_dataset(
    products: list[dict[str, str]],
    users: list[dict[str, str]],
) -> dict[str, list[dict[str, str]]]:
    anomalies: list[dict[str, str]] = []
    alerts: list[dict[str, str]] = []
    recommendations: list[dict[str, str]] = []
    workflow_actions: list[dict[str, str]] = []
    incident_products = products[: min(20, len(products))]
    assigned_user = users[0]
    actor = users[-1]

    for index, product in enumerate(incident_products):
        anomaly_type = "sales_drop" if index % 2 == 0 else "stale_inventory"
        alert_type = "sales_drop" if anomaly_type == "sales_drop" else "overstock_risk"
        severity = ["medium", "high", "critical"][index % 3]
        actual_value = Decimal(20 + index)
        expected_value = Decimal(60 + index)
        deviation = ((actual_value - expected_value) / expected_value) * 100
        anomaly_id = deterministic_uuid("anomaly", product["sku"])
        alert_id = deterministic_uuid("alert", product["sku"])
        recommendation_id = deterministic_uuid("recommendation", product["sku"])
        workflow_action_id = deterministic_uuid(
            "workflow_action",
            product["sku"],
        )
        detected_at = _date_at_offset(index, 2)

        anomalies.append(
            {
                "id": anomaly_id,
                "product_id": product["id"],
                "anomaly_type": anomaly_type,
                "metric_name": "units_sold",
                "actual_value": money(actual_value),
                "expected_value": money(expected_value),
                "deviation_percent": money(deviation),
                "impact_value": money(actual_value - expected_value),
                "impact_unit": "pcs",
                "severity": severity,
                "period_start": _date_at_offset(index + 1),
                "period_end": detected_at,
                "detected_at": detected_at,
            }
        )
        alerts.append(
            {
                "id": alert_id,
                "product_id": product["id"],
                "anomaly_id": anomaly_id,
                "assigned_to_user_id": assigned_user["id"],
                "alert_type": alert_type,
                "severity": severity,
                "status": "open",
                "title": f"{alert_type} for {product['sku']}",
                "recommended_action": "Review synthetic retail signal.",
                "created_at": detected_at,
                "updated_at": detected_at,
            }
        )
        recommendations.append(
            {
                "id": recommendation_id,
                "product_id": product["id"],
                "forecast_id": "",
                "anomaly_id": anomaly_id,
                "alert_id": alert_id,
                "recommendation_type": "investigate_sales_drop"
                if anomaly_type == "sales_drop"
                else "review_stock",
                "recommended_action": "Review product performance.",
                "rationale": "Synthetic profile anomaly rule.",
                "status": "proposed",
                "generated_at": detected_at,
                "expires_at": "",
                "created_at": detected_at,
            }
        )
        workflow_actions.append(
            {
                "id": workflow_action_id,
                "alert_id": alert_id,
                "performed_by_user_id": actor["id"],
                "action_type": "acknowledge",
                "comment": "Synthetic workflow action.",
                "previous_status": "",
                "new_status": "acknowledged",
                "performed_at": detected_at,
                "created_at": detected_at,
            }
        )

    return {
        "anomalies": anomalies,
        "alerts": alerts,
        "recommendations": recommendations,
        "workflow_actions": workflow_actions,
    }


def build_profile_dataset(
    profile: str,
    days: int,
    product_count: int,
    store_count: int,
    warehouse_count: int,
) -> dict[str, list[dict[str, str]]]:
    products = generate_profile_products(product_count)
    users = generate_users()
    stores = generate_profile_stores(store_count)
    warehouses = generate_profile_warehouses(warehouse_count)
    sales = generate_profile_sales(products, stores, days)
    orders = generate_orders(sales, stores)
    order_items = generate_order_items(sales, orders)
    price_history = generate_price_history(products)
    promotions = generate_promotions(products)
    inventory_snapshots = generate_profile_inventory_snapshots(
        products,
        warehouses,
        days,
    )
    stock_movements = generate_stock_movements(
        inventory_snapshots,
        sales,
        warehouses,
    )
    returns = generate_returns(order_items, orders)
    forecasts = generate_forecasts(products)
    incidents = generate_profile_incident_dataset(products, users)

    return {
        "products": products,
        "users": users,
        "stores": stores,
        "warehouses": warehouses,
        "orders": orders,
        "order_items": order_items,
        "price_history": price_history,
        "promotions": promotions,
        "stock_movements": stock_movements,
        "returns": returns,
        "sales": sales,
        "inventory_snapshots": inventory_snapshots,
        "forecasts": forecasts,
        **incidents,
    }
