from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from data.generator.common import deterministic_uuid
from data.generator.dimension_contract import field_rule
from data.generator.dimension_quality import require
from data.generator.simulation_schema import (
    PRODUCT_PARAMETERS,
    SIMULATION_COLUMNS,
    SIMULATION_VERSION,
    STORE_PARAMETERS,
    fact_columns,
)


def separate_simulation(tables: dict) -> None:
    from data.generator.csv_writer import TABLE_COLUMNS  # noqa: PLC0415 - schema cycle

    for name, identity, parameters in (
        ("products", "product_id", PRODUCT_PARAMETERS),
        ("stores", "legacy_store_id", STORE_PARAMETERS),
    ):
        target = (
            "product_simulation_parameters" if name == "products" else "store_simulation_parameters"
        )
        tables[target] = [
            {
                "id": deterministic_uuid(target, row["id"]),
                identity: row["id"],
                **{field: row[field] for field in parameters},
                "simulation_policy_version": SIMULATION_VERSION,
            }
            for row in tables[name]
        ]
    for name in ("products", "stores", "sales"):
        columns = fact_columns(name, TABLE_COLUMNS[name])
        tables[name] = [{field: row[field] for field in columns} for row in tables[name]]


def simulation_entities(tables: dict, name: str) -> list[dict[str, str]]:
    target, identity = (
        ("product_simulation_parameters", "product_id")
        if name == "products"
        else ("store_simulation_parameters", "legacy_store_id")
    )
    if target not in tables:
        return tables[name]
    params = {row[identity]: row for row in tables[target]}
    columns = PRODUCT_PARAMETERS if name == "products" else STORE_PARAMETERS
    return [
        {**row, **{field: params[row["id"]][field] for field in columns}} for row in tables[name]
    ]


def simulation_field_rule(column: str) -> dict[str, Any]:
    rule = field_rule(column)
    if column in {"demand_weight", "price_elasticity", "return_rate", *STORE_PARAMETERS}:
        rule["pattern"] = r"^[0-9]+(?:\.[0-9]+)?$"
    enums = {
        "demand_class": [
            "hero_product",
            "core_product",
            "seasonal",
            "new_product",
            "declining_product",
            "clearance_product",
            "long_tail",
        ],
        "seasonal_pattern": [
            "seasonal_peak",
            "holiday_peak",
            "spring_summer_peak",
            "stable",
            "weekly_sensitive",
        ],
        "simulation_policy_version": [SIMULATION_VERSION],
    }
    if column in enums:
        rule["enum"] = enums[column]
    return rule


def validate_simulation(tables: dict) -> int:
    count = 0
    for name, columns in SIMULATION_COLUMNS.items():
        rows = tables[name]
        identity, facts = (
            ("product_id", "products")
            if name.startswith("product")
            else ("legacy_store_id", "stores")
        )
        require(len({r["id"] for r in rows}) == len(rows), "Duplicate simulation primary key.")
        require(
            len({r[identity] for r in rows}) == len(rows)
            and {r[identity] for r in rows} == {r["id"] for r in tables[facts]},
            "Simulation parameters must cover every entity exactly once.",
        )
        for row in rows:
            require(set(row) == set(columns), "Simulation columns disagree.")
            for field, value in row.items():
                rule = simulation_field_rule(field)
                require(
                    isinstance(value, str)
                    and len(value) >= rule["minLength"]
                    and ("pattern" not in rule or bool(re.fullmatch(rule["pattern"], value)))
                    and ("enum" not in rule or value in rule["enum"]),
                    "Invalid simulation parameter: " + field,
                )
            if "return_rate" in row:
                require(Decimal(row["return_rate"]) <= 1, "Return rate exceeds one.")
            count += 1
    return count


def simulation_contract_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Retail simulation parameters 1.0.0 (string CSV cells)",
        "type": "object",
        "additionalProperties": False,
        "required": list(SIMULATION_COLUMNS),
        "properties": {
            name: {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": columns,
                    "properties": {field: simulation_field_rule(field) for field in columns},
                },
            }
            for name, columns in SIMULATION_COLUMNS.items()
        },
    }
