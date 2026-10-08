from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

# Pydantic resolves these annotations at runtime when building the schema.
from data.inventory.contract import (  # noqa: TC001
    Identifier,
    Product,
    Reference,
    StockLocation,
    Timestamp,
    Unit,
)

REPLENISHMENT_VERSION = "replenishment-1.0.0"
Date = Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2}$")]
Positive = Annotated[int, Field(gt=0)]
Money = Annotated[str, Field(pattern=r"^(?:0|[1-9][0-9]*)\.[0-9]{2}$")]


class SupplyRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class Supplier(SupplyRecord):
    supplier_id: Identifier
    supplier_code: Annotated[str, Field(pattern=r"^[A-Z0-9][A-Z0-9_-]*$")]
    country_code: Literal["PL", "DE"]
    status: Literal["active", "inactive"]
    minimum_order_quantity: Positive
    available_at: Timestamp


class ProductSupplier(SupplyRecord):
    product_supplier_id: Identifier
    product_id: Identifier
    supplier_id: Identifier
    unit_of_measure: Unit
    unit_cost: Money
    currency: Literal["PLN", "EUR"]
    priority: Positive
    effective_from: Date
    effective_to: Date
    quoted_lead_time_days: Annotated[int, Field(ge=0)]
    lead_time_basis: Literal["supplier_quote"]
    quote_reference: Reference
    known_at: Timestamp
    ingested_at: Timestamp
    available_at: Timestamp


class ReplenishmentOrder(SupplyRecord):
    replenishment_order_id: Identifier
    product_supplier_id: Identifier
    product_id: Identifier
    supplier_id: Identifier
    stock_location_id: Identifier
    ordered_quantity: Positive
    unit_of_measure: Unit
    ordered_at: Timestamp
    expected_delivery_at: Timestamp
    ingested_at: Timestamp
    available_at: Timestamp
    status: Literal["ordered"]
    source_reference: Reference


class DeliveryPlanVersion(SupplyRecord):
    plan_version_id: Identifier
    replenishment_order_id: Identifier
    version: Positive
    expected_delivery_at: Timestamp
    known_at: Timestamp
    ingested_at: Timestamp
    available_at: Timestamp
    source_reference: Reference


class ReplenishmentReceipt(SupplyRecord):
    receipt_id: Identifier
    replenishment_order_id: Identifier
    product_id: Identifier
    supplier_id: Identifier
    stock_location_id: Identifier
    received_quantity: Positive
    unit_of_measure: Unit
    received_at: Timestamp
    ingested_at: Timestamp
    available_at: Timestamp
    sequence: Annotated[int, Field(ge=0)]
    source_reference: Reference


class ReplenishmentPayload(SupplyRecord):
    contract_version: Literal["replenishment-1.0.0"]
    over_receipt_policy: Literal["reject"]
    products: Annotated[list[Product], Field(min_length=1)]
    stock_locations: Annotated[list[StockLocation], Field(min_length=1)]
    suppliers: Annotated[list[Supplier], Field(min_length=1)]
    product_suppliers: Annotated[list[ProductSupplier], Field(min_length=1)]
    replenishment_orders: list[ReplenishmentOrder]
    delivery_plan_versions: list[DeliveryPlanVersion]
    replenishment_receipts: list[ReplenishmentReceipt]


def replenishment_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        **ReplenishmentPayload.model_json_schema(),
    }


def parse_replenishment(payload: dict[str, Any]) -> ReplenishmentPayload:
    try:
        return ReplenishmentPayload.model_validate(payload)
    except ValidationError as error:
        first = error.errors(include_input=False)[0]
        location = "/".join(str(part) for part in first["loc"])
        msg = f"Replenishment contract violation at {location or '/'}: {first['msg']}"
        raise ValueError(msg) from error
