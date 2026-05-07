from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from data.generator.common import deterministic_uuid
from data.generator.main import (
    DatasetGenerationConfig,
    SUPPORTED_PROFILES,
    build_dataset,
)

SCHEMA_VERSION = "1.0"
DEFAULT_SOURCE = "retailops.synthetic-generator"
DEFAULT_MAX_EVENTS = 1000
EVENTS_FILENAME = "events.jsonl"
MANIFEST_FILENAME = "event_manifest.json"

EVENT_TOPICS: dict[str, str] = {
    "order_created": "retailops.sales.v1",
    "sale_completed": "retailops.sales.v1",
    "return_completed": "retailops.sales.v1",
    "stock_changed": "retailops.inventory.v1",
    "inventory_snapshot_recorded": "retailops.inventory.v1",
    "replenishment_completed": "retailops.inventory.v1",
    "price_changed": "retailops.pricing.v1",
    "promotion_started": "retailops.pricing.v1",
    "promotion_ended": "retailops.pricing.v1",
    "forecast_generated": "retailops.intelligence.v1",
    "anomaly_detected": "retailops.intelligence.v1",
    "alert_created": "retailops.operations.v1",
    "workflow_action_performed": "retailops.operations.v1",
}


@dataclass(frozen=True)
class RealtimeEventGenerationConfig:
    dataset: DatasetGenerationConfig
    max_events: int | None = DEFAULT_MAX_EVENTS
    source: str = DEFAULT_SOURCE


def default_replay_output_dir(profile: str) -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "data" / "replay" / profile


def validate_event_generation_config(
    config: RealtimeEventGenerationConfig,
) -> None:
    if config.max_events is not None and config.max_events <= 0:
        raise ValueError("max_events must be a positive integer.")

    if not config.source:
        raise ValueError("source must not be empty.")


def _event_id(seed: int, event_type: str, natural_key: str) -> str:
    return deterministic_uuid(
        "event",
        f"{seed}:{event_type}:{natural_key}",
    )


def _scalar(value: Any) -> str:
    if isinstance(value, tuple):
        return str(value[0]) if value else ""

    return str(value)


def _parse_datetime(value: Any) -> datetime:
    normalized = _scalar(value).replace("Z", "+00:00")
    if len(normalized) == 10:
        normalized = f"{normalized}T00:00:00+00:00"
    return datetime.fromisoformat(normalized)


def _event_time(value: str) -> str:
    return _parse_datetime(value).isoformat()


def _plus_one_second(value: str) -> str:
    return (_parse_datetime(value) + timedelta(seconds=1)).isoformat()


def _event(
    *,
    seed: int,
    source: str,
    event_type: str,
    natural_key: str,
    correlation_id: str,
    occurred_at: str,
    ingested_at: str | None,
    payload: dict[str, Any],
) -> dict[str, Any]:
    normalized_occurred_at = _event_time(occurred_at)
    normalized_ingested_at = (
        _event_time(ingested_at)
        if ingested_at
        else _plus_one_second(normalized_occurred_at)
    )

    return {
        "event_id": _event_id(seed, event_type, natural_key),
        "event_type": event_type,
        "schema_version": SCHEMA_VERSION,
        "source": source,
        "topic": EVENT_TOPICS[event_type],
        "correlation_id": correlation_id,
        "occurred_at": normalized_occurred_at,
        "ingested_at": normalized_ingested_at,
        "payload": payload,
    }


def _by_id(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row["id"]: row for row in rows}


def _order_items_by_order_and_product(
    order_items: list[dict[str, str]],
) -> dict[tuple[str, str], list[dict[str, str]]]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = {}
    for item in order_items:
        key = (item["order_id"], item["product_id"])
        grouped.setdefault(key, []).append(item)
    return grouped


def _find_order_item_for_sale(
    sale: dict[str, str],
    order: dict[str, str] | None,
    order_items_by_key: dict[tuple[str, str], list[dict[str, str]]],
) -> dict[str, str]:
    if not order:
        return {}

    candidates = order_items_by_key.get((order["id"], sale["product_id"]), [])
    for candidate in candidates:
        if (
            candidate.get("quantity") == sale.get("quantity")
            and candidate.get("total_amount") == sale.get("total_amount")
        ):
            return candidate

    return candidates[0] if candidates else {}


