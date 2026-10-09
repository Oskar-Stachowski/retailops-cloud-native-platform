"""Schema identity, null/clock/precision rejection and bounded cache lifetime."""

from datetime import date, datetime, timezone
from decimal import Decimal

import pyarrow as pa
import pytest

from data.export.schema import _conversion_plan, typed_row


def test_same_names_different_types_and_nullability_do_not_share_wrong_conversion():
    scalar = pa.schema([pa.field("business_date", pa.string(), nullable=True)])
    day = pa.schema([pa.field("business_date", pa.date32(), nullable=False)])
    assert typed_row({"business_date": "2026-07-01"}, scalar) == {"business_date": "2026-07-01"}
    assert typed_row({"business_date": "2026-07-01"}, day) == {"business_date": date(2026, 7, 1)}
    assert typed_row({"business_date": ""}, scalar) == {"business_date": None}
    with pytest.raises(ValueError, match="Forbidden null"):
        typed_row({"business_date": ""}, day)


def test_metadata_changes_and_schema_replacement_preserve_native_timestamp_and_decimal_checks():
    schema = pa.schema([
        pa.field("available_at", pa.timestamp("us", tz="UTC")),
        pa.field("price", pa.decimal128(38, 2)),
    ])
    for current in (schema, schema.with_metadata({b"test": b"different"})):
        assert typed_row({"available_at": "2026-07-01T00:00:00Z", "price": "1.20"}, current) == {
            "available_at": datetime(2026, 7, 1, tzinfo=timezone.utc), "price": Decimal("1.20")
        }
        with pytest.raises(ValueError, match="microsecond"):
            typed_row({"available_at": "2026-07-01T00:00:00.1234567Z", "price": "1.20"}, current)
        with pytest.raises(ValueError, match="width/columns"):
            typed_row({"available_at": "bad"}, current)
    renamed = schema.set(0, pa.field("ingested_at", pa.timestamp("us", tz="UTC")))
    with pytest.raises(ValueError, match="width/columns"):
        typed_row({"available_at": "2026-07-01T00:00:00Z", "price": "1.20"}, renamed)


def test_cache_evicts_old_schemas_and_returns_only_immutable_plans():
    _conversion_plan.cache_clear()
    for i in range(140):
        schema = pa.schema([pa.field("field_" + str(i), pa.string())])
        assert typed_row({"field_" + str(i): "value"}, schema) == {"field_" + str(i): "value"}
    assert _conversion_plan.cache_info().currsize == 128
    plan = _conversion_plan(pa.schema([pa.field("price", pa.decimal128(38, 2))]))
    with pytest.raises(TypeError):
        plan[0][0] = "changed"


def test_unhashable_compatible_schema_keeps_original_uncached_behavior():
    schema = pa.schema([pa.field("observed_units", pa.int64(), nullable=False)])
    class Wrapper:
        __hash__ = None
        names = schema.names
        def __iter__(self):
            return iter(schema)
    before = _conversion_plan.cache_info()
    assert typed_row({"observed_units": "7"}, Wrapper()) == {"observed_units": 7}
    assert _conversion_plan.cache_info() == before


def test_custom_schema_does_not_read_later_fields_before_rejecting_the_first_value():
    class LaterField:
        @property
        def name(self):
            raise RuntimeError("Later schema field was accessed too early")

    class Wrapper:
        __hash__ = None
        names = ["price", "later"]

        def __iter__(self):
            return iter((pa.field("price", pa.decimal128(38, 2)), LaterField()))

    with pytest.raises(ValueError, match="Invalid numeric field price"):
        typed_row({"price": "not-number", "later": "unused"}, Wrapper())
