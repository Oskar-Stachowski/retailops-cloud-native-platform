"""Separate bounded capture v2 for all canonical sales and native return claims."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, TypeAdapter

from data.dq.contract import MAX_BODY_BYTES, FaultPlan, seal_record
from data.generator.identity import canonical_json
from data.inventory.contract import Timestamp, require, utc_timestamp
from data.inventory.replenishment_contract import SupplyRecord
from data.inventory.source_dataset_contract import (  # noqa: TC001 - Pydantic runtime annotations
    SHA256,
    TableIdentity,
)

PLAN_VERSION = "raw-dq-plan-2.0.0"
GENERATOR_VERSION = "raw-dq-generator-2.0.0"
CAPTURE_VERSION = "raw-dq-capture-2.0.0"
REPLAY_VERSION = "operational-offline-replay-2.0.0"
MAX_CANONICAL_EVENTS = 4096
MAX_EVENTS = 8192
MAX_RECORDS = 16384
MAX_ARTIFACT_BYTES = 32 * 1024 * 1024
SCOPE = "all_parent_sales_and_return_claims"


class FullFaultPlan(FaultPlan):
    contract_version: Literal["raw-dq-plan-2.0.0"]  # type: ignore[assignment]  # separate wire version
    generator_version: Literal["raw-dq-generator-2.0.0"]  # type: ignore[assignment]  # separate wire version
    event_limit: Annotated[int, Field(ge=12, le=MAX_CANONICAL_EVENTS)]


class FullBinding(SupplyRecord):
    contract_version: Literal["raw-dq-binding-2.0.0"]
    source_dataset_id: Annotated[str, Field(pattern=r"^source-sha256-[0-9a-f]{64}$")]
    source_descriptor_sha256: SHA256
    source_events_sha256: SHA256
    source_event_count: Annotated[int, Field(ge=12, le=MAX_CANONICAL_EVENTS)]
    source_sales_count: Annotated[int, Field(ge=0, le=MAX_CANONICAL_EVENTS)]
    source_return_count: Annotated[int, Field(ge=0, le=MAX_CANONICAL_EVENTS)]
    source_facts_ready: Literal[True]
    selection_policy: Literal["all_canonical_sales_and_native_return_claims_v1"]
    projection: Literal["legacy_operational_sales_and_returns_allowlist_v1"]
    scope: Literal["all_parent_sales_and_return_claims"]
    projection_tables: Annotated[
        dict[
            Literal[
                "sales",
                "orders",
                "sale_price_references",
                "products",
                "inventory_sales",
                "return_events",
            ],
            TableIdentity,
        ],
        Field(min_length=6, max_length=6),
    ]
    return_scope: Literal["purchases_in_parent_source_only"]
    return_status_source: Literal["verified_native_parent_not_refund_amount_inference"]
    business_event_day_completeness: Literal["not_qualified"]
    missing_grain_policy: Literal["unknown_not_zero"]

    @classmethod
    def from_payload(cls, payload: dict) -> FullBinding:
        value = cls.model_validate(payload)
        require(
            canonical_json(payload) == canonical_json(value.model_dump()),
            "Noncanonical full binding.",
        )
        require(
            value.source_dataset_id == "source-sha256-" + value.source_descriptor_sha256,
            "Full source descriptor identity differs.",
        )
        require(
            value.source_event_count == value.source_sales_count + value.source_return_count,
            "Full event count does not cover every parent fact.",
        )
        require(
            value.projection_tables["sales"].row_count == value.source_sales_count
            and value.projection_tables["return_events"].row_count == value.source_return_count,
            "Full projection table counts differ.",
        )
        return value


class PortfolioFaultPlan(FullFaultPlan):
    contract_version: Literal["raw-dq-plan-2.1.0"]  # type: ignore[assignment]
    event_limit: Annotated[int, Field(ge=12, le=8192)]


class PortfolioBinding(FullBinding):
    contract_version: Literal["raw-dq-binding-2.1.0"]  # type: ignore[assignment]
    source_event_count: Annotated[int, Field(ge=12, le=8192)]
    source_sales_count: Annotated[int, Field(ge=0, le=8192)]
    source_return_count: Annotated[int, Field(ge=0, le=8192)]


def parse_full_plan(payload: dict) -> FullFaultPlan:
    model = (
        PortfolioFaultPlan
        if payload.get("contract_version") == "raw-dq-plan-2.1.0"
        else FullFaultPlan
    )
    return model.from_payload(payload)


class FullRecord(SupplyRecord):
    contract_version: Literal["raw-dq-capture-2.0.0"]
    record_id: Annotated[str, Field(pattern=r"^raw-record-sha256-[0-9a-f]{64}$")]
    received_at: Timestamp


class FullEventDelivery(FullRecord):
    kind: Literal["event"]
    topic: Literal["retailops.sales.v1"]
    partition: Literal[0]
    offset: Annotated[int, Field(ge=0, lt=MAX_EVENTS)]
    body_utf8: Annotated[str, Field(max_length=MAX_BODY_BYTES)]


class FullProgressDeclaration(FullRecord):
    kind: Literal["progress"]
    scope: Literal["all_parent_sales_and_return_claims"]
    after_offset: Annotated[int, Field(ge=-1, lt=MAX_EVENTS)]
    complete_through: Timestamp


Capture = Annotated[FullEventDelivery | FullProgressDeclaration, Field(discriminator="kind")]
ADAPTER = TypeAdapter(Capture)


def parse_record(payload: dict) -> FullEventDelivery | FullProgressDeclaration:
    value = ADAPTER.validate_python(payload)
    normalized = value.model_dump()
    require(canonical_json(payload) == canonical_json(normalized), "Noncanonical full capture.")
    require(
        normalized == seal_record({k: v for k, v in normalized.items() if k != "record_id"}),
        "Full capture identity differs.",
    )
    utc_timestamp(value.received_at)
    if isinstance(value, FullEventDelivery):
        require(len(value.body_utf8.encode()) <= MAX_BODY_BYTES, "Raw body exceeds budget.")
    else:
        require(
            utc_timestamp(value.complete_through) <= utc_timestamp(value.received_at),
            "Progress declaration precedes its frontier.",
        )
    return value


def plan_schema() -> dict:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        **FullFaultPlan.model_json_schema(),
    }


def capture_schema() -> dict:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", **ADAPTER.json_schema()}


def binding_schema() -> dict:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        **FullBinding.model_json_schema(),
    }
