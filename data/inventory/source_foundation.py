"""Build opening, quotes and demand arrivals without using future demand totals."""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from data.generator.business_calendar import utc_midnight
from data.generator.common import deterministic_uuid
from data.inventory.contract import require
from data.inventory.ledger import build_opening_movements
from data.inventory.simulation_contract import FulfillmentRoute

if TYPE_CHECKING:
    from data.generator.configuration import ResolvedGenerationConfig
    from data.inventory.source_contract import SourceInventoryConfig


def source_foundation(
    tables: dict, generation: ResolvedGenerationConfig, config: SourceInventoryConfig
) -> dict[str, Any]:
    require(generation.profile.startswith("ai-"), "Source inventory requires an AI profile.")
    require(
        config.fulfillment.seed == generation.seed,
        "Supplier fulfillment seed must match the source seed.",
    )
    require(
        config.stock.history_window_days <= generation.days,
        "Inventory history window exceeds the observed source window.",
    )
    start = utc_midnight(generation.start_date)
    end = utc_midnight(generation.end_date + timedelta(days=1))
    known = utc_midnight(generation.start_date - timedelta(days=1))
    products = [
        {"id": row["id"], "unit_of_measure": row["unit_of_measure"]}
        for row in sorted(tables["product_catalog"], key=lambda r: r["id"])
    ]
    locations = [
        {"id": row["id"], "location_code": row["location_code"]}
        for row in sorted(tables["stock_locations"], key=lambda r: r["id"])
    ]
    quantities = {
        (p["id"], s["id"]): config.stock.opening_quantity for p in products for s in locations
    }
    inventory = {
        "contract_version": "inventory-ledger-1.0.0",
        "opening_policy": "single_opening_movement",
        "reservation_policy": "none",
        "opening_at": start,
        "products": products,
        "stock_locations": locations,
        "inventory_scope": [
            {"product_id": p, "stock_location_id": s} for p, s in sorted(quantities)
        ],
        "movements": build_opening_movements(
            quantities,
            {p["id"]: p["unit_of_measure"] for p in products},
            occurred_at=start,
            ingested_at=start,
            available_at=start,
        ),
    }
    supplier_id = deterministic_uuid("supplier", "source-inventory:PL-01")
    supplier = {
        "supplier_id": supplier_id,
        "supplier_code": "SOURCE_PL_01",
        "country_code": "PL",
        "status": "active",
        "minimum_order_quantity": config.stock.minimum_order_quantity,
        "available_at": known,
    }
    quotes = [
        {
            "product_supplier_id": deterministic_uuid("product_supplier", row["id"] + supplier_id),
            "product_id": row["id"],
            "supplier_id": supplier_id,
            "unit_of_measure": row["unit_of_measure"],
            "unit_cost": row["unit_cost"],
            "currency": row["currency"],
            "priority": 1,
            "effective_from": generation.start_date.isoformat(),
            "effective_to": (generation.end_date + timedelta(days=2)).isoformat(),
            "quoted_lead_time_days": config.stock.quoted_lead_time_days,
            "lead_time_basis": "supplier_quote",
            "quote_reference": "source-inventory-initial-quote:" + row["id"],
            "known_at": known,
            "ingested_at": known,
            "available_at": known,
        }
        for row in sorted(tables["product_catalog"], key=lambda r: r["id"])
    ]
    supply = {
        "contract_version": "replenishment-1.0.0",
        "over_receipt_policy": "reject",
        "products": products,
        "stock_locations": locations,
        "suppliers": [supplier],
        "product_suppliers": quotes,
        "replenishment_orders": [],
        "delivery_plan_versions": [],
        "replenishment_receipts": [],
    }
    refs = {row["sale_id"]: row for row in tables["sale_price_references"]}
    arrivals = [
        {
            "demand_id": sale["id"],
            "product_id": sale["product_id"],
            "selling_location_id": refs[sale["id"]]["selling_location_id"],
            "channel": refs[sale["id"]]["channel"],
            "latent_quantity": int(sale["quantity"]),
            "unit_price": sale["unit_price"],
            "currency": sale["currency"],
            "occurred_at": sale["sold_at"],
            "sequence": sequence,
            "source_reference": sale["order_reference"],
        }
        for sequence, sale in enumerate(
            sorted(
                tables["sales"], key=lambda r: (r["sold_at"], r["order_reference"], r["product_id"])
            )
        )
    ]
    # Source versions count assignment periods, including a channel change.
    # Inventory revisions count corrections within one exact route period.
    # Preserve the original route ID and expose both version numbers explicitly.
    periods = defaultdict(list)
    for row in tables["fulfillment_routes"]:
        periods[
            tuple(
                row[key]
                for key in (
                    "selling_location_id",
                    "channel",
                    "effective_from",
                    "effective_to",
                )
            )
        ].append(row)
    routes, route_versions = [], []
    for rows in periods.values():
        for revision, row in enumerate(sorted(rows, key=lambda r: int(r["version"])), start=1):
            routes.append(
                FulfillmentRoute.model_validate(
                    {
                        **{
                            key: row[key]
                            for key in FulfillmentRoute.model_fields
                            if key != "version"
                        },
                        "version": revision,
                    }
                ).model_dump()
            )
            route_versions.append(
                {
                    "route_id": row["id"],
                    "source_version": int(row["version"]),
                    "inventory_revision": revision,
                }
            )
    scenario = {
        "contract_version": "chronological-scenario-1.0.0",
        "settings": {
            "process_version": "chronological-shared-stock-1.0.0",
            "business_timezone": "UTC",
            "start_at": start,
            "end_at": end,
            "event_order": "occurred_at_sequence_then_review",
            "reservation_policy": "none",
            "fulfillment_policy": "instant_partial_fulfillment",
            "sale_ingestion_delay_seconds": config.sale_ingestion_delay_seconds,
            "sale_availability_delay_seconds": config.sale_availability_delay_seconds,
        },
        "selling_locations": [
            {"id": row["id"], "location_code": row["location_code"]}
            for row in tables["selling_locations"]
        ],
        "fulfillment_routes": routes,
        "demand_class": "simulation_truth",
        "demand_arrivals": arrivals,
        "return_events": [],
        "inventory_actions": [],
    }
    policy = {
        "contract_version": "reorder-config-1.0.0",
        "policy_version": "periodic-review-stock-position-1.0.0",
        "business_timezone": "UTC",
        "review_anchor_at": utc_midnight(
            generation.start_date + timedelta(days=config.stock.history_window_days)
        ),
        "known_at": known,
        "available_at": known,
        "rules": [
            {
                "product_id": p,
                "stock_location_id": s,
                **{
                    key: getattr(config.stock, key)
                    for key in (
                        "reorder_point",
                        "safety_stock",
                        "review_cadence_days",
                        "history_window_days",
                        "minimum_order_quantity",
                    )
                },
            }
            for p, s in sorted(quantities)
        ],
    }
    truth = {
        "contract_version": "supplier-simulation-truth-1.0.0",
        "data_class": "simulation_truth",
        "suppliers": [
            {
                "supplier_id": supplier_id,
                **config.supplier_parameters.model_dump(exclude={"data_class"}),
            }
        ],
    }
    return {
        "inventory": inventory,
        "supply": supply,
        "scenario": scenario,
        "policy": policy,
        "fulfillment": config.fulfillment.model_dump(),
        "truth": truth,
        "source_route_versions": sorted(route_versions, key=lambda r: r["route_id"]),
    }
