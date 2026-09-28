from __future__ import annotations

from datetime import datetime
from typing import Any

FACT_INPUT_VERSION = "forecast-facts-1.0.0"
FACT_COLUMNS = {
    "daily_demand_observations": [
        "id",
        "business_date",
        "product_id",
        "selling_location_id",
        "channel",
        "observed_units",
        "observation_status",
        "available_at",
        "is_active_assortment",
        "location_open",
        "source_data_complete",
    ],
    "product_catalog": ["id", "category_id", "brand"],
    "catalog_categories": ["id", "name"],
}
HISTORY_INPUT_VERSION = "forecast-facts-2.0.0"
HISTORY_FACT_COLUMNS = {
    **FACT_COLUMNS,
    "daily_demand_versions": [
        "id",
        "observation_id",
        "business_date",
        "product_id",
        "selling_location_id",
        "channel",
        "version",
        "observed_units",
        "observation_status",
        "available_at",
    ],
}


def require(condition: bool, message: str) -> None:  # noqa: FBT001 - assertion helper
    if not condition:
        raise ValueError(message)


def timestamp(value: str) -> datetime:
    result = datetime.fromisoformat(value)
    require(
        result.tzinfo is not None and result.utcoffset().total_seconds() == 0,
        "Feature timestamps require UTC.",
    )
    return result


def validate_fact_input(payload: dict[str, Any]) -> dict:
    require(
        set(payload) == {"policy_version", "tables"}
        and payload["policy_version"] in {FACT_INPUT_VERSION, HISTORY_INPUT_VERSION},
        "Feature input policy/envelope disagree.",
    )
    tables = payload["tables"]
    columns_by_table = (
        HISTORY_FACT_COLUMNS if payload["policy_version"] == HISTORY_INPUT_VERSION else FACT_COLUMNS
    )
    require(
        isinstance(tables, dict) and set(tables) == set(columns_by_table),
        "Feature input allowlist rejects truth, inventory or unknown tables.",
    )
    for name, columns in columns_by_table.items():
        rows = tables[name]
        require(isinstance(rows, list) and bool(rows), "Required feature facts are empty.")
        for row in rows:
            require(
                isinstance(row, dict)
                and set(row) == set(columns)
                and all(isinstance(value, str) for value in row.values()),
                "Feature input allowlist rejects unknown or simulation fields.",
            )
        require(len({row["id"] for row in rows}) == len(rows), "Duplicate feature input ID.")
    products = {row["id"] for row in tables["product_catalog"]}
    categories = {row["id"] for row in tables["catalog_categories"]}
    require(
        all(row["category_id"] in categories for row in tables["product_catalog"])
        and all(row["product_id"] in products for row in tables["daily_demand_observations"]),
        "Feature input foreign keys disagree.",
    )
    return tables
