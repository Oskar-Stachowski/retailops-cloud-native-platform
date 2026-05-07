from __future__ import annotations

PRODUCT_BLUEPRINTS: list[dict[str, object]] = [
    {
        "sku": "ELEC-HEAD-001",
        "name": "Wireless Headphones",
        "category": "Electronics",
        "brand": "SoundWave",
        "base_price": 299.00,
        "normal_daily_sales": 18,
        "scenario": "sales_drop",
    },
    {
        "sku": "HOME-FLOOR-001",
        "name": "Oak Floor Panels",
        "category": "Home Improvement",
        "brand": "NordicHome",
        "base_price": 89.90,
        "normal_daily_sales": 7,
        "scenario": "stale_inventory",
    },
    {
        "sku": "DAIRY-MILK-001",
        "name": "Organic Milk 1L",
        "category": "Grocery",
        "brand": "GreenFarm",
        "base_price": 6.49,
        "normal_daily_sales": 130,
        "scenario": "sales_drop",
    },
    {
        "sku": "FASHION-JACKET-001",
        "name": "Winter Jacket",
        "category": "Fashion",
        "brand": "UrbanNorth",
        "base_price": 399.00,
        "normal_daily_sales": 24,
        "scenario": "stockout_risk",
    },
    {
        "sku": "BEAUTY-CREAM-001",
        "name": "Moisturizing Cream",
        "category": "Beauty",
        "brand": "SkinLab",
        "base_price": 49.99,
        "normal_daily_sales": 42,
        "scenario": "normal",
    },
    {
        "sku": "SPORT-YOGA-001",
        "name": "Yoga Mat",
        "category": "Sports",
        "brand": "FitCore",
        "base_price": 79.00,
        "normal_daily_sales": 16,
        "scenario": "normal",
    },
    {
        "sku": "TOYS-BLOCKS-001",
        "name": "Creative Blocks Set",
        "category": "Toys",
        "brand": "PlayBox",
        "base_price": 119.00,
        "normal_daily_sales": 13,
        "scenario": "normal",
    },
    {
        "sku": "PET-FOOD-001",
        "name": "Premium Dog Food 3kg",
        "category": "Pet Care",
        "brand": "HappyPaws",
        "base_price": 69.90,
        "normal_daily_sales": 28,
        "scenario": "normal",
    },
]

USER_BLUEPRINTS: list[dict[str, str]] = [
    {
        "login": "category.manager",
        "display_name": "Category Manager",
        "role": "category_manager",
        "team": "Commercial",
    },
    {
        "login": "inventory.planner",
        "display_name": "Inventory Planner",
        "role": "inventory_planner",
        "team": "Supply Chain",
    },
    {
        "login": "retail.analyst",
        "display_name": "Retail Analyst",
        "role": "analyst",
        "team": "Analytics",
    },
    {
        "login": "admin.user",
        "display_name": "Admin User",
        "role": "admin",
        "team": "Platform",
    },
]

STORE_BLUEPRINTS: list[dict[str, str]] = [
    {
        "store_code": "WAW-STORE-01",
        "name": "RetailOps Warsaw Central",
        "region": "PL-Central",
        "country": "PL",
        "city": "Warsaw",
        "channel": "store",
    },
    {
        "store_code": "GDN-STORE-01",
        "name": "RetailOps Gdansk North",
        "region": "PL-North",
        "country": "PL",
        "city": "Gdansk",
        "channel": "store",
    },
    {
        "store_code": "KRK-STORE-01",
        "name": "RetailOps Krakow South",
        "region": "PL-South",
        "country": "PL",
        "city": "Krakow",
        "channel": "store",
    },
    {
        "store_code": "BER-MKT-01",
        "name": "RetailOps Berlin Marketplace",
        "region": "DE-East",
        "country": "DE",
        "city": "Berlin",
        "channel": "marketplace",
    },
]

WAREHOUSE_BLUEPRINTS: list[dict[str, str]] = [
    {
        "warehouse_code": "WAW-01",
        "name": "Warsaw Fulfillment Center",
        "region": "PL-Central",
        "country": "PL",
        "city": "Warsaw",
    },
    {
        "warehouse_code": "GDN-01",
        "name": "Gdansk Regional Warehouse",
        "region": "PL-North",
        "country": "PL",
        "city": "Gdansk",
    },
    {
        "warehouse_code": "KRK-01",
        "name": "Krakow Regional Warehouse",
        "region": "PL-South",
        "country": "PL",
        "city": "Krakow",
    },
    {
        "warehouse_code": "POZ-01",
        "name": "Poznan Overflow Warehouse",
        "region": "PL-Central",
        "country": "PL",
        "city": "Poznan",
    },
]

CHANNELS = ["online", "store", "marketplace", "wholesale"]
REGIONS = ["PL-North", "PL-Central", "PL-South", "DE-East"]
WAREHOUSES = ["WAW-01", "GDN-01", "KRK-01", "POZ-01"]
UNIT_OF_MEASURE = ["pcs", "kg"]
