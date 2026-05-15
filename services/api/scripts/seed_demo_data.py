from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from pathlib import Path

import psycopg
from psycopg import sql

from app.core.config import get_settings

SEED_DATA_PROFILES = ("demo", "small", "medium")
DEFAULT_SEED_DATA_PROFILE = "small"


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


def _profile_data_subdir(profile: str) -> Path:
    if profile == "demo":
        return Path("demo")

    return Path("synthetic") / profile


def resolve_seed_data_profile() -> str:
    profile = os.getenv("RETAILOPS_SEED_DATA_PROFILE")
    if profile is None and os.getenv("RETAILOPS_DEMO_DATA_DIR"):
        profile = "demo"

    profile = (profile or DEFAULT_SEED_DATA_PROFILE).strip().lower()
    if profile not in SEED_DATA_PROFILES:
        supported = "|".join(SEED_DATA_PROFILES)
        msg = (
            f"Unsupported RETAILOPS_SEED_DATA_PROFILE '{profile}'. "
            f"Supported profiles: {supported}."
        )
        raise ValueError(msg)

    return profile


def _candidate_data_dirs(profile: str) -> list[Path]:
    candidates: list[Path] = []
    data_subdir = _profile_data_subdir(profile)

    if os.getenv("RETAILOPS_SEED_DATA_DIR"):
        candidates.append(Path(os.environ["RETAILOPS_SEED_DATA_DIR"]))
    elif os.getenv("RETAILOPS_DEMO_DATA_DIR"):
        candidates.append(Path(os.environ["RETAILOPS_DEMO_DATA_DIR"]))

    script_path = Path(__file__).resolve()
    if len(script_path.parents) > 3:
        candidates.append(script_path.parents[3] / "data" / data_subdir)

    candidates.extend(
        [
            # Useful when the API container mounts ./data into /workspace/data.
            Path("/workspace/data") / data_subdir,
            # Useful when the project root is copied into the image.
            Path("/app/data") / data_subdir,
            # Useful when running from repo root.
            Path.cwd() / "data" / data_subdir,
            # Useful when running from services/api.
            Path.cwd().parents[1] / "data" / data_subdir
            if len(Path.cwd().parents) >= 2
            else Path.cwd() / "data" / data_subdir,
        ],
    )

    return candidates


def resolve_seed_data_dir(profile: str | None = None) -> Path:
    profile = profile or resolve_seed_data_profile()
    for candidate in _candidate_data_dirs(profile):
        if candidate.exists() and candidate.is_dir():
            return candidate

    searched = "\n".join(f"- {candidate}" for candidate in _candidate_data_dirs(profile))
    raise FileNotFoundError(
        f"Could not find seed CSV directory for profile '{profile}'. "
        "Run `python -m data.generator.main --profile "
        f"{profile}` from the repository root first, or set RETAILOPS_SEED_DATA_DIR.\n\n"
        "Searched:\n" + searched,
    )


def resolve_demo_data_dir() -> Path:
    return resolve_seed_data_dir("demo")


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
            msg = f"CSV file has no header: {csv_path}"
            raise ValueError(msg)

        missing_columns = sorted(set(columns) - set(reader.fieldnames))
        if missing_columns:
            msg = f"CSV file {csv_path} is missing required columns: {', '.join(missing_columns)}"
            raise ValueError(
                msg,
            )

        return [
            {column: normalize_csv_value(row.get(column)) for column in columns} for row in reader
        ]


def truncate_tables(cur: psycopg.Cursor) -> None:
    table_identifiers = sql.SQL(", ").join(sql.Identifier(table) for table in TRUNCATE_ORDER)
    cur.execute(sql.SQL("TRUNCATE TABLE {} RESTART IDENTITY CASCADE;").format(table_identifiers))


def seed_table_from_csv(
    cur: psycopg.Cursor,
    table_config: TableConfig,
    data_dir: Path,
) -> int:
    csv_path = data_dir / f"{table_config.name}.csv"

    if not csv_path.exists():
        msg = f"Missing CSV file for table {table_config.name}: {csv_path}"
        raise FileNotFoundError(msg)

    rows = load_csv_rows(csv_path, table_config.columns)
    if not rows:
        return 0

    column_identifiers = sql.SQL(", ").join(
        sql.Identifier(column) for column in table_config.columns
    )
    placeholders = sql.SQL(", ").join(sql.Placeholder() for _ in table_config.columns)

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
    data_dir = data_dir or resolve_seed_data_dir()
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
        msg = "DATABASE_URL is not configured."
        raise RuntimeError(msg)

    profile = resolve_seed_data_profile()
    data_dir = resolve_seed_data_dir(profile)
    seed_counts = seed_demo_data(settings.database_url, data_dir)

    print("\nSeed summary:")  # noqa: T201 - CLI output
    for table_config in TABLE_CONFIGS:
        print(f"- {table_config.name}: {seed_counts[table_config.name]}")  # noqa: T201 - CLI output
    print(f"\nSeed data profile: {profile}")  # noqa: T201 - CLI output
    print(f"Seed CSV directory: {data_dir}")  # noqa: T201 - CLI output
    print("Seed data inserted successfully.")  # noqa: T201 - CLI output


if __name__ == "__main__":
    main()
