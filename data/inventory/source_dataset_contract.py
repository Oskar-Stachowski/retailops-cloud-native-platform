"""Versioned inventory source, separate from the frozen source 2.0-2.6 contracts."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from data.generator.csv_writer import source_columns
from data.generator.demand_schema import DEMAND_GRAINS
from data.generator.dimension_schema import DIMENSION_GRAINS
from data.generator.identity import source_data_class
from data.generator.manifest_v2 import (
    MANIFEST_V2_FILENAME,
    Provenance,
    RequestedParameters,
    ResolvedParameters,
)
from data.generator.pricing_schema import PRICING_GRAINS
from data.generator.return_schema import RETURN_GRAINS
from data.generator.simulation_schema import SIMULATION_GRAINS
from data.inventory.replenishment_contract import SupplyRecord
from data.inventory.source_bridge import COMMERCE_TABLES
from data.inventory.source_tables import TableContext  # noqa: TC001 - Pydantic schema
from data.inventory.source_tables_contract import TABLE_CONTRACT_VERSION, TABLES, field_rules

SOURCE_VERSION = "2.7.0"
SOURCE_POLICY = "inventory-source-acceptance-1.0.0"
GENERATOR_VERSION = "0.9.0"
FORECAST_GENERATOR_VERSION = "0.9.1"
MANIFEST_FILENAME = MANIFEST_V2_FILENAME
PRIVATE_TABLES = (
    "product_simulation_parameters",
    "store_simulation_parameters",
    "daily_demand_truth",
    "promotion_effect_truth",
)
SOURCE_TABLES = tuple(sorted({*COMMERCE_TABLES, *TABLES, *PRIVATE_TABLES}))
SHA256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Count = Annotated[int, Field(ge=0)]


def columns(name: str) -> list[str]:
    if name in TABLES:
        return list(field_rules(TABLES[name].model))
    return source_columns(name, "ai-smoke", "2.6.0")


def grain(name: str) -> list[str]:
    if name in TABLES:
        return list(TABLES[name].grain)
    return {
        **DIMENSION_GRAINS,
        **PRICING_GRAINS,
        **DEMAND_GRAINS,
        **RETURN_GRAINS,
        **SIMULATION_GRAINS,
        "daily_demand_versions": [
            "business_date",
            "product_id",
            "selling_location_id",
            "channel",
            "version",
        ],
    }.get(name, ["id"])


def data_class(name: str) -> str:
    if name in TABLES:
        return TABLES[name].data_class
    return source_data_class(name, "ai-smoke", "2.6.0")


def csv_path(name: str) -> str:
    directory = "simulation_truth" if data_class(name) == "simulation_truth" else "facts"
    return f"{directory}/{name}.csv"


class TableIdentity(SupplyRecord):
    row_count: Count
    columns: list[str]
    grain: list[str]
    data_class: Literal["source_observation", "source_plan", "simulation_truth"]
    content_sha256: SHA256


class Artifact(SupplyRecord):
    path: str
    sha256: SHA256
    size_bytes: Count


class ForecastRequestedParameters(RequestedParameters):
    forecast_plan_days: Annotated[int, Field(ge=1, le=14)]
    forecast_plan_version: Literal["known-forecast-plans-1.0.0"]


class ForecastResolvedParameters(ResolvedParameters):
    forecast_plan_days: Annotated[int, Field(ge=1, le=14)]
    forecast_plan_version: Literal["known-forecast-plans-1.0.0"]


class ForecastWatermark(SupplyRecord):
    as_of_time: str
    complete_through: str | None
    completeness_status: Literal["complete", "not_ready"]
    meaning: Literal["synthetic_sales_day_close_without_return_guarantee"]
    policy_version: Literal["daily-demand-1.0.0"]


class SourceDescriptor(SupplyRecord):
    identity_version: Literal["inventory-source-identity-1.0.0"]
    role: Literal["source"]
    owner: Literal["retailops-cloud-native-platform"]
    schema_version: Literal["2.7.0"]
    generator_version: Literal["0.9.0", "0.9.1"]
    table_contract_version: Literal["inventory-source-tables-1.0.0"]
    source_policy_version: Literal["inventory-source-acceptance-1.0.0"]
    canonicalization_version: Literal["inventory-source-typed-csv-1.0.0"]
    table_schema_sha256: SHA256
    resolved_parameters: ResolvedParameters | ForecastResolvedParameters
    forecast_watermarks: dict[Literal["daily_demand_observations"], ForecastWatermark] | None = (
        Field(default=None, exclude_if=lambda value: value is None)
    )
    inventory_configuration_sha256: SHA256
    context: TableContext
    code_sha256: SHA256
    dependency_sha256: SHA256
    python_version: str
    tables: dict[str, TableIdentity]


class SourceManifest(SupplyRecord):
    schema_version: Literal["2.7.0"]
    dataset_name: Literal["retailops-synthetic"]
    dataset_id: Annotated[str, Field(pattern=r"^source-sha256-[0-9a-f]{64}$")]
    descriptor: SourceDescriptor
    requested_parameters: RequestedParameters | ForecastRequestedParameters
    provenance: Provenance
    generated_at: str
    artifacts: dict[str, Artifact]
    inventory_configuration: Artifact
    reports: dict[str, Artifact]
    facts_ready: bool
    source_ready: Literal[False]
    inventory_ready: Literal[False]
    model_ready: Literal[False]
    publication_status: Literal["awaiting_ai03_handoff"]


def source_schema() -> dict:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        **SourceManifest.model_json_schema(),
    }


def table_schema_document() -> dict:
    return {
        "source_version": SOURCE_VERSION,
        "native_table_contract": TABLE_CONTRACT_VERSION,
        "tables": {
            name: {
                "columns": columns(name),
                "grain": grain(name),
                "data_class": data_class(name),
                "native_fields": field_rules(TABLES[name].model) if name in TABLES else None,
            }
            for name in SOURCE_TABLES
        },
    }
