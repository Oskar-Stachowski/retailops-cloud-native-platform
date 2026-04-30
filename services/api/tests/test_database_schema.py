import os

import psycopg


DATABASE_URL = os.getenv("DATABASE_URL")


def test_required_database_tables_exist():
    assert DATABASE_URL is not None

    expected_tables = {
        "products",
        "users",
        "sales",
        "inventory_snapshots",
        "forecasts",
        "anomalies",
        "alerts",
        "recommendations",
        "workflow_actions",
        "alembic_version",
    }

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public';
                """
            )
            actual_tables = {row[0] for row in cur.fetchall()}

    assert expected_tables.issubset(actual_tables)


def test_required_database_columns_exist():
    assert DATABASE_URL is not None

    expected_columns = {
        "products": {"id", "sku", "name", "category", "brand", "status"},
        "users": {"id", "login", "display_name", "role", "team", "status"},
        "sales": {
            "id",
            "product_id",
            "quantity",
            "sold_at",
            "unit_price",
            "total_amount",
            "currency",
            "channel",
        },
        "inventory_snapshots": {
            "id",
            "product_id",
            "stock_quantity",
            "unit_of_measure",
            "warehouse_code",
            "recorded_at",
            "ingested_at",
        },
        "forecasts": {
            "id",
            "product_id",
            "forecast_period_start",
            "forecast_period_end",
            "predicted_quantity",
            "unit_of_measure",
            "generated_at",
            "method",
            "status",
            "confidence_level",
        },
        "anomalies": {
            "id",
            "product_id",
            "anomaly_type",
            "metric_name",
            "actual_value",
            "expected_value",
            "deviation_percent",
            "impact_value",
            "impact_unit",
            "severity",
            "period_start",
            "period_end",
            "detected_at",
        },
        "alerts": {
            "id",
            "product_id",
            "anomaly_id",
            "assigned_to_user_id",
            "alert_type",
            "severity",
            "status",
            "title",
            "recommended_action",
        },
        "recommendations": {
            "id",
            "product_id",
            "forecast_id",
            "anomaly_id",
            "alert_id",
            "recommendation_type",
            "recommended_action",
            "rationale",
            "status",
            "generated_at",
            "expires_at",
        },
        "workflow_actions": {
            "id",
            "alert_id",
            "performed_by_user_id",
            "action_type",
            "comment",
            "previous_status",
            "new_status",
            "performed_at",
        },
    }

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            for table_name, required_columns in expected_columns.items():
                cur.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = %s;
                    """,
                    (table_name,),
                )

                actual_columns = {row[0] for row in cur.fetchall()}

                assert required_columns.issubset(actual_columns), (
                    f"Missing columns in {table_name}. "
                    f"Expected at least {required_columns}, found {actual_columns}"
                )


def test_alembic_version_exists():
    assert DATABASE_URL is not None

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM alembic_version;")
            version_rows = cur.fetchone()[0]

    assert version_rows == 1
