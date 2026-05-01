from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from uuid import NAMESPACE_DNS, UUID, uuid5

DEMO_NAMESPACE: UUID = uuid5(NAMESPACE_DNS, "retailops-demo-dataset-v1")
BASE_DATE: date = date(2026, 4, 30)
BASE_DATETIME: datetime = datetime(2026, 4, 30, 8, 0, tzinfo=timezone.utc)


def deterministic_uuid(entity: str, natural_key: str) -> str:
    """Return a stable UUID generated from a business-natural key."""
    return str(uuid5(DEMO_NAMESPACE, f"{entity}:{natural_key}"))


def utc_datetime(
    days_offset: int = 0,
    hours_offset: int = 0,
    minutes_offset: int = 0,
) -> str:
    value = BASE_DATETIME + timedelta(
        days=days_offset,
        hours=hours_offset,
        minutes=minutes_offset,
    )
    return value.isoformat()


def iso_date(days_offset: int = 0) -> str:
    return (BASE_DATE + timedelta(days=days_offset)).isoformat()


def decimal_str(value: int | float | Decimal, places: int = 4) -> str:
    quant = Decimal("1").scaleb(-places)
    return str(Decimal(str(value)).quantize(quant, rounding=ROUND_HALF_UP))


def confidence(value: int | float | Decimal) -> str:
    return decimal_str(value, places=4)


def money(value: int | float | Decimal) -> str:
    return decimal_str(value, places=4)
