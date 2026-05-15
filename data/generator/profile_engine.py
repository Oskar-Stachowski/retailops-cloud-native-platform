from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from data.generator.common import BASE_DATETIME, deterministic_uuid, money
from data.generator.pricing import generate_price_history, generate_promotions
from data.generator.users import generate_users


@dataclass(frozen=True)
class SyntheticProfileDefaults:
    days: int
    products: int
    stores: int
    warehouses: int


@dataclass(frozen=True)
class ProductRealism:
    demand_class: str
    demand_weight: Decimal
    price_elasticity: Decimal
    seasonal_pattern: str
    return_rate: Decimal


PROFILE_DEFAULTS: dict[str, SyntheticProfileDefaults] = {
    "small": SyntheticProfileDefaults(days=90, products=100, stores=5, warehouses=3),
    "medium": SyntheticProfileDefaults(days=180, products=500, stores=20, warehouses=6),
    "large": SyntheticProfileDefaults(days=365, products=1000, stores=50, warehouses=10),
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
CHANNELS = ["online", "store", "marketplace", "wholesale"]
REGIONS = ["PL-North", "PL-Central", "PL-South", "DE-East"]

CATEGORY_ELASTICITY = {
    "Electronics": Decimal("1.15"),
    "Home Improvement": Decimal("0.80"),
    "Grocery": Decimal("0.35"),
    "Fashion": Decimal("1.35"),
    "Beauty": Decimal("0.70"),
    "Sports": Decimal("0.95"),
    "Toys": Decimal("1.05"),
    "Pet Care": Decimal("0.45"),
}
CATEGORY_RETURN_RATE = {
    "Electronics": Decimal("0.12"),
    "Home Improvement": Decimal("0.14"),
    "Grocery": Decimal("0.01"),
    "Fashion": Decimal("0.34"),
    "Beauty": Decimal("0.08"),
    "Sports": Decimal("0.11"),
    "Toys": Decimal("0.09"),
    "Pet Care": Decimal("0.02"),
}
CATEGORY_PROMO_UPLIFT = {
    "Electronics": Decimal("1.25"),
    "Home Improvement": Decimal("1.18"),
    "Grocery": Decimal("1.14"),
    "Fashion": Decimal("1.45"),
    "Beauty": Decimal("1.20"),
    "Sports": Decimal("1.22"),
    "Toys": Decimal("1.32"),
    "Pet Care": Decimal("1.10"),
}
COMPLEMENTARY_CATEGORY = {
    "Electronics": "Electronics",
    "Home Improvement": "Home Improvement",
    "Grocery": "Pet Care",
    "Fashion": "Beauty",
    "Beauty": "Fashion",
    "Sports": "Sports",
    "Toys": "Toys",
    "Pet Care": "Grocery",
}

DEMAND_CLASS_PERCENTILES = (
    (Decimal("0.08"), "hero_product"),
    (Decimal("0.25"), "core_product"),
    (Decimal("0.45"), "seasonal"),
    (Decimal("0.60"), "new_product"),
    (Decimal("0.75"), "declining_product"),
    (Decimal("0.85"), "clearance_product"),
)
HOLIDAY_PEAK_START_DAY = 315
SPRING_SUMMER_PEAK_START_DAY = 90
SPRING_SUMMER_PEAK_END_DAY = 220
PROMO_START_DAY = 10
PROMO_END_DAY = 24
POST_PROMO_DIP_START_DAY = 25
POST_PROMO_DIP_END_DAY = 28
PRE_PROMO_SOFTENING_START_DAY = 7
PRE_PROMO_SOFTENING_END_DAY = 9
DATA_QUALITY_DUPLICATE_THRESHOLD = 0.006
DATA_QUALITY_LATE_EVENT_THRESHOLD = 0.018
DATA_QUALITY_MISSING_CONTEXT_THRESHOLD = 0.026
BASKET_SIZE_ROLL_THRESHOLDS = {
    "wholesale": (0.65,),
    "online": (0.35, 0.82),
    "marketplace": (0.55,),
    "store": (0.70,),
}


def profile_defaults(profile: str) -> SyntheticProfileDefaults:
    return PROFILE_DEFAULTS[profile]


def _date_at_offset(days_back: int, hours: int = 0) -> str:
    return (BASE_DATETIME - timedelta(days=days_back) + timedelta(hours=hours)).isoformat()


def _date_only_at_offset(days_back: int) -> str:
    return (BASE_DATETIME.date() - timedelta(days=days_back)).isoformat()


def _rng(seed: int, profile: str) -> random.Random:
    return random.Random(f"retailops-{profile}-{seed}")  # noqa: S311 - deterministic demo data


def _demand_class(index: int, product_count: int) -> str:
    percentile = Decimal(index + 1) / Decimal(max(product_count, 1))
    for threshold, demand_class in DEMAND_CLASS_PERCENTILES:
        if percentile <= threshold:
            return demand_class
    return "long_tail"


def _demand_weight(demand_class: str, rng: random.Random) -> Decimal:
    ranges = {
        "hero_product": (Decimal("2.8"), Decimal("5.2")),
        "core_product": (Decimal("1.5"), Decimal("3.0")),
        "seasonal": (Decimal("0.9"), Decimal("2.2")),
        "new_product": (Decimal("0.6"), Decimal("1.8")),
        "declining_product": (Decimal("0.6"), Decimal("1.4")),
        "clearance_product": (Decimal("0.5"), Decimal("1.2")),
        "long_tail": (Decimal("0.18"), Decimal("0.75")),
    }
    low, high = ranges[demand_class]
    return low + (high - low) * Decimal(str(rng.random()))


def _seasonal_pattern(category: str, demand_class: str) -> str:
    if demand_class == "seasonal":
        return "seasonal_peak"
    if category in {"Fashion", "Toys"}:
        return "holiday_peak"
    if category in {"Sports", "Home Improvement"}:
        return "spring_summer_peak"
    if category == "Grocery":
        return "stable"
    return "weekly_sensitive"


def _base_daily_sales(demand_class: str, demand_weight: Decimal) -> int:
    base_by_class = {
        "hero_product": Decimal("64"),
        "core_product": Decimal("42"),
        "seasonal": Decimal("24"),
        "new_product": Decimal("16"),
        "declining_product": Decimal("18"),
        "clearance_product": Decimal("15"),
        "long_tail": Decimal("10"),
    }
    return max(1, int(base_by_class[demand_class] * demand_weight))


def generate_profile_products(
    product_count: int,
    rng: random.Random,
) -> list[dict[str, str]]:
    products: list[dict[str, str]] = []

    for index in range(product_count):
        category = CATEGORIES[index % len(CATEGORIES)]
        brand = BRANDS[index % len(BRANDS)]
        demand_class = _demand_class(index, product_count)
        demand_weight = _demand_weight(demand_class, rng)
        sku = f"{category[:4].upper()}-{index + 1:06d}"
        base_price = Decimal("9.99") + Decimal(index % 300) * Decimal("1.75")
        price_elasticity = CATEGORY_ELASTICITY[category]
        seasonal_pattern = _seasonal_pattern(category, demand_class)
        return_rate = CATEGORY_RETURN_RATE[category]

        products.append(
            {
                "id": deterministic_uuid("product", sku),
                "sku": sku,
                "name": f"{category} Product {index + 1:06d}",
                "category": category,
                "brand": brand,
                "status": "active",
                "base_price": money(base_price),
                "normal_daily_sales": str(_base_daily_sales(demand_class, demand_weight)),
                "scenario": demand_class,
                "demand_class": demand_class,
                "demand_weight": str(demand_weight.quantize(Decimal("0.0001"))),
                "price_elasticity": str(price_elasticity),
                "seasonal_pattern": seasonal_pattern,
                "return_rate": str(return_rate),
            },
        )

    return products


def generate_profile_stores(
    store_count: int,
    rng: random.Random,
) -> list[dict[str, str]]:
    stores: list[dict[str, str]] = []

    for index in range(store_count):
        region = REGIONS[index % len(REGIONS)]
        channel = CHANNELS[index % len(CHANNELS)]
        store_code = f"STORE-{index + 1:04d}"
        traffic_multiplier = Decimal("0.65") + Decimal(str(rng.random())) * Decimal("1.25")
        promo_sensitivity = Decimal("0.75") + Decimal(str(rng.random())) * Decimal("0.70")
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
                "traffic_multiplier": str(traffic_multiplier.quantize(Decimal("0.0001"))),
                "promo_sensitivity": str(promo_sensitivity.quantize(Decimal("0.0001"))),
            },
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
            },
        )

    return warehouses


