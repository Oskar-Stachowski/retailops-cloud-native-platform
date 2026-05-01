from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import psycopg
import pytest

API_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = API_ROOT.parents[1]
DEFAULT_DATABASE_URL = (
    "postgresql://retailops:retailops@localhost:5432/retailops"
)
EXPECTED_ROW_COUNTS = {
    "products": 8,
    "users": 4,
    "sales": 16,
    "inventory_snapshots": 8,
    "forecasts": 6,
    "anomalies": 4,
    "alerts": 4,
    "recommendations": 4,
    "workflow_actions": 4,
}
EXPECTED_CSV_FILES = [
    f"{table_name}.csv" for table_name in EXPECTED_ROW_COUNTS
]


@pytest.fixture(scope="module")
def database_url() -> str:
    return os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)


def run_generator() -> None:
    subprocess.run(
        [sys.executable, "-m", "data.generator.main"],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )


def run_seed(database_url: str) -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    env["RETAILOPS_DEMO_DATA_DIR"] = str(REPO_ROOT / "data" / "demo")

    subprocess.run(
        [sys.executable, "scripts/seed_demo_data.py"],
        cwd=API_ROOT,
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )


@pytest.fixture(scope="module", autouse=True)
def prepared_demo_dataset(database_url: str) -> None:
    run_generator()
    run_seed(database_url)


def fetch_one(database_url: str, query: str, params: tuple = ()):
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchone()


def fetch_all(database_url: str, query: str, params: tuple = ()):
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()


def test_generator_produces_expected_csv_files() -> None:
    data_dir = REPO_ROOT / "data" / "demo"

    for filename in EXPECTED_CSV_FILES:
        csv_path = data_dir / filename
        assert csv_path.exists(), f"Missing generated CSV file: {csv_path}"
        assert csv_path.read_text(encoding="utf-8").splitlines()[0]


def test_seed_script_is_idempotent(database_url: str) -> None:
    run_seed(database_url)
    first_counts = {
        table_name: fetch_one(
            database_url,
            f"SELECT COUNT(*) FROM {table_name};",
        )[0]
        for table_name in EXPECTED_ROW_COUNTS
    }

    run_seed(database_url)
    second_counts = {
        table_name: fetch_one(
            database_url,
            f"SELECT COUNT(*) FROM {table_name};",
        )[0]
        for table_name in EXPECTED_ROW_COUNTS
    }

    assert first_counts == EXPECTED_ROW_COUNTS
    assert second_counts == EXPECTED_ROW_COUNTS


def test_demo_seed_data_has_expected_row_counts(database_url: str) -> None:
    for table_name, expected_count in EXPECTED_ROW_COUNTS.items():
        actual_count = fetch_one(
            database_url,
            f"SELECT COUNT(*) FROM {table_name};",
        )[0]
        assert actual_count == expected_count, table_name


def test_demo_seed_covers_core_retail_dimensions(database_url: str) -> None:
    category_count, brand_count = fetch_one(
        database_url,
        """
        SELECT COUNT(DISTINCT category), COUNT(DISTINCT brand)
        FROM products;
        """,
    )
    channel_count, region_count = fetch_one(
        database_url,
        """
        SELECT COUNT(DISTINCT channel), COUNT(DISTINCT region)
        FROM sales;
        """,
    )
    warehouse_count = fetch_one(
        database_url,
        """
        SELECT COUNT(DISTINCT warehouse_code)
        FROM inventory_snapshots;
        """,
    )[0]

    assert category_count >= 6
    assert brand_count >= 6
    assert channel_count == 4
    assert region_count >= 3
    assert warehouse_count >= 3


def test_sales_are_connected_to_products_and_values_are_valid(
    database_url: str,
) -> None:
    invalid_sales = fetch_one(
        database_url,
        """
        SELECT COUNT(*)
        FROM sales s
        LEFT JOIN products p ON p.id = s.product_id
        WHERE p.id IS NULL
            OR s.quantity <= 0
            OR s.unit_price < 0
            OR LENGTH(s.currency) <> 3
            OR s.channel NOT IN ('online', 'store', 'marketplace', 'wholesale')
            OR s.region = ''
            OR s.order_reference = '';
        """,
    )[0]

    duplicate_order_references = fetch_one(
        database_url,
        """
        SELECT COUNT(*)
        FROM (
            SELECT order_reference
            FROM sales
            GROUP BY order_reference
            HAVING COUNT(*) > 1
        ) duplicated_orders;
        """,
    )[0]

    assert invalid_sales == 0
    assert duplicate_order_references == 0


def test_inventory_snapshots_are_valid(database_url: str) -> None:
    invalid_inventory_rows = fetch_one(
        database_url,
        """
        SELECT COUNT(*)
        FROM inventory_snapshots i
        JOIN products p ON p.id = i.product_id
        WHERE i.stock_quantity < 0;
        """,
    )[0]

    assert invalid_inventory_rows == 0


