import os
from datetime import date, datetime, timezone
from decimal import Decimal
from urllib.parse import urlparse

import psycopg


DATABASE_URL = os.getenv("DATABASE_URL")

APP_TABLES = [
    "workflow_actions",
    "recommendations",
    "alerts",
    "anomalies",
    "forecasts",
    "inventory_snapshots",
    "sales",
    "users",
    "products",
]


PRODUCT_IDS = {
    "milk": "11111111-1111-1111-1111-111111111111",
    "bread": "22222222-2222-2222-2222-222222222222",
    "coffee": "33333333-3333-3333-3333-333333333333",
    "headphones": "44444444-4444-4444-4444-444444444444",
    "yoga_mat": "55555555-5555-5555-5555-555555555555",
    "jacket": "66666666-6666-6666-6666-666666666666",
    "rice": "77777777-7777-7777-7777-777777777777",
    "floor_panels": "88888888-8888-8888-8888-888888888888",
}

USER_IDS = {
    "inventory_planner": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    "category_manager": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
    "analyst": "cccccccc-cccc-cccc-cccc-cccccccccccc",
    "admin": "dddddddd-dddd-dddd-dddd-dddddddddddd",
}

FORECAST_IDS = {
    "milk": "f1111111-1111-1111-1111-111111111111",
    "headphones": "f2222222-2222-2222-2222-222222222222",
    "jacket": "f3333333-3333-3333-3333-333333333333",
    "floor_panels": "f4444444-4444-4444-4444-444444444444",
}

ANOMALY_IDS = {
    "milk_sales_drop": "e1111111-1111-1111-1111-111111111111",
    "floor_stale_inventory": "e2222222-2222-2222-2222-222222222222",
    "headphones_pricing": "e3333333-3333-3333-3333-333333333333",
    "jacket_sales_spike": "e4444444-4444-4444-4444-444444444444",
}

ALERT_IDS = {
    "milk_sales_drop": "90000000-0000-0000-0000-000000000001",
    "floor_stale_inventory": "90000000-0000-0000-0000-000000000002",
    "headphones_pricing": "90000000-0000-0000-0000-000000000003",
    "jacket_stockout": "90000000-0000-0000-0000-000000000004",
}

RECOMMENDATION_IDS = {
    "milk_investigate": "80000000-0000-0000-0000-000000000001",
    "floor_refresh": "80000000-0000-0000-0000-000000000002",
    "headphones_price": "80000000-0000-0000-0000-000000000003",
    "jacket_replenish": "80000000-0000-0000-0000-000000000004",
}

WORKFLOW_ACTION_IDS = {
    "ack_milk": "70000000-0000-0000-0000-000000000001",
    "assign_floor": "70000000-0000-0000-0000-000000000002",
    "comment_headphones": "70000000-0000-0000-0000-000000000003",
    "accept_jacket": "70000000-0000-0000-0000-000000000004",
}


def require_database_url() -> str:
    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL is not set. Example:\n"
            'DATABASE_URL="postgresql://retailops:retailops@localhost:5432/retailops" '
            "python scripts/seed_demo_data.py"
        )

    parsed = urlparse(DATABASE_URL)
    safe_hosts = {"localhost", "127.0.0.1", "db", "host.docker.internal"}

    if parsed.hostname not in safe_hosts and os.getenv("ALLOW_SEED_NON_LOCAL") != "true":
        raise RuntimeError(
            f"Refusing to seed non-local database host: {parsed.hostname}. "
            "Set ALLOW_SEED_NON_LOCAL=true only if you are sure."
        )

    return DATABASE_URL


