from __future__ import annotations

import csv
from pathlib import Path

TABLE_COLUMNS: dict[str, list[str]] = {
    "products": ["id", "sku", "name", "category", "brand", "status"],
    "users": ["id", "login", "display_name", "role", "team", "status"],
    "sales": [
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
    ],
    "inventory_snapshots": [
        "id",
        "product_id",
        "stock_quantity",
        "unit_of_measure",
        "warehouse_code",
        "recorded_at",
        "ingested_at",
        "created_at",
    ],
    "forecasts": [
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
    ],
    "anomalies": [
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
    ],
    "alerts": [
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
    ],
    "recommendations": [
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
    ],
    "workflow_actions": [
        "id",
        "alert_id",
        "performed_by_user_id",
        "action_type",
        "comment",
        "previous_status",
        "new_status",
        "performed_at",
        "created_at",
    ],
}

CSV_WRITE_ORDER = list(TABLE_COLUMNS.keys())


def write_csv(
    path: Path,
    rows: list[dict[str, str]],
    columns: list[str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=columns,
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)


def write_tables(
    output_dir: Path,
    tables: dict[str, list[dict[str, str]]],
) -> dict[str, int]:
    counts: dict[str, int] = {}

    for table_name in CSV_WRITE_ORDER:
        rows = tables[table_name]
        columns = TABLE_COLUMNS[table_name]
        write_csv(output_dir / f"{table_name}.csv", rows, columns)
        counts[table_name] = len(rows)

    return counts
