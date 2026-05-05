from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from pathlib import Path

import psycopg
from psycopg import sql

from app.core.config import get_settings


@dataclass(frozen=True)
class TableConfig:
    name: str
    columns: tuple[str, ...]


TABLE_CONFIGS: tuple[TableConfig, ...] = (
    TableConfig(
        "products",
        ("id", "sku", "name", "category", "brand", "status"),
    ),
    TableConfig(
        "users",
        ("id", "login", "display_name", "role", "team", "status"),
    ),
    TableConfig(
        "sales",
        (
            "id",
            "product_id",
            "quantity",
            "unit_price",
            "total_amount",
            "currency",
            "channel",
            "region",
            "sold_at",
            "order_reference",
        ),
    ),
    TableConfig(
        "inventory_snapshots",
        (
            "id",
            "product_id",
            "stock_quantity",
            "unit_of_measure",
            "warehouse_code",
            "recorded_at",
            "ingested_at",
            "created_at",
        ),
    ),
    TableConfig(
        "forecasts",
        (
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
        ),
    ),
    TableConfig(
        "anomalies",
        (
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
        ),
    ),
    TableConfig(
        "alerts",
        (
            "id",
            "product_id",
            "anomaly_id",
            "assigned_to_user_id",
            "alert_type",
            "severity",
            "status",
            "title",
            "recommended_action",
            "created_at",
            "updated_at",
        ),
    ),
    TableConfig(
        "recommendations",
        (
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
            "created_at",
        ),
    ),
    TableConfig(
        "workflow_actions",
        (
            "id",
            "alert_id",
            "performed_by_user_id",
            "action_type",
            "comment",
            "previous_status",
            "new_status",
            "performed_at",
            "created_at",
        ),
    ),
)

TRUNCATE_ORDER = tuple(reversed([table.name for table in TABLE_CONFIGS]))


def _candidate_data_dirs() -> list[Path]:
    candidates: list[Path] = []

    if os.getenv("RETAILOPS_DEMO_DATA_DIR"):
        candidates.append(Path(os.environ["RETAILOPS_DEMO_DATA_DIR"]))

    script_path = Path(__file__).resolve()
    if len(script_path.parents) > 3:
        candidates.append(script_path.parents[3] / "data" / "demo")

    candidates.extend(
        [
            # Useful when the API container mounts ./data into /workspace/data.
            Path("/workspace/data/demo"),
            # Useful when the project root is copied into the image.
            Path("/app/data/demo"),
            # Useful when running from repo root.
            Path.cwd() / "data" / "demo",
            # Useful when running from services/api.
            Path.cwd().parents[1] / "data" / "demo"
            if len(Path.cwd().parents) >= 2
            else Path.cwd() / "data" / "demo",
        ]
    )

    return candidates


def resolve_demo_data_dir() -> Path:
    for candidate in _candidate_data_dirs():
        if candidate.exists() and candidate.is_dir():
            return candidate

    searched = "\n".join(
        f"- {candidate}" for candidate in _candidate_data_dirs()
    )
    raise FileNotFoundError(
        "Could not find demo CSV directory. "
        "Run `python -m data.generator.main` from the repository root first, "
        "or set RETAILOPS_DEMO_DATA_DIR.\n\nSearched:\n"
        + searched
    )


def normalize_csv_value(value: str | None) -> str | None:
    if value is None:
        return None

    stripped = value.strip()
    return stripped or None


def load_csv_rows(
    csv_path: Path,
    columns: tuple[str, ...],
) -> list[dict[str, str | None]]:
    with csv_path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        if reader.fieldnames is None:
            raise ValueError(f"CSV file has no header: {csv_path}")

        missing_columns = sorted(set(columns) - set(reader.fieldnames))
        if missing_columns:
            raise ValueError(
                f"CSV file {csv_path} is missing required columns: "
                f"{', '.join(missing_columns)}"
            )

        rows = []
        for row in reader:
            rows.append(
                {
                    column: normalize_csv_value(row.get(column))
                    for column in columns
                }
            )

        return rows


def truncate_tables(cur: psycopg.Cursor) -> None:
    table_identifiers = sql.SQL(", ").join(
        sql.Identifier(table) for table in TRUNCATE_ORDER
    )
    cur.execute(
        sql.SQL("TRUNCATE TABLE {} RESTART IDENTITY CASCADE;").format(
            table_identifiers
        )
    )


def seed_table_from_csv(
    cur: psycopg.Cursor,
    table_config: TableConfig,
    data_dir: Path,
) -> int:
    csv_path = data_dir / f"{table_config.name}.csv"

    if not csv_path.exists():
        raise FileNotFoundError(
            f"Missing CSV file for table {table_config.name}: {csv_path}"
        )

    rows = load_csv_rows(csv_path, table_config.columns)
    if not rows:
        return 0

    column_identifiers = sql.SQL(", ").join(
        sql.Identifier(column) for column in table_config.columns
    )
    placeholders = sql.SQL(", ").join(
        sql.Placeholder() for _ in table_config.columns
    )

    query = sql.SQL("INSERT INTO {} ({}) VALUES ({});").format(
        sql.Identifier(table_config.name),
        column_identifiers,
        placeholders,
    )

    values = [[row[column] for column in table_config.columns] for row in rows]
    cur.executemany(query, values)

    return len(rows)


def seed_demo_data(
    database_url: str,
    data_dir: Path | None = None,
) -> dict[str, int]:
    data_dir = data_dir or resolve_demo_data_dir()
    seed_counts: dict[str, int] = {}

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            truncate_tables(cur)

            for table_config in TABLE_CONFIGS:
                seed_counts[table_config.name] = seed_table_from_csv(
                    cur,
                    table_config,
                    data_dir,
                )

        conn.commit()

    return seed_counts


def main() -> None:
    settings = get_settings()

    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is not configured.")

    data_dir = resolve_demo_data_dir()
    seed_counts = seed_demo_data(settings.database_url, data_dir)

    print("\nSeed summary:")
    for table_config in TABLE_CONFIGS:
        print(f"- {table_config.name}: {seed_counts[table_config.name]}")
    print(f"\nDemo CSV directory: {data_dir}")
    print("Demo seed data inserted successfully.")


if __name__ == "__main__":
    main()