def truncate_app_tables(cur: psycopg.Cursor) -> None:
    tables = ", ".join(APP_TABLES)
    cur.execute(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE;")


def seed_products(cur: psycopg.Cursor) -> None:
    products = [
        (PRODUCT_IDS["milk"], "DAIRY-MILK-001", "Organic Milk 1L", "Dairy", "FreshFarm", "active"),
        (PRODUCT_IDS["bread"], "BAKERY-BREAD-001", "Sourdough Bread", "Bakery", "BakeHouse", "active"),
        (PRODUCT_IDS["coffee"], "COFFEE-BEANS-001", "Espresso Beans 1kg", "Coffee", "RoastLab", "active"),
        (PRODUCT_IDS["headphones"], "ELEC-HEAD-001", "Wireless Headphones", "Electronics", "SoundPeak", "active"),
        (PRODUCT_IDS["yoga_mat"], "SPORT-YOGA-001", "Premium Yoga Mat", "Sports", "FitLine", "active"),
        (PRODUCT_IDS["jacket"], "FASHION-JACKET-001", "Winter Jacket", "Fashion", "NorthPeak", "active"),
        (PRODUCT_IDS["rice"], "GROCERY-RICE-001", "Basmati Rice 1kg", "Grocery", "GrainCo", "active"),
        (PRODUCT_IDS["floor_panels"], "HOME-FLOOR-001", "Oak Floor Panels", "Home", "WoodPro", "active"),
    ]

    cur.executemany(
        """
        INSERT INTO products (id, sku, name, category, brand, status)
        VALUES (%s, %s, %s, %s, %s, %s);
        """,
        products,
    )


def seed_users(cur: psycopg.Cursor) -> None:
    users = [
        (
            USER_IDS["inventory_planner"],
            "inventory.planner",
            "Inventory Planner",
            "inventory_planner",
            "Operations",
            "active",
        ),
        (
            USER_IDS["category_manager"],
            "category.manager",
            "Category Manager",
            "category_manager",
            "Commercial",
            "active",
        ),
        (
            USER_IDS["analyst"],
            "retail.analyst",
            "Retail Analyst",
            "analyst",
            "Analytics",
            "active",
        ),
        (
            USER_IDS["admin"],
            "admin.user",
            "Admin User",
            "admin",
            "Platform",
            "active",
        ),
    ]

    cur.executemany(
        """
        INSERT INTO users (id, login, display_name, role, team, status)
        VALUES (%s, %s, %s, %s, %s, %s);
        """,
        users,
    )


def seed_sales(cur: psycopg.Cursor) -> None:
    sales = [
        (
            "10000000-0000-0000-0000-000000000001",
            PRODUCT_IDS["milk"],
            120,
            datetime(2026, 4, 20, 10, 30, tzinfo=timezone.utc),
            Decimal("4.99"),
            Decimal("598.80"),
            "PLN",
            "store",
        ),
        (
            "10000000-0000-0000-0000-000000000002",
            PRODUCT_IDS["milk"],
            65,
            datetime(2026, 4, 21, 11, 15, tzinfo=timezone.utc),
            Decimal("4.99"),
            Decimal("324.35"),
            "PLN",
            "online",
        ),
        (
            "10000000-0000-0000-0000-000000000003",
            PRODUCT_IDS["bread"],
            90,
            datetime(2026, 4, 21, 9, 45, tzinfo=timezone.utc),
            Decimal("7.49"),
            Decimal("674.10"),
            "PLN",
            "store",
        ),
        (
            "10000000-0000-0000-0000-000000000004",
            PRODUCT_IDS["coffee"],
            35,
            datetime(2026, 4, 22, 14, 10, tzinfo=timezone.utc),
            Decimal("49.99"),
            Decimal("1749.65"),
            "PLN",
            "online",
        ),
        (
            "10000000-0000-0000-0000-000000000005",
            PRODUCT_IDS["headphones"],
            18,
            datetime(2026, 4, 22, 16, 20, tzinfo=timezone.utc),
            Decimal("199.99"),
            Decimal("3599.82"),
            "PLN",
            "marketplace",
        ),
        (
            "10000000-0000-0000-0000-000000000006",
            PRODUCT_IDS["jacket"],
            52,
            datetime(2026, 4, 23, 12, 5, tzinfo=timezone.utc),
            Decimal("299.99"),
            Decimal("15599.48"),
            "PLN",
            "online",
        ),
        (
            "10000000-0000-0000-0000-000000000007",
            PRODUCT_IDS["rice"],
            80,
            datetime(2026, 4, 23, 17, 40, tzinfo=timezone.utc),
            Decimal("11.99"),
            Decimal("959.20"),
            "PLN",
            "store",
        ),
        (
            "10000000-0000-0000-0000-000000000008",
            PRODUCT_IDS["floor_panels"],
            12,
            datetime(2026, 4, 24, 13, 25, tzinfo=timezone.utc),
            Decimal("89.99"),
            Decimal("1079.88"),
            "PLN",
            "store",
        ),
    ]

    cur.executemany(
        """
        INSERT INTO sales
            (id, product_id, quantity, sold_at, unit_price, total_amount, currency, channel)
        VALUES
            (%s, %s, %s, %s, %s, %s, %s, %s);
        """,
        sales,
    )


def seed_inventory_snapshots(cur: psycopg.Cursor) -> None:
    snapshots = [
        (
            "20000000-0000-0000-0000-000000000001",
            PRODUCT_IDS["milk"],
            42,
            "pcs",
            "WH-WAW-01",
            datetime(2026, 4, 24, 8, 0, tzinfo=timezone.utc),
            datetime(2026, 4, 24, 8, 5, tzinfo=timezone.utc),
        ),
        (
            "20000000-0000-0000-0000-000000000002",
            PRODUCT_IDS["bread"],
            125,
            "pcs",
            "WH-WAW-01",
            datetime(2026, 4, 24, 8, 0, tzinfo=timezone.utc),
            datetime(2026, 4, 24, 8, 5, tzinfo=timezone.utc),
        ),
        (
            "20000000-0000-0000-0000-000000000003",
            PRODUCT_IDS["coffee"],
            88,
            "kg",
            "WH-WAW-02",
            datetime(2026, 4, 24, 8, 0, tzinfo=timezone.utc),
            datetime(2026, 4, 24, 8, 6, tzinfo=timezone.utc),
        ),
        (
            "20000000-0000-0000-0000-000000000004",
            PRODUCT_IDS["headphones"],
            15,
            "pcs",
            "WH-GDN-01",
            datetime(2026, 4, 24, 8, 0, tzinfo=timezone.utc),
            datetime(2026, 4, 24, 8, 7, tzinfo=timezone.utc),
        ),
        (
            "20000000-0000-0000-0000-000000000005",
            PRODUCT_IDS["jacket"],
            9,
            "pcs",
            "WH-GDN-01",
            datetime(2026, 4, 24, 8, 0, tzinfo=timezone.utc),
            datetime(2026, 4, 24, 8, 8, tzinfo=timezone.utc),
        ),
        (
            "20000000-0000-0000-0000-000000000006",
            PRODUCT_IDS["floor_panels"],
            320,
            "m2",
            "WH-POZ-01",
            datetime(2026, 4, 24, 8, 0, tzinfo=timezone.utc),
            datetime(2026, 4, 24, 8, 9, tzinfo=timezone.utc),
        ),
    ]

    cur.executemany(
        """
        INSERT INTO inventory_snapshots
            (id, product_id, stock_quantity, unit_of_measure, warehouse_code, recorded_at, ingested_at)
        VALUES
            (%s, %s, %s, %s, %s, %s, %s);
        """,
        snapshots,
    )


def seed_forecasts(cur: psycopg.Cursor) -> None:
    forecasts = [
        (
            FORECAST_IDS["milk"],
            PRODUCT_IDS["milk"],
            date(2026, 4, 25),
            date(2026, 5, 1),
            Decimal("760.000"),
            "pcs",
            datetime(2026, 4, 24, 9, 0, tzinfo=timezone.utc),
            "moving_average",
            "generated",
            Decimal("0.7800"),
        ),
        (
            FORECAST_IDS["headphones"],
            PRODUCT_IDS["headphones"],
            date(2026, 4, 25),
            date(2026, 5, 1),
            Decimal("95.000"),
            "pcs",
            datetime(2026, 4, 24, 9, 0, tzinfo=timezone.utc),
            "naive_baseline",
            "generated",
            Decimal("0.6400"),
        ),
        (
            FORECAST_IDS["jacket"],
            PRODUCT_IDS["jacket"],
            date(2026, 4, 25),
            date(2026, 5, 1),
            Decimal("180.000"),
            "pcs",
            datetime(2026, 4, 24, 9, 0, tzinfo=timezone.utc),
            "seeded_demo",
            "generated",
            Decimal("0.7200"),
        ),
        (
            FORECAST_IDS["floor_panels"],
            PRODUCT_IDS["floor_panels"],
            date(2026, 4, 25),
            date(2026, 5, 1),
            Decimal("110.000"),
            "m2",
            datetime(2026, 4, 24, 9, 0, tzinfo=timezone.utc),
            "seeded_demo",
            "generated",
            Decimal("0.6900"),
        ),
    ]

    cur.executemany(
        """
        INSERT INTO forecasts
            (
                id,
                product_id,
                forecast_period_start,
                forecast_period_end,
                predicted_quantity,
                unit_of_measure,
                generated_at,
                method,
                status,
                confidence_level
            )
        VALUES
            (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """,
        forecasts,
    )


def seed_anomalies(cur: psycopg.Cursor) -> None:
    anomalies = [
        (
            ANOMALY_IDS["milk_sales_drop"],
            PRODUCT_IDS["milk"],
            "sales_drop",
            "daily_sales_quantity",
            Decimal("120.0000"),
            Decimal("230.0000"),
            Decimal("-47.8260"),
            Decimal("8500.0000"),
            "PLN",
            "high",
            datetime(2026, 4, 20, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 4, 24, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 4, 24, 9, 30, tzinfo=timezone.utc),
        ),
        (
            ANOMALY_IDS["floor_stale_inventory"],
            PRODUCT_IDS["floor_panels"],
            "stale_inventory",
            "days_without_sale",
            Decimal("42.0000"),
            Decimal("14.0000"),
            Decimal("200.0000"),
            Decimal("320.0000"),
            "m2",
            "medium",
            datetime(2026, 4, 1, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 4, 24, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 4, 24, 9, 35, tzinfo=timezone.utc),
        ),
        (
            ANOMALY_IDS["headphones_pricing"],
            PRODUCT_IDS["headphones"],
            "pricing_issue",
            "price_vs_market_index",
            Decimal("199.9900"),
            Decimal("249.9900"),
            Decimal("-20.0000"),
            Decimal("5000.0000"),
            "PLN",
            "medium",
            datetime(2026, 4, 20, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 4, 24, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 4, 24, 9, 40, tzinfo=timezone.utc),
        ),
        (
            ANOMALY_IDS["jacket_sales_spike"],
            PRODUCT_IDS["jacket"],
            "sales_spike",
            "daily_sales_quantity",
            Decimal("310.0000"),
            Decimal("180.0000"),
            Decimal("72.2200"),
            Decimal("130.0000"),
            "pcs",
            "critical",
            datetime(2026, 4, 20, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 4, 24, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 4, 24, 9, 45, tzinfo=timezone.utc),
        ),
    ]

    cur.executemany(
        """
        INSERT INTO anomalies
            (
                id,
                product_id,
                anomaly_type,
                metric_name,
                actual_value,
                expected_value,
                deviation_percent,
                impact_value,
                impact_unit,
                severity,
                period_start,
                period_end,
                detected_at
            )
        VALUES
            (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """,
        anomalies,
    )


def seed_alerts(cur: psycopg.Cursor) -> None:
    alerts = [
        (
            ALERT_IDS["milk_sales_drop"],
            PRODUCT_IDS["milk"],
            ANOMALY_IDS["milk_sales_drop"],
            USER_IDS["category_manager"],
            "sales_drop",
            "high",
            "open",
            "Organic Milk sales dropped below expected demand",
            "Investigate promotion, pricing, and store availability for Organic Milk.",
        ),
        (
            ALERT_IDS["floor_stale_inventory"],
            PRODUCT_IDS["floor_panels"],
            ANOMALY_IDS["floor_stale_inventory"],
            USER_IDS["inventory_planner"],
            "stale_inventory",
            "medium",
            "acknowledged",
            "Oak Floor Panels inventory is stale",
            "Review stock aging and consider markdown or stock transfer.",
        ),
        (
            ALERT_IDS["headphones_pricing"],
            PRODUCT_IDS["headphones"],
            ANOMALY_IDS["headphones_pricing"],
            USER_IDS["analyst"],
            "sales_drop",
            "medium",
            "in_progress",
            "Wireless Headphones price may be below market pattern",
            "Review pricing strategy and marketplace competitiveness.",
        ),
        (
            ALERT_IDS["jacket_stockout"],
            PRODUCT_IDS["jacket"],
            ANOMALY_IDS["jacket_sales_spike"],
            USER_IDS["inventory_planner"],
            "stockout_risk",
            "critical",
            "open",
            "Winter Jacket stockout risk after demand spike",
            "Replenish stock and validate demand forecast before weekend.",
        ),
    ]

    cur.executemany(
        """
        INSERT INTO alerts
            (
                id,
                product_id,
                anomaly_id,
                assigned_to_user_id,
                alert_type,
                severity,
                status,
                title,
                recommended_action
            )
        VALUES
            (%s, %s, %s, %s, %s, %s, %s, %s, %s);
        """,
        alerts,
    )


def seed_recommendations(cur: psycopg.Cursor) -> None:
    recommendations = [
        (
            RECOMMENDATION_IDS["milk_investigate"],
            PRODUCT_IDS["milk"],
            FORECAST_IDS["milk"],
            ANOMALY_IDS["milk_sales_drop"],
            ALERT_IDS["milk_sales_drop"],
            "investigate_sales_drop",
            "Check availability, promotion calendar, and competitor pricing.",
            "Sales dropped materially below baseline and may require commercial review.",
            "proposed",
            datetime(2026, 4, 24, 10, 0, tzinfo=timezone.utc),
            datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc),
        ),
        (
            RECOMMENDATION_IDS["floor_refresh"],
            PRODUCT_IDS["floor_panels"],
            FORECAST_IDS["floor_panels"],
            ANOMALY_IDS["floor_stale_inventory"],
            ALERT_IDS["floor_stale_inventory"],
            "refresh_inventory_data",
            "Refresh inventory data and validate stock movement records.",
            "Inventory appears stale and may indicate slow movement or outdated records.",
            "accepted",
            datetime(2026, 4, 24, 10, 5, tzinfo=timezone.utc),
            datetime(2026, 5, 1, 10, 5, tzinfo=timezone.utc),
        ),
        (
            RECOMMENDATION_IDS["headphones_price"],
            PRODUCT_IDS["headphones"],
            FORECAST_IDS["headphones"],
            ANOMALY_IDS["headphones_pricing"],
            ALERT_IDS["headphones_pricing"],
            "review_price",
            "Review current price against target margin and marketplace benchmarks.",
            "Detected price pattern may affect margin and demand quality.",
            "proposed",
            datetime(2026, 4, 24, 10, 10, tzinfo=timezone.utc),
            datetime(2026, 5, 1, 10, 10, tzinfo=timezone.utc),
        ),
        (
            RECOMMENDATION_IDS["jacket_replenish"],
            PRODUCT_IDS["jacket"],
            FORECAST_IDS["jacket"],
            ANOMALY_IDS["jacket_sales_spike"],
            ALERT_IDS["jacket_stockout"],
            "replenish_stock",
            "Create urgent replenishment order for Winter Jacket.",
            "Demand spike combined with low inventory creates stockout risk.",
            "proposed",
            datetime(2026, 4, 24, 10, 15, tzinfo=timezone.utc),
            datetime(2026, 5, 1, 10, 15, tzinfo=timezone.utc),
        ),
    ]

    cur.executemany(
        """
        INSERT INTO recommendations
            (
                id,
                product_id,
                forecast_id,
                anomaly_id,
                alert_id,
                recommendation_type,
                recommended_action,
                rationale,
                status,
                generated_at,
                expires_at
            )
        VALUES
            (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """,
        recommendations,
    )


