"""Private lifecycle/coverage qualification, separate from frozen source 2.7."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from data.inventory.contract import Identifier, Timestamp  # noqa: TC001 - runtime schema
from data.inventory.replenishment_contract import SupplyRecord
from data.inventory.source_dataset_contract import Artifact  # noqa: TC001

QUALIFICATION_VERSION = "inventory-label-qualification-1.0.0"
QUALIFICATION_POLICY = "active-physical-window-1.0.0"
MANIFEST = "qualification_manifest.json"
WINDOWS = "simulation_truth/inventory_qualified_windows.json"
REPORT = "qualification_report.json"
GRAIN = ("product_id", "stock_location_id", "origin")
Hash = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
SourceId = Annotated[str, Field(pattern=r"^source-sha256-[0-9a-f]{64}$")]
QualificationId = Annotated[str, Field(pattern=r"^inventory-labels-sha256-[0-9a-f]{64}$")]
Count = Annotated[int, Field(ge=0)]
Reason = Literal[
    "inactive_lifecycle",
    "inactive_assortment",
    "dimension_not_available",
    "route_missing",
    "calendar_missing",
    "inventory_unknown",
    "origin_state_unavailable",
    "incomplete_window",
    "outcomes_not_available",
    "window_inactive_lifecycle",
    "window_inactive_assortment",
    "window_dimension_not_available",
    "window_route_missing",
    "window_calendar_missing",
    "inventory_coverage_incomplete",
    "sales_coverage_incomplete",
]


class QualifiedWindow(SupplyRecord):
    product_id: Identifier
    stock_location_id: Identifier
    origin: Timestamp
    window_end_at: Timestamp
    evaluated_at: Timestamp
    status: Literal["evaluable", "already_stockout", "not_evaluable"]
    reason: Reason | None
    incident_stockout: Literal[0, 1] | None
    label_available_at: Timestamp | None
    origin_route_ids: list[Identifier]
    window_route_ids: list[Identifier]
    inventory_coverage_id: Identifier | None
    covered_sales_days: Count


class QualificationDescriptor(SupplyRecord):
    role: Literal["inventory_label_qualification"]
    schema_version: Literal["inventory-label-qualification-1.0.0"]
    policy_version: Literal["active-physical-window-1.0.0"]
    data_class: Literal["simulation_truth"]
    parent_source_id: SourceId
    evaluated_at: Timestamp
    horizon_days: Literal[7]
    grain: list[str]
    qualification_schema_sha256: Hash
    rows: Count
    windows_sha256: Hash
    report_sha256: Hash
    code_sha256: Hash
    dependency_sha256: Hash
    python_version: str


class QualificationManifest(SupplyRecord):
    schema_version: Literal["inventory-label-qualification-1.0.0"]
    qualification_id: QualificationId
    descriptor: QualificationDescriptor
    provenance: dict
    windows: Artifact
    report: Artifact
    source_ready: Literal[False]
    inventory_ready: Literal[False]
    model_ready: Literal[False]


def qualification_schema() -> dict:
    return {
        "contract_version": QUALIFICATION_VERSION,
        "policy_version": QUALIFICATION_POLICY,
        "grain": list(GRAIN),
        "data_class": "simulation_truth",
        "window": QualifiedWindow.model_json_schema(),
        "manifest": QualificationManifest.model_json_schema(),
    }
