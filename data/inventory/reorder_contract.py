from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import Field, ValidationError

from data.inventory.contract import Identifier, Reference, Timestamp, require, utc_timestamp
from data.inventory.replenishment_contract import Positive, SupplyRecord

POLICY_VERSION = "periodic-review-stock-position-1.0.0"


class ReorderRule(SupplyRecord):
    product_id: Identifier
    stock_location_id: Identifier
    reorder_point: Annotated[int, Field(ge=0)]
    safety_stock: Annotated[int, Field(ge=0)]
    review_cadence_days: Positive
    history_window_days: Positive
    minimum_order_quantity: Positive


class ReorderConfig(SupplyRecord):
    contract_version: Literal["reorder-config-1.0.0"]
    policy_version: Literal["periodic-review-stock-position-1.0.0"]
    business_timezone: Literal["UTC"]
    review_anchor_at: Timestamp
    known_at: Timestamp
    available_at: Timestamp
    rules: Annotated[list[ReorderRule], Field(min_length=1)]

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> ReorderConfig:
        try:
            parsed = cls.model_validate(payload)
        except ValidationError as error:
            msg = "Invalid reorder configuration contract."
            raise ValueError(msg) from error
        require(
            len({(r.product_id, r.stock_location_id) for r in parsed.rules}) == len(parsed.rules),
            "Duplicate reorder policy position.",
        )
        times = {
            f: utc_timestamp(getattr(parsed, f)).isoformat()
            for f in ("review_anchor_at", "known_at", "available_at")
        }
        require(times["known_at"] <= times["available_at"], "Policy is available before known.")
        return parsed.model_copy(
            update={
                **times,
                "rules": sorted(parsed.rules, key=lambda r: (r.product_id, r.stock_location_id)),
            }
        )


class HistoryCoverage(SupplyRecord):
    coverage_id: Identifier
    product_id: Identifier
    stock_location_id: Identifier
    covered_from_at: Timestamp
    covered_through_at: Timestamp
    available_at: Timestamp
    source_reference: Reference


class HistoryCoveragePayload(SupplyRecord):
    contract_version: Literal["inventory-history-coverage-1.0.0"]
    coverage_basis: Literal["observed_ledger_stream"]
    coverage: list[HistoryCoverage]


def parse_history_coverage(payload: dict[str, Any]) -> tuple[HistoryCoverage, ...]:
    try:
        parsed = HistoryCoveragePayload.model_validate(payload)
    except ValidationError as error:
        msg = "Invalid inventory history coverage contract."
        raise ValueError(msg) from error
    require(
        len({r.coverage_id for r in parsed.coverage}) == len(parsed.coverage),
        "Duplicate history coverage ID.",
    )
    rows = []
    for row in parsed.coverage:
        values = {
            f: utc_timestamp(getattr(row, f)).isoformat()
            for f in ("covered_from_at", "covered_through_at", "available_at")
        }
        require(
            values["covered_from_at"] < values["covered_through_at"] <= values["available_at"],
            "Invalid history coverage chronology.",
        )
        rows.append(row.model_copy(update=values))
    return tuple(sorted(rows, key=lambda r: (r.available_at, r.coverage_id)))


def reorder_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        **ReorderConfig.model_json_schema(),
    }


def history_coverage_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        **HistoryCoveragePayload.model_json_schema(),
    }