def _old_price_for(
    price_point: dict[str, str],
    price_history_by_product: dict[str, list[dict[str, str]]],
) -> str:
    product_history = price_history_by_product.get(
        price_point["product_id"],
        [],
    )
    previous_price = ""
    for candidate in product_history:
        if candidate["id"] == price_point["id"]:
            return previous_price
        previous_price = candidate["price"]

    return previous_price


def _build_lookup_context(
    tables: dict[str, list[dict[str, str]]],
) -> dict[str, Any]:
    orders_by_id = _by_id(tables["orders"])
    orders_by_reference = {
        order["order_reference"]: order for order in tables["orders"]
    }
    stores_by_id = _by_id(tables["stores"])
    warehouses_by_code = {
        warehouse["warehouse_code"]: warehouse
        for warehouse in tables["warehouses"]
    }
    price_history_by_product: dict[str, list[dict[str, str]]] = {}
    for price_point in tables["price_history"]:
        price_history_by_product.setdefault(
            price_point["product_id"],
            [],
        ).append(price_point)

    for product_history in price_history_by_product.values():
        product_history.sort(key=lambda row: row["valid_from"])

    return {
        "products_by_id": _by_id(tables["products"]),
        "orders_by_id": orders_by_id,
        "orders_by_reference": orders_by_reference,
        "stores_by_id": stores_by_id,
        "warehouses_by_code": warehouses_by_code,
        "order_items_by_key": _order_items_by_order_and_product(
            tables["order_items"],
        ),
        "price_history_by_product": price_history_by_product,
    }