# def test_inventory_snapshots_are_valid(database_url: str) -> None:
#     invalid_inventory_rows = fetch_one(
#         database_url,
#         """
#         SELECT COUNT(*)
#         FROM inventory_snapshots i
#         JOIN products p ON p.id = i.product_id
#         WHERE i.on_hand_quantity < 0
#             OR i.reserved_quantity < 0
#             OR i.reserved_quantity > i.on_hand_quantity
#             OR i.reorder_point < 0
#             OR i.safety_stock_quantity < 0
#             OR i.warehouse_code = '';
#         """,
#     )[0]

#     assert invalid_inventory_rows == 0


def test_forecasts_have_valid_product_links_and_windows(
    database_url: str,
) -> None:
    valid_forecasts = fetch_one(
        database_url,
        """
        SELECT COUNT(*)
        FROM forecasts f
        JOIN products p ON p.id = f.product_id
        WHERE f.forecast_period_start <= f.forecast_period_end
            AND f.predicted_quantity >= 0
            AND f.confidence_level >= 0
            AND f.confidence_level <= 1
            AND f.method <> ''
            AND f.status IN ('generated', 'evaluated', 'deprecated');
        """,
    )[0]

    assert valid_forecasts == EXPECTED_ROW_COUNTS["forecasts"]


def test_alerts_have_matching_recommendations(database_url: str) -> None:
    alerts_without_recommendation = fetch_one(
        database_url,
        """
        SELECT COUNT(*)
        FROM alerts a
        LEFT JOIN recommendations r ON r.alert_id = a.id
        WHERE r.id IS NULL;
        """,
    )[0]

    invalid_alerts = fetch_one(
        database_url,
        """
        SELECT COUNT(*)
        FROM alerts a
        JOIN products p ON p.id = a.product_id
        LEFT JOIN anomalies an ON an.id = a.anomaly_id
        WHERE an.id IS NULL
            OR a.alert_type NOT IN (
                'stale_inventory',
                'sales_drop',
                'stockout_risk'
                'overstock_risk'
            )
            OR a.severity NOT IN ('low', 'medium', 'high', 'critical')
            OR a.status NOT IN (
                'open',
                'acknowledged',
                'in_progress',
                'resolved'
            )
            OR a.title = ''
            OR a.recommended_action = '';
        """,
    )[0]

    assert alerts_without_recommendation == 0
    assert invalid_alerts == 0


def test_workflow_actions_have_actor_context(database_url: str) -> None:
    workflow_rows = fetch_all(
        database_url,
        """
        SELECT
            p.sku,
            a.alert_type,
            a.status AS alert_status,
            w.action_type,
            u.role AS actor_role,
            u.display_name AS actor_name,
            w.comment
        FROM workflow_actions w
        JOIN alerts a ON a.id = w.alert_id
        JOIN products p ON p.id = a.product_id
        JOIN users u ON u.id = w.performed_by_user_id
        ORDER BY w.created_at;
        """,
    )

    assert len(workflow_rows) == EXPECTED_ROW_COUNTS["workflow_actions"]
    allowed_roles = {
        "category_manager",
        "inventory_planner",
        "analyst",
        "admin",
    }

    assert all(row[4] in allowed_roles for row in workflow_rows)
    assert all(row[6] for row in workflow_rows)


def test_no_orphan_records_in_demo_dataset(database_url: str) -> None:
    orphan_count = fetch_one(
        database_url,
        """
        SELECT
            (
                SELECT COUNT(*)
                FROM sales s
                LEFT JOIN products p ON p.id = s.product_id
                WHERE p.id IS NULL
            )
            +
            (
                SELECT COUNT(*)
                FROM inventory_snapshots i
                LEFT JOIN products p ON p.id = i.product_id
                WHERE p.id IS NULL
            )
            +
            (
                SELECT COUNT(*)
                FROM forecasts f
                LEFT JOIN products p ON p.id = f.product_id
                WHERE p.id IS NULL
            )
            +
            (
                SELECT COUNT(*)
                FROM anomalies an
                LEFT JOIN products p ON p.id = an.product_id
                WHERE p.id IS NULL
            )
            +
            (
                SELECT COUNT(*)
                FROM alerts a
                LEFT JOIN products p ON p.id = a.product_id
                LEFT JOIN anomalies an ON an.id = a.anomaly_id
                WHERE p.id IS NULL OR an.id IS NULL
            )
            +
            (
                SELECT COUNT(*)
                FROM recommendations r
                LEFT JOIN products p ON p.id = r.product_id
                LEFT JOIN alerts a ON a.id = r.alert_id
                WHERE p.id IS NULL OR a.id IS NULL
            )
            +
            (
                SELECT COUNT(*)
                FROM workflow_actions w
                LEFT JOIN alerts a ON a.id = w.alert_id
                LEFT JOIN users u ON u.id = w.performed_by_user_id
                WHERE a.id IS NULL OR u.id IS NULL
            ) AS orphan_count;
        """,
    )[0]

    assert orphan_count == 0
