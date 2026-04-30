import os

import psycopg


DATABASE_URL = os.getenv("DATABASE_URL")


def test_demo_seed_data_exists():
    assert DATABASE_URL is not None

    expected_counts = {
        "products": 8,
        "users": 4,
        "sales": 8,
        "inventory_snapshots": 6,
        "forecasts": 4,
        "anomalies": 4,
        "alerts": 4,
        "recommendations": 4,
        "workflow_actions": 4,
    }

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            for table_name, expected_count in expected_counts.items():
                cur.execute(f"SELECT COUNT(*) FROM {table_name};")
                actual_count = cur.fetchone()[0]

                assert actual_count == expected_count, (
                    f"Expected {expected_count} rows in {table_name}, "
                    f"but found {actual_count}"
                )