def _order_events(
    tables: dict[str, list[dict[str, str]]],
    context: dict[str, Any],
    config: RealtimeEventGenerationConfig,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []

    for order in tables["orders"]:
        store = context["stores_by_id"].get(order["store_id"], {})
        events.append(
            _event(
                seed=config.dataset.seed,
                source=config.source,
                event_type="order_created",
                natural_key=order["id"],
                correlation_id=order["id"],
                occurred_at=order["ordered_at"],
                ingested_at=order.get("created_at"),
                payload={
                    "order_id": order["id"],
                    "store_id": order["store_id"],
                    "store_code": store.get("store_code", ""),
                    "channel": order["channel"],
                    "customer_segment": "synthetic",
                    "order_total": order["order_total"],
                    "currency": order["currency"],
                    "status": order["status"],
                },
            )
        )

    return events


def _sale_events(
    tables: dict[str, list[dict[str, str]]],
    context: dict[str, Any],
    config: RealtimeEventGenerationConfig,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []

    for sale in tables["sales"]:
        order = context["orders_by_reference"].get(sale["order_reference"])
        order_item = _find_order_item_for_sale(
            sale,
            order,
            context["order_items_by_key"],
        )
        product = context["products_by_id"].get(sale["product_id"], {})
        store_id = order["store_id"] if order else ""

        events.append(
            _event(
                seed=config.dataset.seed,
                source=config.source,
                event_type="sale_completed",
                natural_key=sale["id"],
                correlation_id=order["id"] if order else sale["order_reference"],
                occurred_at=sale["sold_at"],
                ingested_at=sale.get("ingested_at"),
                payload={
                    "sale_id": sale["id"],
                    "order_id": order["id"] if order else "",
                    "order_item_id": order_item.get("id", ""),
                    "product_id": sale["product_id"],
                    "sku": product.get("sku", ""),
                    "store_id": store_id,
                    "channel": sale["channel"],
                    "quantity": sale["quantity"],
                    "unit_price": sale["unit_price"],
                    "total_amount": sale["total_amount"],
                    "currency": sale["currency"],
                    "promotion_applied": sale.get(
                        "promotion_applied",
                        "false",
                    )
                    == "true",
                    "latent_demand": sale.get(
                        "latent_demand",
                        sale["quantity"],
                    ),
                    "observed_sales": sale.get(
                        "observed_sales",
                        sale["quantity"],
                    ),
                    "stockout_flag": sale.get("stockout_flag", "false")
                    == "true",
                    "data_quality_status": sale.get(
                        "data_quality_status",
                        "valid",
                    ),
                },
            )
        )

    return events


def _return_events(
    tables: dict[str, list[dict[str, str]]],
    context: dict[str, Any],
    config: RealtimeEventGenerationConfig,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []

    for returned_item in tables["returns"]:
        order = context["orders_by_id"].get(returned_item["order_id"], {})
        events.append(
            _event(
                seed=config.dataset.seed,
                source=config.source,
                event_type="return_completed",
                natural_key=returned_item["id"],
                correlation_id=returned_item["order_id"],
                occurred_at=returned_item["returned_at"],
                ingested_at=None,
                payload={
                    "return_id": returned_item["id"],
                    "order_id": returned_item["order_id"],
                    "order_item_id": returned_item["order_item_id"],
                    "product_id": returned_item["product_id"],
                    "store_id": order.get("store_id", ""),
                    "channel": order.get("channel", ""),
                    "quantity": returned_item["quantity"],
                    "refund_amount": returned_item["refund_amount"],
                    "reason": returned_item["reason"],
                },
            )
        )

    return events


def _inventory_events(
    tables: dict[str, list[dict[str, str]]],
    context: dict[str, Any],
    config: RealtimeEventGenerationConfig,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []

    for snapshot in tables["inventory_snapshots"]:
        warehouse = context["warehouses_by_code"].get(
            snapshot["warehouse_code"],
            {},
        )
        events.append(
            _event(
                seed=config.dataset.seed,
                source=config.source,
                event_type="inventory_snapshot_recorded",
                natural_key=snapshot["id"],
                correlation_id=snapshot["id"],
                occurred_at=snapshot["recorded_at"],
                ingested_at=snapshot.get("ingested_at"),
                payload={
                    "inventory_snapshot_id": snapshot["id"],
                    "product_id": snapshot["product_id"],
                    "warehouse_id": warehouse.get("id", ""),
                    "stock_quantity": snapshot["stock_quantity"],
                    "unit_of_measure": snapshot["unit_of_measure"],
                    "recorded_at": snapshot["recorded_at"],
                },
            )
        )

    for movement in tables["stock_movements"]:
        event_type = (
            "replenishment_completed"
            if movement["movement_type"] == "replenishment"
            else "stock_changed"
        )
        payload = {
            "stock_movement_id": movement["id"],
            "product_id": movement["product_id"],
            "warehouse_id": movement["warehouse_id"],
            "store_id": "",
            "movement_type": movement["movement_type"],
            "quantity_delta": movement["quantity"],
            "stock_after": "",
            "reason_code": movement["movement_type"],
        }
        if event_type == "replenishment_completed":
            payload = {
                "replenishment_id": movement["id"],
                "product_id": movement["product_id"],
                "warehouse_id": movement["warehouse_id"],
                "quantity": movement["quantity"],
                "supplier_id": "",
                "lead_time_days": "0",
            }

        events.append(
            _event(
                seed=config.dataset.seed,
                source=config.source,
                event_type=event_type,
                natural_key=movement["id"],
                correlation_id=movement["source_reference"],
                occurred_at=movement["occurred_at"],
                ingested_at=movement.get("created_at"),
                payload=payload,
            )
        )

    return events


def _pricing_events(
    tables: dict[str, list[dict[str, str]]],
    context: dict[str, Any],
    config: RealtimeEventGenerationConfig,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []

    for price_point in tables["price_history"]:
        events.append(
            _event(
                seed=config.dataset.seed,
                source=config.source,
                event_type="price_changed",
                natural_key=price_point["id"],
                correlation_id=price_point["product_id"],
                occurred_at=price_point["valid_from"],
                ingested_at=price_point.get("created_at"),
                payload={
                    "price_history_id": price_point["id"],
                    "product_id": price_point["product_id"],
                    "old_price": _old_price_for(
                        price_point,
                        context["price_history_by_product"],
                    ),
                    "new_price": price_point["price"],
                    "currency": price_point["currency"],
                    "effective_from": price_point["valid_from"],
                    "effective_to": price_point["valid_to"],
                },
            )
        )

    for promotion in tables["promotions"]:
        base_payload = {
            "promotion_id": promotion["id"],
            "product_id": promotion["product_id"],
        }
        events.append(
            _event(
                seed=config.dataset.seed,
                source=config.source,
                event_type="promotion_started",
                natural_key=f"{promotion['id']}:started",
                correlation_id=promotion["id"],
                occurred_at=promotion["starts_at"],
                ingested_at=None,
                payload={
                    **base_payload,
                    "promotion_type": promotion["promotion_type"],
                    "discount_percent": promotion["discount_percent"],
                    "starts_at": promotion["starts_at"],
                    "ends_at": promotion["ends_at"],
                    "expected_uplift": "",
                },
            )
        )
        events.append(
            _event(
                seed=config.dataset.seed,
                source=config.source,
                event_type="promotion_ended",
                natural_key=f"{promotion['id']}:ended",
                correlation_id=promotion["id"],
                occurred_at=promotion["ends_at"],
                ingested_at=None,
                payload={
                    **base_payload,
                    "ended_at": promotion["ends_at"],
                    "post_promotion_effect": "",
                },
            )
        )

    return events


def _intelligence_events(
    tables: dict[str, list[dict[str, str]]],
    config: RealtimeEventGenerationConfig,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []

    for forecast in tables["forecasts"]:
        events.append(
            _event(
                seed=config.dataset.seed,
                source=config.source,
                event_type="forecast_generated",
                natural_key=forecast["id"],
                correlation_id=forecast["product_id"],
                occurred_at=forecast["generated_at"],
                ingested_at=None,
                payload={
                    "forecast_id": forecast["id"],
                    "product_id": forecast["product_id"],
                    "store_id": "",
                    "forecast_date": forecast["forecast_period_start"],
                    "predicted_demand": forecast["predicted_quantity"],
                    "model_version": forecast["method"],
                    "confidence": forecast["confidence_level"],
                },
            )
        )

    for anomaly in tables["anomalies"]:
        events.append(
            _event(
                seed=config.dataset.seed,
                source=config.source,
                event_type="anomaly_detected",
                natural_key=anomaly["id"],
                correlation_id=anomaly["product_id"],
                occurred_at=anomaly["detected_at"],
                ingested_at=None,
                payload={
                    "anomaly_id": anomaly["id"],
                    "product_id": anomaly["product_id"],
                    "store_id": "",
                    "anomaly_type": anomaly["anomaly_type"],
                    "severity": anomaly["severity"],
                    "score": anomaly["deviation_percent"],
                    "description": anomaly["metric_name"],
                },
            )
        )

    return events


def _operations_events(
    tables: dict[str, list[dict[str, str]]],
    config: RealtimeEventGenerationConfig,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []

    for alert in tables["alerts"]:
        events.append(
            _event(
                seed=config.dataset.seed,
                source=config.source,
                event_type="alert_created",
                natural_key=alert["id"],
                correlation_id=alert["id"],
                occurred_at=alert["created_at"],
                ingested_at=alert.get("updated_at") or None,
                payload={
                    "alert_id": alert["id"],
                    "product_id": alert["product_id"],
                    "anomaly_id": alert["anomaly_id"],
                    "alert_type": alert["alert_type"],
                    "severity": alert["severity"],
                    "status": alert["status"],
                    "title": alert["title"],
                    "recommended_action": alert["recommended_action"],
                },
            )
        )

    for action in tables["workflow_actions"]:
        events.append(
            _event(
                seed=config.dataset.seed,
                source=config.source,
                event_type="workflow_action_performed",
                natural_key=action["id"],
                correlation_id=action["alert_id"],
                occurred_at=action.get("performed_at")
                or action["created_at"],
                ingested_at=action.get("created_at"),
                payload={
                    "workflow_action_id": action["id"],
                    "alert_id": action["alert_id"],
                    "user_id": action["performed_by_user_id"],
                    "action_type": action["action_type"],
                    "previous_status": action["previous_status"],
                    "new_status": action["new_status"],
                    "comment": action["comment"],
                },
            )
        )

    return events


def build_realtime_events(
    tables: dict[str, list[dict[str, str]]],
    config: RealtimeEventGenerationConfig,
) -> list[dict[str, Any]]:
    validate_event_generation_config(config)
    context = _build_lookup_context(tables)
    events = [
        *_order_events(tables, context, config),
        *_sale_events(tables, context, config),
        *_return_events(tables, context, config),
        *_inventory_events(tables, context, config),
        *_pricing_events(tables, context, config),
        *_intelligence_events(tables, config),
        *_operations_events(tables, config),
    ]
    events.sort(
        key=lambda event: (
            event["occurred_at"],
            event["event_type"],
            event["event_id"],
        )
    )

    if config.max_events is not None:
        return events[: config.max_events]

    return events


def build_event_manifest(
    config: RealtimeEventGenerationConfig,
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    event_type_counts: dict[str, int] = {}
    topic_counts: dict[str, int] = {}
    for event in events:
        event_type_counts[event["event_type"]] = (
            event_type_counts.get(event["event_type"], 0) + 1
        )
        topic_counts[event["topic"]] = topic_counts.get(event["topic"], 0) + 1

    return {
        "dataset_name": "retailops-realtime-events",
        "profile": config.dataset.profile,
        "schema_version": SCHEMA_VERSION,
        "source": config.source,
        "seed": config.dataset.seed,
        "max_events": config.max_events,
        "formats": ["jsonl"],
        "event_count": len(events),
        "event_type_counts": dict(sorted(event_type_counts.items())),
        "topic_counts": dict(sorted(topic_counts.items())),
        "date_start": events[0]["occurred_at"] if events else None,
        "date_end": events[-1]["occurred_at"] if events else None,
        "artifacts": [
            EVENTS_FILENAME,
            MANIFEST_FILENAME,
        ],
    }


def write_realtime_events(
    output_dir: Path,
    events: list[dict[str, Any]],
    config: RealtimeEventGenerationConfig,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    events_path = output_dir / EVENTS_FILENAME
    manifest_path = output_dir / MANIFEST_FILENAME

    with events_path.open("w", encoding="utf-8") as file:
        for event in events:
            file.write(json.dumps(event, sort_keys=True) + "\n")

    manifest = build_event_manifest(config, events)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    return manifest


def generate_realtime_event_dataset(
    output_dir: Path | None = None,
    config: RealtimeEventGenerationConfig | None = None,
) -> dict[str, Any]:
    config = config or RealtimeEventGenerationConfig(
        dataset=DatasetGenerationConfig(),
    )
    tables = build_dataset(config.dataset)
    events = build_realtime_events(tables, config)
    output_dir = output_dir or default_replay_output_dir(config.dataset.profile)
    return write_realtime_events(output_dir, events, config)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate RetailOps replayable real-time events as JSONL."
    )
    parser.add_argument(
        "--profile",
        choices=SUPPORTED_PROFILES,
        default="demo",
        help="Synthetic data profile used as event source.",
    )
    parser.add_argument(
        "--days",
        type=int,
        help="Number of historical business days to generate.",
    )
    parser.add_argument(
        "--products",
        type=int,
        help="Number of products to generate.",
    )
    parser.add_argument(
        "--stores",
        type=int,
        help="Number of stores or selling locations to generate.",
    )
    parser.add_argument(
        "--warehouses",
        type=int,
        help="Number of warehouses to generate.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Deterministic generation seed.",
    )
    parser.add_argument(
        "--max-events",
        type=int,
        default=DEFAULT_MAX_EVENTS,
        help="Maximum number of events to write. Use 0 to write all events.",
    )
    parser.add_argument(
        "--source",
        default=DEFAULT_SOURCE,
        help="Event producer source name.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory where JSONL replay files should be written.",
    )

    return parser.parse_args()


def config_from_args(args: argparse.Namespace) -> RealtimeEventGenerationConfig:
    max_events = None if args.max_events == 0 else args.max_events
    return RealtimeEventGenerationConfig(
        dataset=DatasetGenerationConfig(
            profile=args.profile,
            days=args.days,
            products=args.products,
            stores=args.stores,
            warehouses=args.warehouses,
            seed=args.seed,
        ),
        max_events=max_events,
        source=args.source,
    )


def main() -> None:
    args = parse_args()
    config = config_from_args(args)
    output_dir = args.output_dir or default_replay_output_dir(
        config.dataset.profile,
    )
    manifest = generate_realtime_event_dataset(output_dir, config)

    print(
        "RetailOps real-time event replay generated "
        f"for profile '{config.dataset.profile}':"
    )
    print(f"- events: {manifest['event_count']}")
    for event_type, count in manifest["event_type_counts"].items():
        print(f"- {event_type}: {count}")
    print(f"\nOutput directory: {output_dir}")


if __name__ == "__main__":
    main()
