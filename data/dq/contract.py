"""Versioned private fault plans and separately typed raw delivery metadata."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, TypeAdapter

from data.generator.identity import canonical_json, json_sha256
from data.inventory.contract import Identifier, Timestamp, require, utc_timestamp
from data.inventory.replenishment_contract import SupplyRecord
from data.inventory.source_dataset_contract import (
    SHA256,  # noqa: TC001 - Pydantic runtime annotation
)

PLAN_VERSION = "raw-dq-plan-1.0.0"
GENERATOR_VERSION = "raw-dq-generator-1.0.0"
REPLAY_VERSION = "sales-offline-replay-1.0.0"
TOPIC = "retailops.sales.v1"
MAX_EVENTS = 1024
MAX_RECORDS = 2048
MAX_BODY_BYTES = 64 * 1024
KINDS = (
    "exact_duplicate",
    "business_duplicate",
    "late_event",
    "out_of_order",
    "missing_optional_context",
    "unsupported_major",
    "unsupported_minor",
    "unexpected_additive_field",
)
Issue = Literal[
    "exact_duplicate",
    "business_duplicate",
    "late_event",
    "out_of_order",
    "missing_optional_context",
    "unsupported_major",
    "unsupported_minor",
    "unexpected_additive_field",
]


class Injection(SupplyRecord):
    injection_id: Identifier
    target_event_id: Identifier
    issue_type: Issue
    deliver_after_event_id: Identifier | None = None


class FaultPlan(SupplyRecord):
    contract_version: Literal["raw-dq-plan-1.0.0"]
    generator_version: Literal["raw-dq-generator-1.0.0"]
    data_class: Literal["simulation_truth"]
    seed: int
    source_dataset_id: Annotated[str, Field(pattern=r"^source-sha256-[0-9a-f]{64}$")]
    source_events_sha256: SHA256
    event_limit: Annotated[int, Field(ge=12, le=512)]
    overlap_policy: Literal["reject_target_or_anchor_overlap"]
    injections: Annotated[list[Injection], Field(min_length=1, max_length=100)]

    @classmethod
    def from_payload(cls, payload: dict) -> FaultPlan:
        value = cls.model_validate(payload)
        ids = [i.injection_id for i in value.injections]
        targets = [i.target_event_id for i in value.injections]
        anchors = [i.deliver_after_event_id for i in value.injections if i.deliver_after_event_id]
        require(len(ids) == len(set(ids)), "Duplicate DQ injection ID.")
        require(len(targets) == len(set(targets)), "Overlapping DQ targets.")
        require(len(anchors) == len(set(anchors)), "Overlapping DQ anchors.")
        for injection in value.injections:
            delayed = injection.issue_type in {"late_event", "out_of_order"}
            require(delayed == bool(injection.deliver_after_event_id), "DQ timing anchor differs.")
            require(injection.deliver_after_event_id not in targets, "DQ anchor is also a target.")
        return value.model_copy(
            update={"injections": sorted(value.injections, key=lambda i: i.injection_id)}
        )


class CaptureRecord(SupplyRecord):
    record_id: Annotated[str, Field(pattern=r"^raw-record-sha256-[0-9a-f]{64}$")]
    received_at: Timestamp


class EventDelivery(CaptureRecord):
    kind: Literal["event"]
    topic: Literal["retailops.sales.v1"]
    partition: Literal[0]
    offset: Annotated[int, Field(ge=0, lt=MAX_EVENTS)]
    body_utf8: Annotated[str, Field(max_length=MAX_BODY_BYTES)]


class ProgressDeclaration(CaptureRecord):
    kind: Literal["progress"]
    scope: Literal["selected_sales_fixture"]
    after_offset: Annotated[int, Field(ge=-1, lt=MAX_EVENTS)]
    complete_through: Timestamp


Capture = Annotated[EventDelivery | ProgressDeclaration, Field(discriminator="kind")]
CAPTURE_ADAPTER = TypeAdapter(Capture)


def seal_record(payload: dict) -> dict:
    require("record_id" not in payload, "Record identity cannot hash itself.")
    return {"record_id": "raw-record-sha256-" + json_sha256(payload), **payload}


def parse_record(payload: dict) -> EventDelivery | ProgressDeclaration:
    record = CAPTURE_ADAPTER.validate_python(payload)
    normalized = record.model_dump()
    require(
        canonical_json(normalized) == canonical_json(payload),
        "Noncanonical raw capture fields/types.",
    )
    require(
        normalized == seal_record({k: v for k, v in normalized.items() if k != "record_id"}),
        "Raw capture identity differs.",
    )
    utc_timestamp(record.received_at)
    if isinstance(record, EventDelivery):
        require(len(record.body_utf8.encode("utf-8")) <= MAX_BODY_BYTES, "Raw body exceeds budget.")
    else:
        require(
            utc_timestamp(record.complete_through) <= utc_timestamp(record.received_at),
            "Progress declaration precedes its event-time frontier.",
        )
    return record


def plan_schema() -> dict:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        **FaultPlan.model_json_schema(),
    }


def capture_schema() -> dict:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        **CAPTURE_ADAPTER.json_schema(),
    }
