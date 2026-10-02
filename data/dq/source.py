"""Read verified canonical source facts and project a bounded legacy sales stream."""

from __future__ import annotations

from typing import TYPE_CHECKING

from services.api.app.services.realtime_contract import validate_event

from data.generator.identity import json_sha256
from data.generator.realtime import DEFAULT_SOURCE, _event
from data.inventory.contract import require, utc_timestamp
from data.inventory.source_dataset_contract import MANIFEST_FILENAME, SourceManifest
from data.inventory.source_dataset_io import load_json, read_source_dataset, safe_file

if TYPE_CHECKING:
    from pathlib import Path

MAX_SOURCE_BYTES = 64 * 1024 * 1024


def load_source(directory: Path) -> tuple[dict, dict]:
    payload = load_json(safe_file(directory, MANIFEST_FILENAME, limit=2 * 1024 * 1024))
    manifest = SourceManifest.model_validate(payload)
    params = manifest.descriptor.resolved_parameters
    require(
        params.days * params.products * params.stores <= 5000,
        "DQ parent exceeds bounded daily scope.",
    )
    require(
        sum(a.size_bytes for a in manifest.artifacts.values()) <= MAX_SOURCE_BYTES,
        "DQ parent exceeds source artifact budget.",
    )
    tables, verified = read_source_dataset(directory, payload)
    require(verified["facts_ready"], "DQ parent source facts are not qualified.")
    return tables, verified


def sales_events(tables: dict, manifest: dict, limit: int) -> list[dict]:
    require(12 <= limit <= 512, "Invalid bounded sales event limit.")
    orders = {r["order_reference"]: r for r in tables["orders"]}
    refs = {r["sale_id"]: r for r in tables["sale_price_references"]}
    products = {r["id"]: r for r in tables["products"]}
    inventory_sales = {r["sale_id"]: r for r in tables["inventory_sales"]}
    sales = sorted(tables["sales"], key=lambda r: (utc_timestamp(r["sold_at"]), r["id"]))
    require(len(sales) >= 12, "DQ source needs at least twelve actual sales.")
    # Equally spaced, deterministic selection covers both ends of the source history.
    if len(sales) > limit:
        sales = [sales[i * (len(sales) - 1) // (limit - 1)] for i in range(limit)]
    events = []
    for sale in sales:
        order, ref = orders[sale["order_reference"]], refs[sale["id"]]
        event = _event(
            seed=manifest["descriptor"]["resolved_parameters"]["seed"],
            source=DEFAULT_SOURCE,
            event_type="sale_completed",
            natural_key=sale["id"],
            correlation_id=order["id"],
            occurred_at=sale["sold_at"],
            ingested_at=max(
                utc_timestamp(sale["ingested_at"]),
                utc_timestamp(inventory_sales[sale["id"]]["available_at"]),
            ).isoformat(),
            payload={
                "sale_id": sale["id"],
                "order_id": order["id"],
                "order_item_id": ref["order_item_id"],
                "product_id": sale["product_id"],
                "sku": products[sale["product_id"]]["sku"],
                "store_id": order["store_id"],
                "channel": sale["channel"],
                "quantity": sale["quantity"],
                "unit_price": sale["unit_price"],
                "total_amount": sale["total_amount"],
                "currency": sale["currency"],
                "promotion_applied": sale["promotion_applied"] == "true",
            },
        )
        validate_event(event, transport_topic=event["topic"])
        events.append(event)
    require(len({e["event_id"] for e in events}) == len(events), "Repeated canonical event ID.")
    return events


def source_binding(manifest: dict, events: list[dict]) -> dict:
    return {
        "source_dataset_id": manifest["dataset_id"],
        "source_descriptor_sha256": json_sha256(manifest["descriptor"]),
        "source_events_sha256": json_sha256(events),
        "source_event_count": len(events),
        "source_sales_count": manifest["descriptor"]["tables"]["sales"]["row_count"],
        "source_facts_ready": manifest["facts_ready"],
        "selection_policy": "chronological_equally_spaced_inclusive_endpoints_v1",
        "projection": "legacy_sale_completed_operational_allowlist_v1",
    }
