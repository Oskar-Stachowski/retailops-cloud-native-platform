"""Snapshot 1.2 transports anomaly source 2.8 with explicit private scenario truth."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from data.anomalies.source_contract import (
    AnomalySourceManifest,  # noqa: TC001 - Pydantic runtime type
)
from data.anomalies.source_process import table_contract
from data.export import inventory_contract as base
from data.export.inventory_contract import Descriptor as InventoryDescriptor
from data.export.inventory_contract import InventorySnapshot

if TYPE_CHECKING:
    import pyarrow as pa

VERSION = "1.2.0"
POLICY = "retailops-anomaly-snapshot-1.0.0"
FORMAT = "retailops-parquet-1.2.0"
SOURCE_POLICY = "anomaly-source-acceptance-1.0.0"
USE_CASES = {"forecast_source", "inventory_source", "anomaly_source"}
HANDOFF = "source_snapshot_handoff.v1_2.json"
SCHEMAS = (
    "anomaly_snapshot.v1_2.schema.json",
    "anomaly_source_dataset.v2_8.schema.json",
    "inventory_source_tables.v1.schema.json",
    "inventory_label_qualification.v1.schema.json",
    "business_anomaly_plan.v1.schema.json",
    "business_physical_anomaly_plan.v1.schema.json",
)
GATES = (*base.GATES, "anomaly_process_replay", "anomaly_effect_reconciliation")
FACT_TABLES = base.FACT_TABLES
TRUTH_TABLES = base.TRUTH_TABLES


class Descriptor(InventoryDescriptor):
    identity_version: Literal["1.2.0"]  # type: ignore[assignment]  # explicit wire version override
    policy_version: Literal["retailops-anomaly-snapshot-1.0.0"]  # type: ignore[assignment]  # explicit wire version override
    format_version: Literal["retailops-parquet-1.2.0"]  # type: ignore[assignment]  # explicit wire version override


class AnomalySnapshot(InventorySnapshot):
    schema_version: Literal["1.2.0"]  # type: ignore[assignment]  # explicit wire version override
    descriptor: Descriptor
    source: AnomalySourceManifest


SnapshotManifest = AnomalySnapshot


def table_schema(name: str) -> pa.Schema:
    return base.table_schema(name).with_metadata(
        {b"retailops.format": FORMAT.encode(), b"retailops.source_schema": b"2.8.0"}
    )


def columns(name: str) -> list[dict]:
    return [
        {"name": f.name, "type": str(f.type), "nullable": f.nullable} for f in table_schema(name)
    ]


def snapshot_schema() -> dict:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        **AnomalySnapshot.model_json_schema(by_alias=True),
    }


def handoff_contract() -> dict:
    return {
        **base.handoff_contract(),
        "contract_version": VERSION,
        "supported_snapshot_versions": [VERSION],
        "supported_source_versions": ["2.8.0"],
        "export_policy_version": POLICY,
        "format_version": FORMAT,
        "source_policy_version": SOURCE_POLICY,
        "source_table_contract": table_contract(),
        "schema_files": list(SCHEMAS),
        "hard_gates": list(GATES),
        "arrow_metadata": {"retailops.format": FORMAT, "retailops.source_schema": "2.8.0"},
        "scenario_file": "evaluation_truth/anomaly_scenario.json",
        "configuration_file": "evaluation_truth/inventory_configuration.json",
        "supported_use_cases": sorted(USE_CASES),
    }