def _weekly_multiplier(category: str, channel: str, day_index: int) -> Decimal:
    weekday = (BASE_DATETIME.date() - timedelta(days=day_index)).weekday()
    if channel == "wholesale":
        return Decimal("1.25") if weekday in (0, 1, 2) else Decimal("0.72")
    if weekday in (5, 6):
        if category in {"Fashion", "Toys", "Beauty", "Sports"}:
            return Decimal("1.30")
        if category == "Grocery":
            return Decimal("1.10")
    return Decimal("1.00")


def _seasonal_multiplier(pattern: str, day_index: int) -> Decimal:
    day_of_year = (BASE_DATETIME.date() - timedelta(days=day_index)).timetuple().tm_yday
    if pattern == "holiday_peak" and day_of_year >= HOLIDAY_PEAK_START_DAY:
        return Decimal("1.65")
    if (
        pattern == "spring_summer_peak"
        and SPRING_SUMMER_PEAK_START_DAY <= day_of_year <= SPRING_SUMMER_PEAK_END_DAY
    ):
        return Decimal("1.40")
    if pattern == "seasonal_peak" and day_of_year in range(250, 360):
        return Decimal("1.55")
    if pattern == "stable":
        return Decimal("1.00")
    return Decimal("1.08") if day_of_year % 30 in range(5) else Decimal("1.00")


