from __future__ import annotations

import re
from typing import Any

from data.generator.demand_schema import DEMAND_COLUMNS, DEMAND_VERSION
from data.generator.dimension_contract import field_rule

OPTIONAL = {
    "observed_units",
    "observed_orders",
    "gross_revenue",
    "net_revenue",
    "return_units",
    "realized_unit_price",
    "promotion_plan_ids",
}
COUNTS = {"observed_units", "observed_orders", "return_units", "latent_units"}
MONEY = {"gross_revenue", "net_revenue", "realized_unit_price"}
FLAGS = {"source_data_complete", "return_data_complete", "is_active_assortment", "location_open"}


def demand_field_rule(column: str) -> dict[str, Any]:
    rule = field_rule(column)
    if column in OPTIONAL:
        rule["minLength"] = 0
    if column in COUNTS:
        rule["pattern"] = r"^(?:0|[1-9][0-9]*)$"
    if column in MONEY:
        rule["pattern"] = r"^[0-9]+\.[0-9]{2}$"
    if column in OPTIONAL and "pattern" in rule:
        rule["pattern"] = r"^(?:" + rule["pattern"].removeprefix("^").removesuffix("$") + r")?$"
    enums = {
        "observation_status": [
            "observed_positive",
            "observed_zero",
            "closed",
            "missing",
            "inactive",
        ],
        "quality_status": ["valid", "incomplete"],
        "exclusion_reason": ["inactive_lifecycle", "inactive_assignment", "inactive_assortment"],
        "demand_policy_version": [DEMAND_VERSION],
        **{flag: ["true", "false"] for flag in FLAGS},
    }
    if column in enums:
        rule["enum"] = enums[column]
    return rule


def validate_demand_row(name: str, row: dict[str, Any]) -> None:
    if set(row) != set(DEMAND_COLUMNS[name]):
        msg = "Demand columns disagree."
        raise ValueError(msg)
    for column, value in row.items():
        rule = demand_field_rule(column)
        if (
            not isinstance(value, str)
            or len(value) < rule["minLength"]
            or ("pattern" in rule and not re.fullmatch(rule["pattern"], value))
            or ("enum" in rule and value not in rule["enum"])
        ):
            msg = "Invalid demand value: " + column
            raise ValueError(msg)


def demand_contract_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Daily demand 1.0.0 (string CSV cells)",
        "type": "object",
        "additionalProperties": False,
        "required": list(DEMAND_COLUMNS),
        "properties": {
            name: {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": columns,
                    "properties": {column: demand_field_rule(column) for column in columns},
                },
            }
            for name, columns in DEMAND_COLUMNS.items()
        },
    }
