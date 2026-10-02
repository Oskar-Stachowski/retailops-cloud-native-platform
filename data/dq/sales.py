"""Operational allowlist for the bounded legacy sales projection."""

from __future__ import annotations

from decimal import Decimal

from services.api.app.services.realtime_contract import validate_event

from data.generator.identity import json_sha256
from data.generator.realtime import DEFAULT_SOURCE
from data.inventory.contract import require, utc_timestamp

PAYLOAD_FIELDS = frozenset(
    {
        "sale_id",
        "order_id",
        "order_item_id",
        "product_id",
        "sku",
        "store_id",
        "channel",
        "quantity",
        "unit_price",
        "total_amount",
        "currency",
        "promotion_applied",
    }
)
GRAIN = ("business_date", "product_id", "store_id", "channel", "currency")


def sale_fact(event: dict, transport_topic: str) -> dict:
    validate_event(event, transport_topic=transport_topic)
    require(event["event_type"] == "sale_completed", "unsupported_offline_event_type")
    require(event["source"] == DEFAULT_SOURCE, "unsupported_offline_source")
    payload = event["payload"]
    require(set(payload) <= PAYLOAD_FIELDS, "unsupported_offline_payload_field")
    require(bool(payload.get("sale_id")), "missing_business_key")
    require(payload.get("currency") in {"PLN", "EUR"}, "unsupported_currency")
    quantity, amount = Decimal(payload["quantity"]), Decimal(payload["total_amount"])
    require(quantity.is_finite() and 0 < quantity <= 10**9, "invalid_sale_quantity")
    require(quantity == quantity.to_integral_value(), "fractional_sale_quantity")
    require(amount.is_finite() and 0 <= amount <= 10**12, "invalid_sale_amount")
    require(amount == amount.quantize(Decimal("0.01")), "invalid_sale_precision")
    occurred, ingested = utc_timestamp(event["occurred_at"]), utc_timestamp(event["ingested_at"])
    require(occurred <= ingested, "ingestion_precedes_event")
    # SKU is optional descriptive context; it never distinguishes business facts.
    payload_version = {k: v for k, v in payload.items() if k != "sku"}
    payload_version.update(quantity=str(int(quantity)), total_amount=f"{amount:.2f}")
    if "unit_price" in payload_version:
        price = Decimal(payload_version["unit_price"])
        require(price.is_finite() and 0 <= price <= 10**12, "invalid_unit_price")
        require(price == price.quantize(Decimal("0.01")), "invalid_unit_price_precision")
        require(price * quantity == amount, "invalid_sale_total")
        payload_version["unit_price"] = f"{price:.2f}"
    return {
        "source": event["source"],
        "sale_id": payload["sale_id"],
        "business_date": occurred.date().isoformat(),
        "product_id": payload["product_id"],
        "store_id": payload["store_id"],
        "channel": payload["channel"],
        "currency": payload["currency"],
        "quantity": int(quantity),
        "total_amount": f"{amount:.2f}",
        "occurred_at": occurred.isoformat(),
        "ingested_at": ingested.isoformat(),
        "business_version_sha256": json_sha256(
            {"occurred_at": occurred.isoformat(), "payload": payload_version}
        ),
    }


def fact_totals(facts: list[dict]) -> list[dict]:
    grouped: dict[tuple, dict] = {}
    for fact in facts:
        key = tuple(fact[k] for k in GRAIN)
        current = grouped.setdefault(
            key,
            {
                **dict(zip(GRAIN, key, strict=True)),
                "quantity": 0,
                "total_amount": "0.00",
                "fact_count": 0,
            },
        )
        current["quantity"] += fact["quantity"]
        current["total_amount"] = (
            f"{Decimal(current['total_amount']) + Decimal(fact['total_amount']):.2f}"
        )
        current["fact_count"] += 1
    return [grouped[k] for k in sorted(grouped)]
