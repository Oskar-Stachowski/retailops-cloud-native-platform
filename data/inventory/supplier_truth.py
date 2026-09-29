"""Generator-only supplier parameters; never imported by operational supply readers."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from data.inventory.contract import Identifier, require

SUPPLIER_TRUTH_VERSION = "supplier-simulation-truth-1.0.0"
NonnegativeDecimal = Annotated[str, Field(pattern=r"^(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$")]


class SupplierTruth(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    supplier_id: Identifier
    reliability: NonnegativeDecimal
    lead_time_mean_days: NonnegativeDecimal
    lead_time_std_days: NonnegativeDecimal


class SupplierTruthPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    contract_version: Literal["supplier-simulation-truth-1.0.0"]
    data_class: Literal["simulation_truth"]
    suppliers: Annotated[list[SupplierTruth], Field(min_length=1)]


def supplier_truth_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        **SupplierTruthPayload.model_json_schema(),
    }


def validate_supplier_truth(
    payload: dict[str, Any], supplier_ids: set[str]
) -> tuple[SupplierTruth, ...]:
    try:
        parsed = SupplierTruthPayload.model_validate(payload)
    except ValidationError as error:
        msg = "Invalid supplier simulation truth contract."
        raise ValueError(msg) from error
    rows = parsed.suppliers
    require(len(rows) == len({r.supplier_id for r in rows}), "Duplicate supplier truth ID.")
    require(
        {r.supplier_id for r in rows} == supplier_ids,
        "Supplier truth must exactly cover supplier IDs.",
    )
    require(
        all(Decimal(r.reliability) <= 1 for r in rows),
        "Supplier reliability must be between zero and one.",
    )
    return tuple(sorted(rows, key=lambda r: r.supplier_id))
