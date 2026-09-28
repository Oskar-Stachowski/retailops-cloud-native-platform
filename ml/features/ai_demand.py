from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

from ml.features.fact_input import (
    FACT_COLUMNS,
    FACT_INPUT_VERSION,
    require,
    timestamp,
    validate_fact_input,
)

AI_FEATURE_COLUMNS = [
    "schema_version",
    "dataset_id",
    "feature_row_id",
    "date",
    "product_id",
    "selling_location_id",
    "channel",
    "units_sold",
    "observation_status",
    "observation_available_at",
    "is_active_assortment",
    "location_open",
    "source_data_complete",
    "category",
    "brand",
    "day_of_week",
    "is_weekend",
    "week_of_year",
    "month",
    "generated_at",
]
AI_FEATURE_SCHEMA_PATH = "ml/contracts/demand_forecast_features.v3.schema.json"


def validate_ai_records(rows: list[dict[str, Any]]) -> None:
    seen = set()
    for row in rows:
        require(
            set(row) == set(AI_FEATURE_COLUMNS) and row["schema_version"] == "3.0",
            "AI feature contract columns/version disagree.",
        )
        day = date.fromisoformat(row["date"])
        key = (row["date"], row["product_id"], row["selling_location_id"], row["channel"])
        require(
            key not in seen and row["feature_row_id"] == ":".join(key),
            "AI feature grain is duplicate or inconsistent.",
        )
        seen.add(key)
        for field in ("product_id", "selling_location_id"):
            require(
                bool(
                    re.fullmatch(
                        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", row[field]
                    )
                ),
                "AI feature entity ID is invalid.",
            )
        require(
            row["channel"] in {"online", "store", "marketplace", "wholesale"},
            "AI feature channel is invalid.",
        )
        status = row["observation_status"]
        require(
            status in {"observed_positive", "observed_zero", "closed", "missing"},
            "AI feature observation status is invalid.",
        )
        flags = {
            name: str(row[name]).lower()
            for name in (
                "source_data_complete",
                "is_active_assortment",
                "location_open",
                "is_weekend",
            )
        }
        require(
            all(value in {"true", "false"} for value in flags.values()),
            "AI feature flag must be boolean.",
        )
        require(
            flags["is_active_assortment"] == "true"
            and flags["source_data_complete"] == "true"
            and status != "missing",
            "Complete AI feature export cannot contain inactive/missing labels.",
        )
        require(str(row["units_sold"]).isdigit(), "AI feature label must be a nonnegative integer.")
        units = int(row["units_sold"])
        require(
            (units > 0) == (status == "observed_positive")
            and (flags["location_open"] == "false") == (status == "closed"),
            "AI feature label/status/closure disagree.",
        )
        require(
            (int(row["day_of_week"]), int(row["week_of_year"]), int(row["month"]))
            == (day.isoweekday(), day.isocalendar().week, day.month)
            and (flags["is_weekend"] == "true") == (day.weekday() >= 5),
            "AI feature calendar fields disagree.",
        )
        require(
            timestamp(row["observation_available_at"])
            >= timestamp((day + timedelta(days=1)).isoformat() + "T00:00:00+00:00"),
            "AI daily label cannot be available before source day close.",
        )


def ai_feature_rows(
    observations: list[dict[str, str]],
    catalog: list[dict[str, str]],
    categories: list[dict[str, str]],
) -> list[dict[str, Any]]:
    validate_fact_input(
        {
            "policy_version": FACT_INPUT_VERSION,
            "tables": {
                "daily_demand_observations": observations,
                "product_catalog": catalog,
                "catalog_categories": categories,
            },
        }
    )
    products, category_names = (
        {r["id"]: r for r in catalog},
        {r["id"]: r["name"] for r in categories},
    )
    generated = max((r["available_at"] for r in observations), default="")
    result = []
    for row in sorted(
        observations,
        key=lambda r: (r["business_date"], r["product_id"], r["selling_location_id"], r["channel"]),
    ):
        require(
            set(row) == set(FACT_COLUMNS["daily_demand_observations"]),
            "Feature observation allowlist rejects unknown or simulation fields.",
        )
        day, product = date.fromisoformat(row["business_date"]), products[row["product_id"]]
        require(
            row["is_active_assortment"] == "true",
            "Inactive combinations are excluded from features.",
        )
        require(
            row["observation_status"]
            in {"observed_positive", "observed_zero", "closed", "missing"},
            "Unknown observation status.",
        )
        require(
            (row["observation_status"] == "missing") == (row["source_data_complete"] == "false"),
            "Missing observations cannot claim completeness.",
        )
        units = None if row["observed_units"] == "" else int(row["observed_units"])
        require(
            (units is None) == (row["observation_status"] == "missing"),
            "Missing is unknown, never a zero label.",
        )
        timestamp(row["available_at"])
        key = (row["business_date"], row["product_id"], row["selling_location_id"], row["channel"])
        result.append(
            {
                "schema_version": "3.0",
                "dataset_id": "",
                "feature_row_id": ":".join(key),
                "date": key[0],
                "product_id": key[1],
                "selling_location_id": key[2],
                "channel": key[3],
                "units_sold": units,
                "observation_status": row["observation_status"],
                "observation_available_at": row["available_at"],
                "is_active_assortment": True,
                "location_open": row["location_open"] == "true",
                "source_data_complete": row["source_data_complete"] == "true",
                "category": category_names[product["category_id"]],
                "brand": product["brand"],
                "day_of_week": day.isoweekday(),
                "is_weekend": day.weekday() >= 5,
                "week_of_year": day.isocalendar().week,
                "month": day.month,
                "generated_at": generated,
            }
        )
    return result


def calendar_lag(
    rows: list[dict[str, Any]], series: tuple[str, str, str], first_target: date, days: int
) -> int | None:
    if days <= 0:
        msg = "Calendar lag must precede the origin date."
        raise ValueError(msg)
    origin_day = first_target - timedelta(days=1)
    wanted = (origin_day - timedelta(days=days)).isoformat()
    origin = timestamp(origin_day.isoformat() + "T23:59:59+00:00")
    matches = [
        r
        for r in rows
        if r["date"] == wanted
        and (r["product_id"], r["selling_location_id"], r["channel"]) == series
    ]
    require(len(matches) <= 1, "Duplicate calendar history grain.")
    if not matches:
        return None
    row = matches[0]
    if (
        row["observation_status"] not in {"observed_positive", "observed_zero"}
        or str(row["source_data_complete"]).lower() != "true"
        or timestamp(row["observation_available_at"]) > origin
    ):
        return None
    return int(row["units_sold"])
