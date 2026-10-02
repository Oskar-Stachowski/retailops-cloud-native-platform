"""Snapshot 1.1 transports source 2.7; the frozen snapshot 1.0 stays separate."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from data.export.schema import table_schema as commerce_schema
from data.export.snapshot_contract import (
    FACT_TABLES as COMMERCE_FACTS,
)
from data.export.snapshot_contract import (
    ExporterProvenance,
    FileReference,
    LogicalTable,
    SnapshotID,
    SourceID,
    TableArtifact,
)
from data.inventory.qualification_contract import (  # noqa: TC001 - Pydantic resolves annotations at runtime
    QualificationDescriptor,
    QualificationId,
)
from data.inventory.replenishment_contract import SupplyRecord
from data.inventory.source_dataset_contract import (
    SOURCE_TABLES,
    SourceManifest,
    data_class,
    grain,
    table_schema_document,
)
from data.inventory.source_tables_contract import TABLES
from data.inventory.source_tables_io import table_schema as native_schema

if TYPE_CHECKING:
    import pyarrow as pa

VERSION = "1.1.0"
POLICY = "retailops-inventory-snapshot-1.0.0"
FORMAT = "retailops-parquet-1.1.0"
METADATA = {b"retailops.format": FORMAT.encode(), b"retailops.source_schema": b"2.7.0"}
FACT_TABLES = tuple(
    sorted({*COMMERCE_FACTS, *(n for n in TABLES if data_class(n) != "simulation_truth")})
)
TRUTH_TABLES = tuple(n for n in SOURCE_TABLES if data_class(n) == "simulation_truth")
GATES = (
    "dimension_schema_pk_sku",
    "selling_stock_channel_region",
    "assignment_routing_versions",
    "catalog_lifecycle_assortment",
    "calendar_exact_coverage",
    "category_season_coverage",
    "legacy_adapter_consistency",
    "sales_active_open_known_routing",
    "pricing_schema_versions_scope",
    "known_price_coverage_and_priority",
    "transaction_price_reconciliation",
    "realized_price_aggregates",
    "legacy_pricing_adapter",
    "promotion_truth_direction",
    "demand_schema",
    "daily_panel_coverage",
    "daily_transaction_aggregation",
    "basket_sku_totals",
    "daily_source_completeness",
    "returns_schema",
    "return_window_policy",
    "transaction_chronology",
    "return_reference_and_window",
    "return_quantity_and_refunds",
    "return_tail_completeness",
    "inventory_graph_and_projection",
    "commerce_inventory_parity",
    "inventory_configuration_binding",
    "historical_fulfillment_adapter",
    "private_supplier_realization",
    "known_fact_reorder_policy",
    "inventory_daily_demand_conservation",
    "causal_observation_and_finance_history",
    "private_simulation_parameters",
    "forecast_feature_projection",
    "inventory_known_completeness",
)
SCHEMAS = (
    "inventory_snapshot.v1_1.schema.json",
    "inventory_source_dataset.v2_7.schema.json",
    "inventory_source_tables.v1.schema.json",
    "inventory_label_qualification.v1.schema.json",
)
LEGACY_SCHEMAS = {
    "inventory_snapshot.v1_1.schema.json": "inventory_snapshot.legacy.v1_1.schema.json",
    "inventory_source_dataset.v2_7.schema.json": "inventory_source_dataset.legacy.v2_7.schema.json",
}


class Descriptor(SupplyRecord):
    role: Literal["source_snapshot"]
    identity_version: Literal["1.1.0"]
    policy_version: Literal["retailops-inventory-snapshot-1.0.0"]
    format_version: Literal["retailops-parquet-1.1.0"]
    parent_source_dataset_id: SourceID
    parent_qualification_id: QualificationId
    qualification: QualificationDescriptor
    required_use_cases: list[str]
    include_evaluation_truth: bool
    exporter_code_sha256: str
    dependency_sha256: str
    source_qualification_sha256: str
    schemas: dict[str, str]
    tables: list[LogicalTable]


class InventorySnapshot(SupplyRecord):
    schema_version: Literal["1.1.0"]
    snapshot_id: SnapshotID
    source_dataset_id: SourceID
    source_repository: Literal["retailops-cloud-native-platform"]
    generated_at: str
    snapshot_ready: Literal[True]
    descriptor: Descriptor
    source: SourceManifest
    exporter: ExporterProvenance
    tables: list[TableArtifact]
    metadata_files: list[FileReference]


def table_schema(name: str) -> pa.Schema:
    schema = native_schema(name) if name in TABLES else commerce_schema(name, "ai-smoke")
    return schema.with_metadata(METADATA)


def columns(name: str) -> list[dict]:
    return [
        {"name": f.name, "type": str(f.type), "nullable": f.nullable} for f in table_schema(name)
    ]


def snapshot_schema() -> dict:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        **InventorySnapshot.model_json_schema(by_alias=True),
    }


def handoff_contract() -> dict:
    specs = {
        n: {"schema": columns(n), "grain": grain(n), "data_class": data_class(n)}
        for n in (*FACT_TABLES, *TRUTH_TABLES)
    }
    return {
        "contract_version": VERSION,
        "producer": "retailops-cloud-native-platform",
        "supported_snapshot_versions": [VERSION],
        "supported_source_versions": ["2.7.0"],
        "export_policy_version": POLICY,
        "format_version": FORMAT,
        "arrow_metadata": {k.decode(): v.decode() for k, v in METADATA.items()},
        "fact_tables": {n: specs[n] for n in FACT_TABLES},
        "evaluation_truth_tables": {n: specs[n] for n in TRUTH_TABLES},
        "excluded_source_tables": sorted(set(SOURCE_TABLES) - set(specs)),
        "schema_files": list(SCHEMAS),
        "source_table_contract": table_schema_document(),
        "hard_gates": list(GATES),
        "reports": [
            "source_report.json",
            "source_report.md",
            "realism_report.json",
            "realism_report.md",
        ],
        "qualification_files": [
            "qualification_manifest.json",
            "qualification_report.json",
            "simulation_truth/inventory_qualified_windows.json",
        ],
    }
