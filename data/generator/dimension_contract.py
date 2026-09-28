from __future__ import annotations

import re
from typing import Any

from data.generator.dimension_schema import DIMENSION_COLUMNS, SKU_PATTERN

DATE_FIELDS = {"launch_date", "discontinue_date", "effective_from", "effective_to", "business_date"}
TIMESTAMP_FIELDS = {
    "available_at",
    "business_day_start_at",
    "business_day_end_at",
    "local_day_start_at",
    "local_day_end_at",
}
BOOLEAN_FIELDS = {
    "is_weekend",
    "is_public_holiday",
    "is_easter",
    "is_christmas",
    "is_black_friday",
    "is_cyber_monday",
    "location_open",
    "is_category_season",
}
COUNT_FIELDS = {"version", "pack_quantity", "day_of_week", "week_of_year", "month", "quarter"}
EMPTY_FIELDS = {"discontinue_date", "seasonal_months", "holiday_names"}
ENUMS = {
    "channel": ["store", "online", "marketplace", "wholesale"],
    "country_code": ["PL", "DE"],
    "calendar_jurisdiction": ["PL", "DE-BE"],
    "business_timezone": ["UTC"],
    "local_timezone": ["Europe/Warsaw", "Europe/Berlin"],
    "unit_of_measure": ["pcs"],
    "pack_unit": ["pcs", "g", "ml"],
    "currency": ["PLN"],
    "margin_band": ["low", "standard", "high"],
    "status": ["active", "inactive"],
    "location_type": ["warehouse"],
}


def field_rule(column: str) -> dict[str, Any]:
    rule: dict[str, Any] = {"type": "string", "minLength": 0 if column in EMPTY_FIELDS else 1}
    if column == "id" or column.endswith("_id"):
        rule["pattern"] = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    if column in DATE_FIELDS:
        rule["pattern"] = (
            r"^\d{4}-\d{2}-\d{2}$" if column != "discontinue_date" else r"^(?:\d{4}-\d{2}-\d{2})?$"
        )
    if column in TIMESTAMP_FIELDS:
        rule["format"] = "date-time"
    if column in COUNT_FIELDS:
        rule["pattern"] = r"^[1-9][0-9]*$"
    if column in BOOLEAN_FIELDS:
        rule["enum"] = ["true", "false"]
    if column in ENUMS:
        rule["enum"] = ENUMS[column]
    if column == "sku":
        rule["pattern"] = SKU_PATTERN
    if column == "unit_cost":
        rule["pattern"] = r"^[0-9]+\.[0-9]{2}$"
    return rule


def validate_dimension_row(name: str, row: dict[str, Any]) -> None:
    if set(row) != set(DIMENSION_COLUMNS[name]):
        msg = "Dimension columns disagree."
        raise ValueError(msg)
    for column, value in row.items():
        rule = field_rule(column)
        if (
            not isinstance(value, str)
            or len(value) < rule["minLength"]
            or ("enum" in rule and value not in rule["enum"])
            or ("pattern" in rule and not re.fullmatch(rule["pattern"], value))
        ):
            msg = "Invalid dimension value: " + column
            raise ValueError(msg)


def dimension_contract_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Retail dimensions 1.0.0 (CSV cells represented as strings)",
        "type": "object",
        "additionalProperties": False,
        "required": list(DIMENSION_COLUMNS),
        "properties": {
            name: {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": columns,
                    "properties": {column: field_rule(column) for column in columns},
                },
            }
            for name, columns in DIMENSION_COLUMNS.items()
        },
    }
