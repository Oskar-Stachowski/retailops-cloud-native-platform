from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

LEDGER_VERSION = "inventory-ledger-1.0.0"
LEGACY_ADAPTER_VERSION = "inventory-ledger-to-legacy-1.0.0"
UTC_TIMESTAMP_PATTERN = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)$"
MOVEMENT_PROCESSES = {
    "opening_stock": "opening",
    "replenishment_received": "replenishment",
    "sale": "sale",
    "return_to_stock": "return",
    "write_off": "write_off",
    "transfer_in": "transfer",
    "transfer_out": "transfer",
    "inventory_adjustment": "adjustment",
}
POSITIVE_MOVEMENTS = {"replenishment_received", "return_to_stock", "transfer_in"}
NEGATIVE_MOVEMENTS = {"sale", "write_off", "transfer_out"}


def require(condition: bool, message: str) -> None:  # noqa: FBT001 - validation predicate
    if not condition:
        raise ValueError(message)


def utc_timestamp(value: str) -> datetime:
    require(
        isinstance(value, str) and re.fullmatch(UTC_TIMESTAMP_PATTERN, value) is not None,
        "Inventory timestamps require explicit UTC and at most microsecond precision.",
    )
    try:
        stamp = datetime.fromisoformat(value)
    except ValueError as error:
        msg = "Inventory timestamps must be valid ISO timestamps."
        raise ValueError(msg) from error
    require(
        stamp.tzinfo is not None and stamp.utcoffset() == UTC.utcoffset(stamp),
        "Inventory timestamps require an explicit UTC offset.",
    )
    return stamp.astimezone(UTC)


Identifier = Annotated[
    str, Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
]
Unit = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*$")]
Timestamp = Annotated[str, Field(pattern=UTC_TIMESTAMP_PATTERN)]
Reference = Annotated[str, Field(min_length=1, pattern=r"\S")]


class _Record(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class Product(_Record):
    id: Identifier
    unit_of_measure: Unit


class StockLocation(_Record):
    id: Identifier
    location_code: Reference


class InventoryPosition(_Record):
    product_id: Identifier
    stock_location_id: Identifier


class MovementRecord(_Record):
    inventory_event_id: Identifier
    product_id: Identifier
    stock_location_id: Identifier
    movement_type: Literal[
        "opening_stock",
        "replenishment_received",
        "sale",
        "return_to_stock",
        "write_off",
        "transfer_in",
        "transfer_out",
        "inventory_adjustment",
    ]
    quantity_delta: int
    unit_of_measure: Unit
    occurred_at: Timestamp
    ingested_at: Timestamp
    available_at: Timestamp
    sequence: Annotated[int, Field(ge=0)]
    source_process: Literal[
        "opening", "replenishment", "sale", "return", "write_off", "transfer", "adjustment"
    ]
    source_reference: Reference
    transfer_id: Identifier | None
    supplier_id: Identifier | None
    order_id: Identifier | None


class LedgerPayload(_Record):
    contract_version: Literal["inventory-ledger-1.0.0"]
    opening_policy: Literal["single_opening_movement"]
    reservation_policy: Literal["none"]
    opening_at: Timestamp
    products: Annotated[list[Product], Field(min_length=1)]
    stock_locations: Annotated[list[StockLocation], Field(min_length=1)]
    inventory_scope: Annotated[list[InventoryPosition], Field(min_length=1)]
    movements: Annotated[list[MovementRecord], Field(min_length=1)]


def ledger_contract_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        **LedgerPayload.model_json_schema(),
    }


def validate_structure(payload: dict[str, Any]) -> None:
    try:
        LedgerPayload.model_validate(payload)
    except ValidationError as error:
        first = error.errors(include_input=False)[0]
        location = "/".join(str(part) for part in first["loc"])
        msg = f"Inventory contract violation at {location or '/'}: {first['msg']}"
        raise ValueError(msg) from error
