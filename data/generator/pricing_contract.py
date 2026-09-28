from __future__ import annotations

import re
from typing import Any

from data.generator.dimension_contract import field_rule
from data.generator.pricing_schema import (
    PRICING_COLUMNS,
    PRICING_VERSION,
    PROMOTION_POLICIES,
    SCOPE_RANK,
    STACKING_POLICY,
    TRUTH_VERSION,
)

EMPTY_FIELDS = {
    "selling_location_id",
    "promotion_plan_id",
    "promotion_plan_ids",
    "realized_unit_price",
}
MONEY_FIELDS = {"price", "discount_percent", "gross_revenue", "realized_unit_price"}


def pricing_field_rule(column: str) -> dict[str, Any]:
    rule = field_rule(column)
    if column in {"known_at", "as_of_time"}:
        rule["format"] = "date-time"
    if column in EMPTY_FIELDS:
        rule["minLength"] = 0
        if "pattern" in rule:
            rule["pattern"] = r"^(?:" + rule["pattern"].removeprefix("^").removesuffix("$") + r")?$"
    if column in MONEY_FIELDS:
        rule["pattern"] = (
            r"^[0-9]+\.[0-9]{2}$" if column != "realized_unit_price" else r"^(?:[0-9]+\.[0-9]{2})?$"
        )
    if column in {"minimum_quantity", "priority"}:
        rule["pattern"] = r"^[1-9][0-9]*$"
    if column == "quantity":
        rule["pattern"] = r"^(?:0|[1-9][0-9]*)$"
    if column == "demand_multiplier":
        rule["pattern"] = r"^[0-9]+\.[0-9]{4}$"
    enums = {
        "channel": ["all", "store", "online", "marketplace", "wholesale"],
        "scope": list(SCOPE_RANK),
        "promotion_type": list(PROMOTION_POLICIES),
        "stacking_policy": [STACKING_POLICY],
        "status": ["active", "cancelled"],
        "phase": ["pre", "during", "post"],
        "pricing_policy_version": [PRICING_VERSION],
        "truth_policy_version": [TRUTH_VERSION],
    }
    if column in enums:
        rule["enum"] = enums[column]
    return rule


def validate_pricing_row(name: str, row: dict[str, Any]) -> None:
    if set(row) != set(PRICING_COLUMNS[name]):
        msg = "Pricing columns disagree."
        raise ValueError(msg)
    for column, value in row.items():
        rule = pricing_field_rule(column)
        if (
            not isinstance(value, str)
            or len(value) < rule["minLength"]
            or ("pattern" in rule and not re.fullmatch(rule["pattern"], value))
            or ("enum" in rule and value not in rule["enum"])
        ):
            msg = "Invalid pricing value: " + column
            raise ValueError(msg)


def pricing_contract_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Retail pricing 1.0.0 (CSV cells represented as strings)",
        "type": "object",
        "additionalProperties": False,
        "required": list(PRICING_COLUMNS),
        "properties": {
            name: {
                "type": "array",
                "minItems": 1 if name == "price_plans" else 0,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": columns,
                    "properties": {column: pricing_field_rule(column) for column in columns},
                },
            }
            for name, columns in PRICING_COLUMNS.items()
        },
    }
