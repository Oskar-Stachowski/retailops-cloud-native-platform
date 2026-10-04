"""Public operational projection; return status and native route come from the parent."""

from __future__ import annotations

from services.api.app.services.realtime_contract import validate_event

from data.dq.full_contract import MAX_CANONICAL_EVENTS, SCOPE, FullBinding, PortfolioBinding
from data.dq.sales import sale_fact
from data.dq.source import source_binding as selected_binding
from data.generator.identity import json_sha256
from data.generator.realtime import DEFAULT_SOURCE, _event
from data.inventory.contract import require, utc_timestamp

RETURN_FIELDS = frozenset(
    {
        "return_id",
        "order_id",
        "order_item_id",
        "product_id",
        "store_id",
        "channel",
        "quantity",
        "refund_amount",
        "reason",
    }
)
OPTIONAL_CONTEXT = {"sale_completed": "sku", "return_completed": "order_id"}
GRAIN = ("event_type", "business_date", "product_id", "selling_location_id", "channel", "currency")
PROJECTION_TABLES = (
    "sales",
    "orders",
    "sale_price_references",
    "products",
    "inventory_sales",
    "return_events",
)


def full_events(tables: dict, manifest: dict) -> list[dict]:
    """No uniform sampling and no legacy returns.csv truncation at the sales cutoff."""
    orders = {r["order_reference"]: r for r in tables["orders"]}
    order_ids = {r["id"]: r for r in tables["orders"]}
    refs = {r["sale_id"]: r for r in tables["sale_price_references"]}
    products = {r["id"]: r for r in tables["products"]}
    physical = {r["sale_id"]: r for r in tables["inventory_sales"]}
    require(
        12
        <= len(tables["sales"]) + len(tables["return_events"])
        <= (
            8192
            if manifest["descriptor"]["resolved_parameters"]["profile"]
            in {"ai-07-portfolio-v1", "ai-07-portfolio-v2"}
            else MAX_CANONICAL_EVENTS
        ),
        "Full canonical stream exceeds bounded scope.",
    )
    seed = manifest["descriptor"]["resolved_parameters"]["seed"]
    events = []
    for sale in tables["sales"]:
        order, ref = orders[sale["order_reference"]], refs[sale["id"]]
        events.append(
            _event(
                seed=seed,
                source=DEFAULT_SOURCE,
                event_type="sale_completed",
                natural_key=sale["id"],
                correlation_id=order["id"],
                occurred_at=sale["sold_at"],
                ingested_at=max(
                    utc_timestamp(sale["ingested_at"]),
                    utc_timestamp(physical[sale["id"]]["available_at"]),
                ).isoformat(),
                payload={
                    "sale_id": sale["id"],
                    "order_id": order["id"],
                    "order_item_id": ref["order_item_id"],
                    "product_id": sale["product_id"],
                    "sku": products[sale["product_id"]]["sku"],
                    "store_id": order["store_id"],
                    "channel": sale["channel"],
                    **{k: sale[k] for k in ("quantity", "unit_price", "total_amount", "currency")},
                    "promotion_applied": sale["promotion_applied"] == "true",
                },
            )
        )
    for returned in tables["return_events"]:
        order = order_ids[returned["order_id"]]
        require(returned["status"] in {"refunded", "rejected"}, "Unknown native return status.")
        events.append(
            _event(
                seed=seed,
                source=DEFAULT_SOURCE,
                event_type="return_completed",
                natural_key=returned["id"],
                correlation_id=order["id"],
                occurred_at=returned["returned_at"],
                ingested_at=returned["available_at"],
                payload={
                    "return_id": returned["id"],
                    "order_id": returned["order_id"],
                    "order_item_id": returned["order_item_id"],
                    "product_id": returned["product_id"],
                    "store_id": order["store_id"],
                    "channel": returned["channel"],
                    "quantity": str(returned["quantity"]),
                    "refund_amount": returned["refund_amount"],
                    "reason": returned["reason"],
                },
            )
        )
    for event in events:
        validate_event(event, transport_topic=event["topic"])
    events.sort(key=lambda e: (e["occurred_at"], e["event_type"], business_id(e)))
    require(len({e["event_id"] for e in events}) == len(events), "Repeated canonical event ID.")
    return events


def business_id(event: dict) -> str:
    return event["payload"]["sale_id" if event["event_type"] == "sale_completed" else "return_id"]


def source_binding(manifest: dict, events: list[dict]) -> dict:
    base = selected_binding(manifest, events)
    portfolio = manifest["descriptor"]["resolved_parameters"]["profile"] in {
        "ai-07-portfolio-v1",
        "ai-07-portfolio-v2",
    }
    model = PortfolioBinding if portfolio else FullBinding
    return model.from_payload(
        {
            **base,
            "contract_version": "raw-dq-binding-2.1.0" if portfolio else "raw-dq-binding-2.0.0",
            "selection_policy": "all_canonical_sales_and_native_return_claims_v1",
            "projection": "legacy_operational_sales_and_returns_allowlist_v1",
            "scope": SCOPE,
            "source_return_count": manifest["descriptor"]["tables"]["return_events"]["row_count"],
            "projection_tables": {
                n: manifest["descriptor"]["tables"][n] for n in PROJECTION_TABLES
            },
            "return_scope": "purchases_in_parent_source_only",
            "return_status_source": "verified_native_parent_not_refund_amount_inference",
            "business_event_day_completeness": "not_qualified",
            "missing_grain_policy": "unknown_not_zero",
        }
    ).model_dump()


def parent_facts(tables: dict, events: list[dict]) -> dict[tuple[str, str], dict]:
    native_sales = {r["sale_id"]: r for r in tables["inventory_sales"]}
    native_returns = {r["id"]: r for r in tables["return_events"]}
    result = {}
    for event in events:
        kind, identifier = event["event_type"], business_id(event)
        native = (
            native_sales[identifier] if kind == "sale_completed" else native_returns[identifier]
        )
        sale = native if kind == "sale_completed" else native_sales[native["sale_id"]]
        payload = event["payload"]
        if kind == "sale_completed":
            sale_fact(event, event["topic"])
        fact = {
            "event_type": kind,
            "business_id": identifier,
            "business_date": utc_timestamp(event["occurred_at"]).date().isoformat(),
            "product_id": payload["product_id"],
            "selling_location_id": sale["selling_location_id"],
            "stock_location_id": sale["stock_location_id"],
            "channel": sale["channel"],
            "currency": native["currency"],
            "quantity": int(payload["quantity"]),
            "amount": payload["total_amount" if kind == "sale_completed" else "refund_amount"],
            "status": "sold" if kind == "sale_completed" else native["status"],
            "occurred_at": event["occurred_at"],
            "ingested_at": event["ingested_at"],
        }
        result[kind, identifier] = {**fact, "business_version_sha256": json_sha256(fact)}
    return result


def match_fact(event: dict, canonical: dict[tuple[str, str], dict], facts: dict) -> dict:
    validate_event(event, transport_topic="retailops.sales.v1")
    key = event["event_type"], business_id(event)
    require(key in canonical, "Fact absent from canonical parent.")
    expected = canonical[key]
    optional = OPTIONAL_CONTEXT[key[0]]
    actual = {k: v for k, v in event.items() if k != "event_id"}
    reference = {k: v for k, v in expected.items() if k != "event_id"}
    if optional not in actual["payload"]:
        reference = {
            **reference,
            "payload": {k: v for k, v in reference["payload"].items() if k != optional},
        }
    require(actual == reference, "Event differs from canonical operational parent.")
    return facts[key]
