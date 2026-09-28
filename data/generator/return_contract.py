from __future__ import annotations

import re
from typing import Any

from data.generator.dimension_contract import field_rule
from data.generator.dimension_quality import timestamp
from data.generator.return_schema import RETURN_COLUMNS, RETURNS_VERSION


def return_field_rule(column: str) -> dict[str, Any]:
    rule = field_rule(column)
    if column in {"window_days", "max_ingestion_delay_days", "quantity"}:
        rule["pattern"] = r"^[1-9][0-9]*$"
    if column in {"observed_units", "return_units", "net_units"}:
        rule["pattern"] = r"^(?:0|[1-9][0-9]*)$"
    if column in {"gross_revenue", "refund_amount", "net_revenue"}:
        rule["pattern"] = r"^[0-9]+\.[0-9]{2}$"
    if column in {"known_at", "returned_at", "ingested_at", "available_at", "as_of_time"}:
        rule["format"] = "date-time"
    enums = {
        "status": ["refunded", "rejected"],
        "reason": ["wrong_size", "damaged", "changed_mind", "not_as_described", "defective"],
        "snapshot_kind": ["history", "return_tail"],
        "return_data_complete": ["true", "false"],
        "returns_policy_version": [RETURNS_VERSION],
    }
    if column in enums:
        rule["enum"] = enums[column]
    return rule


def validate_return_row(name: str, row: dict[str, Any]) -> None:
    if set(row) != set(RETURN_COLUMNS[name]):
        msg = "Return columns disagree."
        raise ValueError(msg)
    for column, value in row.items():
        rule = return_field_rule(column)
        if (
            not isinstance(value, str)
            or len(value) < rule["minLength"]
            or ("pattern" in rule and not re.fullmatch(rule["pattern"], value))
            or ("enum" in rule and value not in rule["enum"])
        ):
            msg = "Invalid return value: " + column
            raise ValueError(msg)
        if rule.get("format") == "date-time":
            timestamp(value)


def return_contract_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Retail returns 1.0.0 (string CSV cells)",
        "type": "object",
        "additionalProperties": False,
        "required": list(RETURN_COLUMNS),
        "properties": {
            name: {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": columns,
                    "properties": {column: return_field_rule(column) for column in columns},
                },
            }
            for name, columns in RETURN_COLUMNS.items()
        },
    }
