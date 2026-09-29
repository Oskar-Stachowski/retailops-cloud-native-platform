"""Explicit Arrow types for source 2.6; no inference or floating point money."""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal

import pyarrow as pa

from data.generator.csv_writer import source_columns
from data.generator.identity import (
    BOOLEAN_FIELDS,
    DECIMAL_FIELDS,
    INTEGER_FIELDS,
    TIME_FIELDS,
    canonical_cell,
)

FORMAT_VERSION = "retailops-parquet-1.0.0"
DATE_FIELDS = {
    "business_date",
    "launch_date",
    "discontinue_date",
    "effective_from",
    "effective_to",
    "valid_from",
    "valid_to",
    "starts_at",
    "ends_at",
    "forecast_period_start",
    "forecast_period_end",
    "date",
}
MONEY_FIELDS = {
    "price",
    "unit_price",
    "total_amount",
    "order_total",
    "refund_amount",
    "discount_percent",
    "unit_cost",
    "gross_revenue",
    "net_revenue",
    "realized_unit_price",
    "impact_value",
}
# Nullability expresses the source's empty-cell semantics, including missing demand.
NULLABLE_FIELDS = {
    "valid_to",
    "expires_at",
    "discontinue_date",
    "seasonal_months",
    "holiday_names",
    "forecast_id",
    "anomaly_id",
    "alert_id",
    "assigned_to_user_id",
    "previous_status",
    "promotion_plan_id",
    "promotion_plan_ids",
    "comment",
}
TABLE_NULLABLE = {
    "price_plans": {"selling_location_id"},
    "promotion_plans": {"selling_location_id"},
    "daily_price_observations": {"realized_unit_price"},
    "daily_demand_observations": {
        "observed_units",
        "observed_orders",
        "gross_revenue",
        "net_revenue",
        "return_units",
        "realized_unit_price",
    },
    "daily_demand_versions": {"observed_units"},
}


def field_type(field: str) -> pa.DataType:
    if field in BOOLEAN_FIELDS:
        return pa.bool_()
    if field in INTEGER_FIELDS:
        return pa.int64()
    if field in DECIMAL_FIELDS:
        # Truth factors use up to 28 significant Decimal digits, including very small rates.
        return pa.decimal128(38, 2) if field in MONEY_FIELDS else pa.decimal256(76, 40)
    if field in DATE_FIELDS:
        return pa.date32()
    if field in TIME_FIELDS:
        return pa.timestamp("us", tz="UTC")
    return pa.string()


def table_schema(table: str, profile: str) -> pa.Schema:
    nullable = NULLABLE_FIELDS | TABLE_NULLABLE.get(table, set())
    return pa.schema(
        [
            pa.field(field, field_type(field), nullable=field in nullable)
            for field in source_columns(table, profile)
        ],
        metadata={
            b"retailops.format": FORMAT_VERSION.encode(),
            b"retailops.source_schema": b"2.6.0",
        },
    )


def typed_row(row: dict, schema: pa.Schema) -> dict:
    if set(row) != set(schema.names):
        msg = "CSV record width/columns disagree with the explicit schema."
        raise ValueError(msg)
    result = {}
    for field in schema:
        if pa.types.is_timestamp(field.type) and re.search(r"\.\d{7,}", str(row[field.name])):
            msg = "Timestamp exceeds the declared microsecond precision."
            raise ValueError(msg)
        value = canonical_cell(field.name, row[field.name])
        if value is None:
            if not field.nullable:
                msg = "Forbidden null: " + field.name
                raise ValueError(msg)
        elif pa.types.is_decimal(field.type):
            value = Decimal(value)
            if value != Decimal(row[field.name]):
                msg = "Numeric value exceeds the source canonicalization precision."
                raise ValueError(msg)
        elif pa.types.is_date(field.type):
            value = date.fromisoformat(value)
        elif pa.types.is_timestamp(field.type):
            value = datetime.fromisoformat(value)
        result[field.name] = value
    return result
