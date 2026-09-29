"""Native inventory table extension, separate from the immutable source 2.6 contract."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

from data.inventory.contract import (
    Identifier,
    InventoryPosition,
    MovementRecord,
    Product,
    StockLocation,
    Timestamp,
)
from data.inventory.projection_contract import (
    Count,
    InventorySnapshot,
    LostSalesImpact,
    PhysicalDailyBalance,
    StockoutEpisode,
    WindowDiagnostic,
)
from data.inventory.reorder_contract import HistoryCoverage, ReorderRule
from data.inventory.replenishment_contract import (
    DeliveryPlanVersion,
    Money,
    Positive,
    ProductSupplier,
    ReplenishmentOrder,
    ReplenishmentReceipt,
    Supplier,
    SupplyRecord,
)
from data.inventory.simulation_contract import (
    Channel,
    DemandArrival,
    ExecutedSale,
    FulfillmentRoute,
    ProcessedReturn,
    SellingLocation,
)

TABLE_CONTRACT_VERSION = "inventory-source-tables-1.0.0"


class ReturnInventoryDecision(SupplyRecord):
    return_id: Identifier
    sale_id: Identifier
    product_id: Identifier
    stock_location_id: Identifier
    quantity: Positive
    quality_status: Literal["accepted", "rejected"]
    inventory_disposition: Literal[
        "not_refunded", "outside_inventory_window", "restocked", "quality_rejected"
    ]
    returned_at: Timestamp
    financial_available_at: Timestamp
    inventory_available_at: Timestamp | None


class FinancialReturn(SupplyRecord):
    id: Identifier
    sale_id: Identifier
    order_id: Identifier
    order_item_id: Identifier
    product_id: Identifier
    selling_location_id: Identifier
    channel: Channel
    policy_id: Identifier
    quantity: Positive
    refund_amount: Money
    currency: Literal["PLN", "EUR"]
    reason: Literal["wrong_size", "damaged", "changed_mind", "not_as_described", "defective"]
    status: Literal["refunded", "rejected"]
    returned_at: Timestamp
    ingested_at: Timestamp
    available_at: Timestamp
    returns_policy_version: Literal["retail-returns-1.0.0"]


class RouteVersion(SupplyRecord):
    route_id: Identifier
    source_version: Positive
    inventory_revision: Positive


class DemandOutcome(SupplyRecord):
    demand_id: Identifier
    product_id: Identifier
    stock_location_id: Identifier
    selling_location_id: Identifier
    channel: Channel
    occurred_at: Timestamp
    sequence: Count
    latent_quantity: Count
    observed_quantity: Count
    lost_sales_quantity: Count
    stock_before: Count
    stock_after: Count
    reason: Literal["no_demand", "inventory_constraint", "fulfilled"]


class SupplierSample(SupplyRecord):
    order_id: Identifier
    simulation_id: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    disrupted: bool
    lead_days: Positive


@dataclass(frozen=True)
class TableDefinition:
    model: type[BaseModel]
    grain: tuple[str, ...]
    data_class: Literal["source_observation", "source_plan", "simulation_truth"]


TABLES = {
    "inventory_products": TableDefinition(Product, ("id",), "source_observation"),
    "inventory_stock_locations": TableDefinition(StockLocation, ("id",), "source_observation"),
    "inventory_scope": TableDefinition(
        InventoryPosition, ("product_id", "stock_location_id"), "source_plan"
    ),
    "inventory_ledger": TableDefinition(
        MovementRecord, ("inventory_event_id",), "source_observation"
    ),
    "inventory_selling_locations": TableDefinition(SellingLocation, ("id",), "source_observation"),
    "inventory_fulfillment_routes": TableDefinition(FulfillmentRoute, ("id",), "source_plan"),
    "inventory_route_versions": TableDefinition(RouteVersion, ("route_id",), "source_plan"),
    "suppliers": TableDefinition(Supplier, ("supplier_id",), "source_plan"),
    "product_suppliers": TableDefinition(ProductSupplier, ("product_supplier_id",), "source_plan"),
    "replenishment_orders": TableDefinition(
        ReplenishmentOrder, ("replenishment_order_id",), "source_observation"
    ),
    "delivery_plan_versions": TableDefinition(
        DeliveryPlanVersion, ("plan_version_id",), "source_plan"
    ),
    "replenishment_receipts": TableDefinition(
        ReplenishmentReceipt, ("receipt_id",), "source_observation"
    ),
    "inventory_sales": TableDefinition(ExecutedSale, ("sale_id",), "source_observation"),
    "inventory_returns": TableDefinition(ProcessedReturn, ("return_id",), "source_observation"),
    "return_events": TableDefinition(FinancialReturn, ("id",), "source_observation"),
    "return_inventory_decisions": TableDefinition(
        ReturnInventoryDecision, ("return_id",), "source_observation"
    ),
    "inventory_history_coverage": TableDefinition(
        HistoryCoverage, ("coverage_id",), "source_observation"
    ),
    "inventory_reorder_rules": TableDefinition(
        ReorderRule, ("product_id", "stock_location_id"), "source_plan"
    ),
    "inventory_daily_snapshots": TableDefinition(
        InventorySnapshot,
        ("product_id", "stock_location_id", "business_date"),
        "source_observation",
    ),
    "inventory_demand_arrivals": TableDefinition(DemandArrival, ("demand_id",), "simulation_truth"),
    "inventory_demand_outcomes": TableDefinition(DemandOutcome, ("demand_id",), "simulation_truth"),
    "inventory_supplier_samples": TableDefinition(
        SupplierSample, ("order_id",), "simulation_truth"
    ),
    "inventory_scheduled_receipt_tail": TableDefinition(
        ReplenishmentReceipt, ("receipt_id",), "simulation_truth"
    ),
    "inventory_physical_daily_balances": TableDefinition(
        PhysicalDailyBalance,
        ("product_id", "stock_location_id", "business_date"),
        "simulation_truth",
    ),
    "stockout_episodes": TableDefinition(StockoutEpisode, ("episode_id",), "simulation_truth"),
    "inventory_lost_sales_impacts": TableDefinition(
        LostSalesImpact, ("demand_id",), "simulation_truth"
    ),
    "inventory_window_diagnostics": TableDefinition(
        WindowDiagnostic, ("product_id", "stock_location_id", "origin"), "simulation_truth"
    ),
}


@lru_cache
def field_rules(model: type[BaseModel]) -> dict[str, dict]:
    return {
        name: (
            {**next(r for r in rule["anyOf"] if r.get("type") != "null"), "nullable": True}
            if "anyOf" in rule
            else {**rule, "nullable": False}
        )
        for name, rule in model.model_json_schema()["properties"].items()
    }


def table_contract_schema() -> dict[str, Any]:
    # Keep each schema self-contained: a consumer need not resolve external model references.
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": TABLE_CONTRACT_VERSION,
        "type": "object",
        "additionalProperties": False,
        "required": list(TABLES),
        "properties": {
            name: {
                "type": "array",
                "x-data-class": definition.data_class,
                "x-grain": list(definition.grain),
                "items": definition.model.model_json_schema(),
            }
            for name, definition in TABLES.items()
        },
    }