def seed_workflow_actions(cur: psycopg.Cursor) -> None:
    workflow_actions = [
        (
            WORKFLOW_ACTION_IDS["ack_milk"],
            ALERT_IDS["milk_sales_drop"],
            USER_IDS["category_manager"],
            "acknowledge",
            "Initial review started.",
            "open",
            "acknowledged",
            datetime(2026, 4, 24, 10, 30, tzinfo=timezone.utc),
        ),
        (
            WORKFLOW_ACTION_IDS["assign_floor"],
            ALERT_IDS["floor_stale_inventory"],
            USER_IDS["admin"],
            "assign",
            "Assigned to inventory planning team.",
            "open",
            "acknowledged",
            datetime(2026, 4, 24, 10, 35, tzinfo=timezone.utc),
        ),
        (
            WORKFLOW_ACTION_IDS["comment_headphones"],
            ALERT_IDS["headphones_pricing"],
            USER_IDS["analyst"],
            "comment",
            "Marketplace price comparison is being prepared.",
            "in_progress",
            "in_progress",
            datetime(2026, 4, 24, 10, 40, tzinfo=timezone.utc),
        ),
        (
            WORKFLOW_ACTION_IDS["accept_jacket"],
            ALERT_IDS["jacket_stockout"],
            USER_IDS["inventory_planner"],
            "accept",
            "Replenishment recommendation accepted.",
            "open",
            "in_progress",
            datetime(2026, 4, 24, 10, 45, tzinfo=timezone.utc),
        ),
    ]

    cur.executemany(
        """
        INSERT INTO workflow_actions
            (
                id,
                alert_id,
                performed_by_user_id,
                action_type,
                comment,
                previous_status,
                new_status,
                performed_at
            )
        VALUES
            (%s, %s, %s, %s, %s, %s, %s, %s);
        """,
        workflow_actions,
    )


def print_counts(cur: psycopg.Cursor) -> None:
    print("\nSeed summary:")
    for table in reversed(APP_TABLES):
        cur.execute(f"SELECT COUNT(*) FROM {table};")
        count = cur.fetchone()[0]
        print(f"- {table}: {count}")


def main() -> None:
    database_url = require_database_url()

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            truncate_app_tables(cur)

            seed_products(cur)
            seed_users(cur)
            seed_sales(cur)
            seed_inventory_snapshots(cur)
            seed_forecasts(cur)
            seed_anomalies(cur)
            seed_alerts(cur)
            seed_recommendations(cur)
            seed_workflow_actions(cur)

            print_counts(cur)

        conn.commit()

    print("\nDemo seed data inserted successfully.")


if __name__ == "__main__":
    main()
