"""JSON serialization helpers for repository/service payloads."""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID


def make_json_safe(value: object) -> object:
    """Convert DB/domain-native Python values into JSON-friendly structures."""
    if isinstance(value, datetime | date):
        return value.isoformat()

    if isinstance(value, Decimal):
        return float(value)

    if isinstance(value, UUID):
        return str(value)

    if isinstance(value, Enum):
        return value.value

    if isinstance(value, list):
        return [make_json_safe(item) for item in value]

    if isinstance(value, tuple):
        return [make_json_safe(item) for item in value]

    if isinstance(value, dict):
        return {key: make_json_safe(item) for key, item in value.items()}

    return value
