from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from uuid import NAMESPACE_DNS, UUID, uuid5

DEMO_NAMESPACE: UUID = uuid5(NAMESPACE_DNS, "retailops-demo-dataset-v1")
BASE_DATE: date = date(2026, 4, 30)
BASE_DATETIME: datetime = datetime(2026, 4, 30, 8, 0, tzinfo=UTC)


@dataclass(frozen=True)
class GenerationClock:
    end_date: date = BASE_DATE

    def at(self, days_back: int, hours: int = 0) -> str:
        base = datetime.combine(self.end_date, time(8), tzinfo=UTC)
        return (base - timedelta(days=days_back) + timedelta(hours=hours)).isoformat()

    def day(self, days_back: int) -> str:
        return (self.end_date - timedelta(days=days_back)).isoformat()


DEFAULT_CLOCK = GenerationClock()


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


def decimal_str(value: float | Decimal, places: int = 4) -> str:
    quant = Decimal(1).scaleb(-places)
    return str(Decimal(str(value)).quantize(quant, rounding=ROUND_HALF_UP))


def confidence(value: float | Decimal) -> str:
    return decimal_str(value, places=4)


def money(value: float | Decimal) -> str:
    return decimal_str(value, places=2)
