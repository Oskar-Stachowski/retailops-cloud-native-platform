"""Closed snapshot manifest and explicit AI 03.2 export policy."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from data.generator.manifest_v2 import (
    SHA256,
    Contract,
    Count,
    DataClass,
    DateRange,
    SourceManifestV2,
)

POLICY_VERSION = "retailops-ai-snapshot-1.0.0"
MANIFEST_NAME = "snapshot_manifest.json"
FACT_TABLES = (
    "products",
    "stores",
    "warehouses",
    "orders",
    "order_items",
    "sales",
    "catalog_categories",
    "product_catalog",
    "selling_locations",
    "stock_locations",
    "channel_assignments",
    "fulfillment_routes",
    "assortment",
    "business_calendar",
    "category_calendar",
    "price_plans",
    "promotion_plans",
    "sale_price_references",
    "daily_price_observations",
    "daily_demand_observations",
    "daily_demand_exclusions",
    "return_policies",
    "return_events",
    "daily_return_cohorts",
    "daily_demand_versions",
)
TRUTH_TABLES = (
    "promotion_effect_truth",
    "daily_demand_truth",
    "product_simulation_parameters",
    "store_simulation_parameters",
)
CONTRACT_FILES = (
    "retailops_seed_dataset.contract.json",
    "retail_dimensions.v1.schema.json",
    "retail_pricing.v1.schema.json",
    "retail_demand.v1.schema.json",
    "retail_returns.v1.schema.json",
    "observation_history.v1.schema.json",
    "source_dataset_manifest.v2.schema.json",
    "ai_snapshot.v1.schema.json",
)
USE_CASES = ("forecast_source", "forecasting", "anomaly", "stockout", "replay", "rag")
SourceID = Annotated[str, Field(pattern=r"^source-sha256-[0-9a-f]{64}$")]
SnapshotID = Annotated[str, Field(pattern=r"^snapshot-sha256-[0-9a-f]{64}$")]


class Column(Contract):
    name: str
    type: str
    nullable: bool


class LogicalTable(Contract):
    table: str
    data_class: DataClass
    row_count: Count
    content_sha256: SHA256
    grain: list[str]
    date_range: DateRange
    field_ranges: dict[str, DateRange]
    column_schema: list[Column] = Field(alias="schema")


class FileReference(Contract):
    path: str
    bytes: Count
    sha256: SHA256


class ParquetReference(FileReference):
    row_count: Count


class TableArtifact(LogicalTable):
    partition_source_field: str | None
    files: Annotated[list[ParquetReference], Field(min_length=1)]


class SnapshotDescriptor(Contract):
    role: Literal["source_snapshot"]
    identity_version: Literal["1.0.0"]
    policy_version: Literal["retailops-ai-snapshot-1.0.0"]
    format_version: Literal["retailops-parquet-1.0.0"]
    parent_source_dataset_id: SourceID
    required_use_cases: list[str]
    include_evaluation_truth: bool
    exporter_code_sha256: SHA256
    dependency_sha256: SHA256
    source_qualification_sha256: SHA256
    schemas: dict[str, SHA256]
    tables: list[LogicalTable]


class ExporterProvenance(Contract):
    git_commit: str
    python_version: str
    pyarrow_version: str
    code_files: dict[str, SHA256]
    dependency_sha256: SHA256


class SnapshotManifest(Contract):
    schema_version: Literal["1.0.0"]
    snapshot_id: SnapshotID
    source_dataset_id: SourceID
    source_repository: Literal["retailops-cloud-native-platform"]
    generated_at: str
    snapshot_ready: Literal[True]
    descriptor: SnapshotDescriptor
    source: SourceManifestV2
    exporter: ExporterProvenance
    tables: list[TableArtifact]
    metadata_files: list[FileReference]
