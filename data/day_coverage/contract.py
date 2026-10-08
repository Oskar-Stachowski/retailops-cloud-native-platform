"""Additive closure contract; the legacy transport and source schemas stay frozen."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from data.inventory.contract import Identifier, Timestamp
from data.inventory.replenishment_contract import Date, SupplyRecord
from data.inventory.source_dataset_contract import (  # noqa: TC001 - Pydantic schema
    SHA256,
    TableIdentity,
)

VERSION = "business-day-coverage-1.0.0"
POLICY = "synthetic-parent-event-day-close-1.0.0"
TABLES = (
    "daily_demand_observations",
    "inventory_sales",
    "product_catalog",
    "return_events",
    "return_policies",
)
MAX_ROWS = 10000
MAX_BYTES = 32 * 1024**2
IDs = Annotated[list[Identifier], Field(max_length=4096)]


class Day(SupplyRecord):
    event_type: Literal["sale_completed", "return_completed"]
    business_date: Date
    product_id: Identifier
    selling_location_id: Identifier
    channel: Literal["store", "online", "marketplace", "wholesale"]
    currency: Literal["PLN", "EUR"]
    window_end: Timestamp
    known_at: Timestamp
    source_complete: bool
    activity: Literal["open", "closed", "missing"]
    expected_business_ids: IDs
    required_sale_ids: IDs


class Descriptor(SupplyRecord):
    contract_version: Literal["business-day-coverage-1.0.0"]
    policy_version: Literal["synthetic-parent-event-day-close-1.0.0"]
    owner: Literal["retailops-cloud-native-platform"]
    source_dataset_id: Annotated[str, Field(pattern=r"^source-sha256-[0-9a-f]{64}$")]
    source_descriptor_sha256: SHA256
    source_tables: dict[str, TableIdentity]
    return_scope: Literal["purchases_in_parent_source_only"]
    return_closure_basis: Literal["verified_complete_synthetic_export_and_bounded_native_ingestion"]
    missing_grain_policy: Literal["unknown_not_zero"]
    cohort_maturity_is_day_closure: Literal[False]
    transport_durability_proven: Literal[False]
    code_sha256: SHA256
    dependency_sha256: SHA256
    python_version: str
    rows_sha256: SHA256
    row_count: Annotated[int, Field(ge=1, le=MAX_ROWS)]


class Manifest(SupplyRecord):
    coverage_id: Annotated[str, Field(pattern=r"^day-coverage-sha256-[0-9a-f]{64}$")]
    descriptor: Descriptor


def schemas() -> dict:
    return {
        name: {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            **model.model_json_schema(),
        }
        for name, model in (("day", Day), ("manifest", Manifest))
    }
