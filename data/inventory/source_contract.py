"""Explicit configuration for the unpublished source-commerce integration."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import Field, ValidationError

from data.inventory.contract import require
from data.inventory.replenishment_contract import Positive, SupplyRecord
from data.inventory.supplier_fulfillment import FulfillmentConfig
from data.inventory.supplier_truth import NonnegativeDecimal  # noqa: TC001 - schema annotation

SOURCE_INVENTORY_VERSION = "source-inventory-commerce-1.0.0"


class SourceStockPolicy(SupplyRecord):
    opening_quantity: Annotated[int, Field(ge=0)]
    reorder_point: Annotated[int, Field(ge=0)]
    safety_stock: Annotated[int, Field(ge=0)]
    history_window_days: Positive
    review_cadence_days: Positive
    minimum_order_quantity: Positive
    quoted_lead_time_days: Annotated[int, Field(ge=0)]


class SourceSupplierParameters(SupplyRecord):
    data_class: Literal["simulation_truth"]
    reliability: NonnegativeDecimal
    lead_time_mean_days: NonnegativeDecimal
    lead_time_std_days: NonnegativeDecimal


class SourceInventoryConfig(SupplyRecord):
    contract_version: Literal["source-inventory-config-1.0.0"]
    process_version: Literal["source-inventory-commerce-1.0.0"]
    business_timezone: Literal["UTC"]
    reservation_policy: Literal["none"]
    return_quality_policy: Literal["refunded_undamaged_returns_only"]
    return_tail_policy: Literal["financial_tail_without_inventory_extension"]
    stock: SourceStockPolicy
    sale_ingestion_delay_seconds: Annotated[int, Field(ge=0)]
    sale_availability_delay_seconds: Annotated[int, Field(ge=0)]
    return_inventory_ingestion_delay_seconds: Annotated[int, Field(ge=0)]
    return_inventory_availability_delay_seconds: Annotated[int, Field(ge=0)]
    supplier_parameters: SourceSupplierParameters
    fulfillment: FulfillmentConfig

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> SourceInventoryConfig:
        try:
            config = cls.model_validate(payload)
        except ValidationError as error:
            msg = "Invalid source inventory configuration."
            raise ValueError(msg) from error
        FulfillmentConfig.from_payload(config.fulfillment.model_dump())
        require(
            Decimal(config.supplier_parameters.reliability) <= 1,
            "Supplier reliability must not exceed one.",
        )
        return config


def source_inventory_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        **SourceInventoryConfig.model_json_schema(),
    }