def _lifecycle_multiplier(product: dict[str, str], day_index: int, days: int) -> Decimal:
    demand_class = product["demand_class"]
    age_progress = Decimal(str((days - day_index) / max(days, 1)))
    if demand_class == "new_product":
        return Decimal("0.45") + age_progress * Decimal("1.25")
    if demand_class == "declining_product":
        return Decimal("1.30") - age_progress * Decimal("0.65")
    if demand_class == "clearance_product":
        return Decimal("0.75") + age_progress * Decimal("0.55")
    return Decimal("1.00")


def _promotion_multiplier(
    product: dict[str, str],
    store: dict[str, str],
    day_index: int,
) -> tuple[Decimal, str, Decimal]:
    if PROMO_START_DAY <= day_index <= PROMO_END_DAY:
        base_uplift = CATEGORY_PROMO_UPLIFT[product["category"]]
        sensitivity = Decimal(store["promo_sensitivity"])
        uplift = Decimal("1.00") + (base_uplift - Decimal("1.00")) * sensitivity
        return uplift, "true", uplift
    if POST_PROMO_DIP_START_DAY <= day_index <= POST_PROMO_DIP_END_DAY:
        return Decimal("0.86"), "false", Decimal("0.86")
    if PRE_PROMO_SOFTENING_START_DAY <= day_index <= PRE_PROMO_SOFTENING_END_DAY:
        return Decimal("0.92"), "false", Decimal("0.92")
    return Decimal("1.00"), "false", Decimal("1.00")


def _price_effect(product: dict[str, str], day_index: int) -> tuple[Decimal, Decimal]:
    base_price = Decimal(product["base_price"])
    if PROMO_START_DAY <= day_index <= PROMO_END_DAY:
        price = base_price * Decimal("0.90")
    elif day_index % 29 == 0:
        price = base_price * Decimal("1.06")
    elif product["demand_class"] == "clearance_product":
        price = base_price * Decimal("0.84")
    else:
        price = base_price

    elasticity = Decimal(product["price_elasticity"])
    price_delta = (price - base_price) / base_price
    effect = max(Decimal("0.35"), Decimal("1.00") - price_delta * elasticity)
    return price, effect


