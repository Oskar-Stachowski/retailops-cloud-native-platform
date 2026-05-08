from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from uuid import NAMESPACE_URL, uuid5

from psycopg.rows import dict_row

from app.db.connection import get_connection
from app.services.realtime_consumer import RealtimeEventConsumer


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def stable_event_id(value: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"retailops-observability-demo:{value}"))


def fetch_demo_products(limit: int = 3) -> list[dict]:
    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT id, sku, name, category
                FROM products
                ORDER BY sku ASC
                LIMIT %s;
                """,
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]


def event(
    *,
    run_id: str,
    sequence: int,
    event_type: str,
    product: dict | None,
    payload: dict,
    occurred_at: datetime,
    ingested_delay_seconds: int,
) -> dict:
    product_suffix = product["sku"].lower() if product else "platform"
    readable_id = f"{run_id}-{sequence:02d}-{product_suffix}"
    return {
        "event_id": stable_event_id(readable_id),
        "event_type": event_type,
        "schema_version": "1.0",
        "source": "observability-demo",
        "correlation_id": f"obs-demo-{run_id}",
        "occurred_at": iso(occurred_at),
        "ingested_at": iso(occurred_at + timedelta(seconds=ingested_delay_seconds)),
        "payload": payload,
    }


def build_events(products: list[dict]) -> list[dict]:
    now = utc_now()
    run_id = now.strftime("%Y%m%d%H%M%S")
    primary = products[0]
    secondary = products[1] if len(products) > 1 else products[0]
    tertiary = products[2] if len(products) > 2 else products[0]

    primary_payload = {
        "product_id": str(primary["id"]),
        "sku": primary["sku"],
        "store_id": "warsaw-flagship",
        "channel": "online",
        "quantity": "8",
        "unit_price": "149.90",
        "total_amount": "1199.20",
    }

    sale = event(
        run_id=run_id,
        sequence=1,
        event_type="sale_completed",
        product=primary,
        payload=primary_payload,
        occurred_at=now - timedelta(minutes=9, seconds=20),
        ingested_delay_seconds=4,
    )

    events = [
        event(
            run_id=run_id,
            sequence=0,
            event_type="order_created",
            product=primary,
            payload={
                "product_id": str(primary["id"]),
                "store_id": "warsaw-flagship",
                "channel": "online",
                "order_total": "1199.20",
                "priority": "same_day_delivery",
            },
            occurred_at=now - timedelta(minutes=10),
            ingested_delay_seconds=3,
        ),
        sale,
        event(
            run_id=run_id,
            sequence=2,
            event_type="stock_changed",
            product=primary,
            payload={
                "product_id": str(primary["id"]),
                "warehouse_id": "waw-fulfillment-01",
                "quantity_delta": "-8",
                "reason": "sale_allocation",
            },
            occurred_at=now - timedelta(minutes=8, seconds=45),
            ingested_delay_seconds=5,
        ),
        event(
            run_id=run_id,
            sequence=3,
            event_type="price_changed",
            product=secondary,
            payload={
                "product_id": str(secondary["id"]),
                "sku": secondary["sku"],
                "old_price": "199.90",
                "new_price": "179.90",
                "reason": "competitor_price_match",
            },
            occurred_at=now - timedelta(minutes=7, seconds=30),
            ingested_delay_seconds=6,
        ),
        event(
            run_id=run_id,
            sequence=4,
            event_type="forecast_generated",
            product=tertiary,
            payload={
                "product_id": str(tertiary["id"]),
                "store_id": "krakow-marketplace",
                "predicted_demand": "42",
                "horizon": "next_24h",
                "confidence": "0.84",
            },
            occurred_at=now - timedelta(minutes=5, seconds=10),
            ingested_delay_seconds=10,
        ),
        event(
            run_id=run_id,
            sequence=5,
            event_type="anomaly_detected",
            product=primary,
            payload={
                "product_id": str(primary["id"]),
                "store_id": "warsaw-flagship",
                "metric": "checkout_conversion",
                "actual": "0.19",
                "expected": "0.31",
                "severity": "high",
            },
            occurred_at=now - timedelta(minutes=3, seconds=50),
            ingested_delay_seconds=11,
        ),
        event(
            run_id=run_id,
            sequence=6,
            event_type="alert_created",
            product=primary,
            payload={
                "product_id": str(primary["id"]),
                "alert_id": f"obs-demo-alert-{run_id}",
                "severity": "high",
                "title": "Conversion drop after price and stock movement",
            },
            occurred_at=now - timedelta(minutes=3, seconds=20),
            ingested_delay_seconds=13,
        ),
        event(
            run_id=run_id,
            sequence=7,
            event_type="return_completed",
            product=secondary,
            payload={
                "product_id": str(secondary["id"]),
                "store_id": "gdansk-pop-up",
                "channel": "store",
                "quantity": "1",
                "refund_amount": "179.90",
                "reason": "wrong_size",
            },
            occurred_at=now - timedelta(minutes=2, seconds=15),
            ingested_delay_seconds=8,
        ),
        sale,
        {
            "event_id": stable_event_id(f"{run_id}-99-invalid-schema"),
            "event_type": "unknown_operational_signal",
            "source": "observability-demo",
            "correlation_id": f"obs-demo-{run_id}",
            "occurred_at": iso(now - timedelta(minutes=1)),
            "ingested_at": iso(now - timedelta(seconds=30)),
            "payload": {"reason": "schema_contract_validation_demo"},
        },
    ]
    return events


def main() -> None:
    products = fetch_demo_products()
    if not products:
        raise RuntimeError("No demo products found. Run migrations and seed first.")

    consumer = RealtimeEventConsumer(consumer_name="retailops-observability-demo")
    consumer.start()
    results = consumer.process_events(build_events(products))

    status_counts: dict[str, int] = {}
    for result in results:
        status = str(result.get("status", "unknown"))
        status_counts[status] = status_counts.get(status, 0) + 1

    print(
        json.dumps(
            {
                "scenario": "flash-demand-and-stock-risk",
                "correlation_id": "obs-demo-stream-batch",
                "products": [
                    {
                        "id": str(product["id"]),
                        "sku": product["sku"],
                        "name": product["name"],
                        "category": product["category"],
                    }
                    for product in products
                ],
                "event_results": status_counts,
                "interpretation": [
                    "sale/order traffic should increase live revenue and units sold",
                    "stock_changed should reduce live stock delta",
                    "anomaly_detected and alert_created should appear in stream/business panels",
                    "one duplicate sale should increase ignored duplicate count",
                    "one invalid event should increase dead-letter metrics",
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