def _stock_limit(
    product: dict[str, str],
    latent_demand: int,
    day_index: int,
) -> tuple[int, str]:
    if product["demand_class"] == "hero_product" and day_index % 31 in range(4):
        return max(0, int(latent_demand * Decimal("0.55"))), "true"
    if product["demand_class"] == "stockout_risk":
        return max(0, int(latent_demand * Decimal("0.65"))), "true"
    if product["demand_class"] == "long_tail":
        return latent_demand, "false"
    return latent_demand, "false"


def _data_quality_status(rng: random.Random) -> str:
    value = rng.random()
    if value < DATA_QUALITY_DUPLICATE_THRESHOLD:
        return "duplicate_candidate"
    if value < DATA_QUALITY_LATE_EVENT_THRESHOLD:
        return "late_event"
    if value < DATA_QUALITY_MISSING_CONTEXT_THRESHOLD:
        return "missing_optional_context"
    return "ok"


def _products_by_category(products: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for product in products:
        grouped[product["category"]].append(product)
    return grouped


def _basket_size(channel: str, rng: random.Random) -> int:
    roll = rng.random()
    thresholds = BASKET_SIZE_ROLL_THRESHOLDS
    if channel == "wholesale":
        return 3 if roll < thresholds["wholesale"][0] else 4
    if channel == "online":
        return 1 if roll < thresholds["online"][0] else 2 if roll < thresholds["online"][1] else 3
    if channel == "marketplace":
        return 1 if roll < thresholds["marketplace"][0] else 2
    return 1 if roll < thresholds["store"][0] else 2


def generate_profile_commerce(
    products: list[dict[str, str]],
    stores: list[dict[str, str]],
    days: int,
    rng: random.Random,
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    sales: list[dict[str, str]] = []
    orders: list[dict[str, str]] = []
    order_items: list[dict[str, str]] = []
    products_by_category = _products_by_category(products)

    for day_index in range(days):
        for product_index, product in enumerate(products):
            store = stores[(product_index + day_index) % len(stores)]
            basket_size = _basket_size(store["channel"], rng)
            order_reference = f"ORD-{product['sku']}-{day_index + 1:04d}"
            order_id = deterministic_uuid("order", order_reference)
            candidate_products = [product]
            complementary = COMPLEMENTARY_CATEGORY[product["category"]]
            candidate_products.extend(
                products_by_category.get(complementary, [])[: max(0, basket_size - 1)],
            )
            candidate_products = candidate_products[:basket_size]
            order_total = Decimal("0.00")
            order_item_rows: list[dict[str, str]] = []

            for item_index, item_product in enumerate(candidate_products):
                base_demand = Decimal(item_product["normal_daily_sales"])
                weekly = _weekly_multiplier(
                    item_product["category"],
                    store["channel"],
                    day_index,
                )
                seasonal = _seasonal_multiplier(
                    item_product["seasonal_pattern"],
                    day_index,
                )
                lifecycle = _lifecycle_multiplier(item_product, day_index, days)
                price, price_effect = _price_effect(item_product, day_index)
                promotion, promotion_applied, promotion_uplift = _promotion_multiplier(
                    item_product,
                    store,
                    day_index,
                )
                noise = Decimal(str(rng.uniform(0.78, 1.24)))
                latent_demand = max(
                    1,
                    int(
                        base_demand
                        * Decimal(item_product["demand_weight"])
                        * Decimal(store["traffic_multiplier"])
                        * weekly
                        * seasonal
                        * lifecycle
                        * price_effect
                        * promotion
                        * noise,
                    ),
                )
                observed_sales, stockout_flag = _stock_limit(
                    item_product,
                    latent_demand,
                    day_index,
                )
                if item_index > 0:
                    observed_sales = max(1, int(observed_sales * Decimal("0.18")))
                    latent_demand = max(observed_sales, int(latent_demand * Decimal("0.18")))

                unit_price = money(price)
                total_amount = money(Decimal(observed_sales) * Decimal(unit_price))
                order_total += Decimal(total_amount)
                item_key = f"{order_reference}-{item_product['sku']}-{item_index + 1}"
                order_item_id = deterministic_uuid("order_item", item_key)
                sale_id = deterministic_uuid("sale", item_key)
                sold_at = _date_at_offset(day_index, (product_index + item_index) % 12)
                data_quality_status = _data_quality_status(rng)

                order_item_rows.append(
                    {
                        "id": order_item_id,
                        "order_id": order_id,
                        "product_id": item_product["id"],
                        "quantity": str(observed_sales),
                        "unit_price": unit_price,
                        "total_amount": total_amount,
                        "currency": "PLN",
                    },
                )
                sales.append(
                    {
                        "id": sale_id,
                        "product_id": item_product["id"],
                        "quantity": str(observed_sales),
                        "unit_price": unit_price,
                        "total_amount": total_amount,
                        "currency": "PLN",
                        "channel": store["channel"],
                        "region": store["region"],
                        "sold_at": sold_at,
                        "order_reference": order_reference,
                        "latent_demand": str(latent_demand),
                        "observed_sales": str(observed_sales),
                        "stockout_flag": stockout_flag,
                        "promotion_applied": promotion_applied,
                        "promotion_uplift": str(promotion_uplift.quantize(Decimal("0.0001"))),
                        "price_elasticity_effect": str(price_effect.quantize(Decimal("0.0001"))),
                        "demand_noise": str(noise.quantize(Decimal("0.0001"))),
                        "data_quality_status": data_quality_status,
                        "ingested_at": _date_at_offset(
                            day_index,
                            (product_index + item_index) % 12
                            + (2 if data_quality_status == "late_event" else 0),
                        ),
                    },
                )

            orders.append(
                {
                    "id": order_id,
                    "order_reference": order_reference,
                    "store_id": store["id"],
                    "channel": store["channel"],
                    "region": store["region"],
                    "status": "completed",
                    "order_total": money(order_total),
                    "currency": "PLN",
                    "ordered_at": _date_at_offset(day_index, product_index % 12),
                    "created_at": _date_at_offset(day_index, product_index % 12),
                },
            )
            order_items.extend(order_item_rows)

    return sales, orders, order_items


def generate_profile_inventory_snapshots(
    products: list[dict[str, str]],
    warehouses: list[dict[str, str]],
    days: int,
) -> list[dict[str, str]]:
    snapshots: list[dict[str, str]] = []
    oldest_snapshot_day_index = ((days - 1) // 7) * 7

    for day_index in range(days):
        if day_index % 7 != 0 and day_index != 0:
            continue

        for product_index, product in enumerate(products):
            warehouse = warehouses[(product_index + day_index) % len(warehouses)]
            normal_daily_sales = int(product["normal_daily_sales"])
            chronological_day = oldest_snapshot_day_index - day_index
            cycle_position = chronological_day % 28
            cycle_start_stock = normal_daily_sales * (12 + product_index % 18) + 160
            stock_quantity = max(
                0,
                cycle_start_stock - cycle_position * max(1, normal_daily_sales // 3),
            )
            natural_key = f"{product['sku']}-{warehouse['warehouse_code']}-{day_index}"
            recorded_at = _date_at_offset(day_index, product_index % 8)

            snapshots.append(
                {
                    "id": deterministic_uuid("inventory_snapshot", natural_key),
                    "product_id": product["id"],
                    "stock_quantity": str(stock_quantity),
                    "unit_of_measure": "pcs",
                    "warehouse_code": warehouse["warehouse_code"],
                    "recorded_at": recorded_at,
                    "ingested_at": recorded_at,
                    "created_at": recorded_at,
                },
            )

    return snapshots


def generate_profile_stock_movements(
    inventory_snapshots: list[dict[str, str]],
    sales: list[dict[str, str]],
    warehouses: list[dict[str, str]],
) -> list[dict[str, str]]:
    warehouse_ids = {warehouse["warehouse_code"]: warehouse["id"] for warehouse in warehouses}
    warehouse_codes = list(warehouse_ids)
    movements: list[dict[str, str]] = []

    for snapshot in inventory_snapshots:
        natural_key = f"initial-{snapshot['id']}"
        movements.append(
            {
                "id": deterministic_uuid("stock_movement", natural_key),
                "product_id": snapshot["product_id"],
                "warehouse_id": warehouse_ids[snapshot["warehouse_code"]],
                "warehouse_code": snapshot["warehouse_code"],
                "movement_type": "initial_stock",
                "quantity": snapshot["stock_quantity"],
                "unit_of_measure": snapshot["unit_of_measure"],
                "source_reference": snapshot["id"],
                "occurred_at": snapshot["recorded_at"],
                "created_at": snapshot["created_at"],
            },
        )
        day_value = snapshot["recorded_at"][:10]
        if day_value.endswith(("-30", "-01")):
            natural_key = f"replenishment-{snapshot['id']}"
            movements.append(
                {
                    "id": deterministic_uuid("stock_movement", natural_key),
                    "product_id": snapshot["product_id"],
                    "warehouse_id": warehouse_ids[snapshot["warehouse_code"]],
                    "warehouse_code": snapshot["warehouse_code"],
                    "movement_type": "replenishment",
                    "quantity": str(max(10, int(snapshot["stock_quantity"]) // 3)),
                    "unit_of_measure": snapshot["unit_of_measure"],
                    "source_reference": snapshot["id"],
                    "occurred_at": snapshot["recorded_at"],
                    "created_at": snapshot["created_at"],
                },
            )

    for index, sale in enumerate(sales):
        warehouse_code = warehouse_codes[index % len(warehouse_codes)]
        natural_key = f"sale-{sale['id']}"
        movements.append(
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

    return movements


def generate_profile_returns(
    products: list[dict[str, str]],
    order_items: list[dict[str, str]],
    orders: list[dict[str, str]],
    rng: random.Random,
) -> list[dict[str, str]]:
    order_by_id = {order["id"]: order for order in orders}
    product_by_id = {product["id"]: product for product in products}
    returns: list[dict[str, str]] = []

    for index, order_item in enumerate(order_items):
        product = product_by_id[order_item["product_id"]]
        order = order_by_id[order_item["order_id"]]
        base_rate = Decimal(product["return_rate"])
        channel_multiplier = {
            "online": Decimal("1.55"),
            "store": Decimal("1.00"),
            "marketplace": Decimal("1.80"),
            "wholesale": Decimal("0.65"),
        }[order["channel"]]
        return_probability = min(
            Decimal("0.75"),
            base_rate * channel_multiplier,
        )
        if Decimal(str(rng.random())) > return_probability:
            continue

        returned_quantity = max(1, int(order_item["quantity"]) // 3)
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
                "returned_at": _date_at_offset(-(1 + index % 5), index % 12),
            },
        )

    return returns


def generate_profile_forecasts(
    products: list[dict[str, str]],
    days: int,  # noqa: ARG001 - retained for profile generator interface
) -> list[dict[str, str]]:
    forecasts: list[dict[str, str]] = []
    forecast_product_count = min(len(products), max(20, len(products) // 2))
    horizon_days = 7

    for index, product in enumerate(products[:forecast_product_count]):
        normal_daily_sales = Decimal(product["normal_daily_sales"])
        demand_weight = Decimal(product["demand_weight"])
        forecast_multiplier = Decimal("1.00")
        if product["demand_class"] == "hero_product":
            forecast_multiplier = Decimal("1.18")
        elif product["demand_class"] == "long_tail":
            forecast_multiplier = Decimal("0.72")
        elif product["demand_class"] == "seasonal":
            forecast_multiplier = Decimal("1.10")

        predicted_quantity = max(
            1,
            int(normal_daily_sales * demand_weight * Decimal("7") * forecast_multiplier),
        )
        confidence = Decimal("0.82") - Decimal(index % 9) * Decimal("0.015")

        for horizon_index in range(horizon_days):
            horizon_multiplier = Decimal("0.94") + Decimal(horizon_index) * Decimal("0.02")
            horizon_quantity = max(1, int(Decimal(predicted_quantity) * horizon_multiplier))
            natural_key = f"{product['sku']}-profile-weekly-forecast-{horizon_index + 1}"
            forecast_start_offset = -(horizon_index + 1)
            forecast_end_offset = -(horizon_index + horizon_days)
            horizon_confidence = confidence - Decimal(horizon_index) * Decimal("0.01")

            forecasts.append(
                {
                    "id": deterministic_uuid("forecast", natural_key),
                    "product_id": product["id"],
                    "forecast_period_start": _date_only_at_offset(forecast_start_offset),
                    "forecast_period_end": _date_only_at_offset(forecast_end_offset),
                    "predicted_quantity": str(horizon_quantity),
                    "unit_of_measure": "pcs",
                    "generated_at": _date_at_offset(0, horizon_index + 1),
                    "method": "retailops-realism-baseline-demand-model",
                    "status": "generated",
                    "confidence_level": str(
                        max(Decimal("0.55"), horizon_confidence).quantize(Decimal("0.0001")),
                    ),
                },
            )

    return forecasts


def _sales_by_product(sales: list[dict[str, str]]) -> dict[str, int]:
    totals: dict[str, int] = defaultdict(int)
    for sale in sales:
        totals[sale["product_id"]] += int(sale["quantity"])
    return totals


def generate_profile_incident_dataset(
    products: list[dict[str, str]],
    users: list[dict[str, str]],
    sales: list[dict[str, str]],
) -> dict[str, list[dict[str, str]]]:
    anomalies: list[dict[str, str]] = []
    alerts: list[dict[str, str]] = []
    recommendations: list[dict[str, str]] = []
    workflow_actions: list[dict[str, str]] = []
    assigned_user = users[0]
    actor = users[-1]
    product_sales = _sales_by_product(sales)
    candidate_products = sorted(
        products,
        key=lambda product: product_sales.get(product["id"], 0),
    )[: min(20, len(products))]

    for index, product in enumerate(candidate_products):
        total_sales = Decimal(product_sales.get(product["id"], 0))
        expected_value = Decimal(product["normal_daily_sales"]) * Decimal("14")
        if product["demand_class"] == "hero_product":
            anomaly_type = "sales_spike"
            alert_type = "stockout_risk"
            actual_value = expected_value * Decimal("1.80")
        elif product["demand_class"] in {"long_tail", "declining_product"}:
            anomaly_type = "sales_drop"
            alert_type = "sales_drop"
            actual_value = max(Decimal("1"), total_sales)
        else:
            anomaly_type = "stale_inventory"
            alert_type = "overstock_risk"
            actual_value = expected_value * Decimal("0.45")

        severity = ["medium", "high", "critical"][index % 3]
        deviation = ((actual_value - expected_value) / expected_value) * 100
        anomaly_id = deterministic_uuid("anomaly", product["sku"])
        alert_id = deterministic_uuid("alert", product["sku"])
        recommendation_id = deterministic_uuid("recommendation", product["sku"])
        workflow_action_id = deterministic_uuid("workflow_action", product["sku"])
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
            },
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
            },
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
                "rationale": "Derived from synthetic business signal.",
                "status": "proposed",
                "generated_at": detected_at,
                "expires_at": "",
                "created_at": detected_at,
            },
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
            },
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
    seed: int = 42,
) -> dict[str, list[dict[str, str]]]:
    rng = _rng(seed, profile)
    products = generate_profile_products(product_count, rng)
    users = generate_users()
    stores = generate_profile_stores(store_count, rng)
    warehouses = generate_profile_warehouses(warehouse_count)
    sales, orders, order_items = generate_profile_commerce(
        products,
        stores,
        days,
        rng,
    )
    price_history = generate_price_history(products)
    promotions = generate_promotions(products)
    inventory_snapshots = generate_profile_inventory_snapshots(
        products,
        warehouses,
        days,
    )
    stock_movements = generate_profile_stock_movements(
        inventory_snapshots,
        sales,
        warehouses,
    )
    returns = generate_profile_returns(products, order_items, orders, rng)
    forecasts = generate_profile_forecasts(products, days)
    incidents = generate_profile_incident_dataset(products, users, sales)

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
