"""Object-aware typed hashes for native integer, boolean, money and UTC columns."""

from __future__ import annotations

import unicodedata
from datetime import UTC, date, datetime
from decimal import Decimal
from itertools import islice
from typing import TYPE_CHECKING, Any

import pyarrow as pa

from data.export.hashing import ContentHash
from data.generator.identity import canonical_json
from data.inventory.contract import require
from data.inventory.source_tables_io import _arrow_value, _native_value

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path


def canonical_cell(value: object) -> object:
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        require(value.is_finite(), "Nonfinite snapshot money/factor.")
        return "0" if not value else format(value.normalize(), "f")
    if isinstance(value, datetime):
        require(
            value.tzinfo is not None and value.utcoffset() == UTC.utcoffset(value),
            "Snapshot instant requires UTC.",
        )
        return value.astimezone(UTC).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    require(isinstance(value, (bool, int)), "Unsupported typed snapshot value.")
    return value


class TypedHash(ContentHash):
    def add(self, rows: list[dict]) -> None:
        self.connection.executemany(
            "INSERT INTO records VALUES (?)",
            ((canonical_json({k: canonical_cell(r[k]) for k in self.columns}),) for r in rows),
        )
        self.rows += len(rows)


def typed_row(row: dict, schema: pa.Schema) -> dict:
    return {
        f.name: _arrow_value(None if row[f.name] == "" and f.nullable else row[f.name], f)
        for f in schema
    }


def source_row(row: dict, *, native: bool) -> dict:
    if native:
        return {k: _native_value(v) for k, v in row.items()}
    return {
        k: ""
        if v is None
        else "true"
        if v is True
        else "false"
        if v is False
        else format(v, "f")
        if isinstance(v, Decimal)
        else str(_native_value(v))
        for k, v in row.items()
    }


def logical(
    name: str,
    rows: Iterable[dict],
    schema: pa.Schema,
    grain: list[str],
    data_class: str,
    scratch: Path,
) -> dict:
    temporal = [f.name for f in schema if pa.types.is_date(f.type) or pa.types.is_timestamp(f.type)]
    ranges: dict[str, Any] = {
        key: {"date_start": None, "date_end": None, "value_count": 0} for key in temporal
    }
    count = 0
    iterator = iter(rows)
    with TypedHash(schema.names, scratch) as digest:
        while batch := list(islice(iterator, 8192)):
            for row in batch:
                for key in temporal:
                    if row[key] is not None:
                        value = row[key].isoformat()[:10]
                        span = ranges[key]
                        span["date_start"] = (
                            value if span["date_start"] is None else min(value, span["date_start"])
                        )
                        span["date_end"] = (
                            value if span["date_end"] is None else max(value, span["date_end"])
                        )
                        span["value_count"] += 1
            digest.add(batch)
            count += len(batch)
        content = digest.digest()
    populated = [r for r in ranges.values() if r["value_count"]]
    date_range = {
        "date_start": min((r["date_start"] for r in populated), default=None),
        "date_end": max((r["date_end"] for r in populated), default=None),
        "value_count": sum(r["value_count"] for r in populated),
    }
    return {
        "table": name,
        "data_class": data_class,
        "row_count": count,
        "content_sha256": content,
        "grain": grain,
        "date_range": date_range,
        "field_ranges": ranges,
        "schema": [{"name": f.name, "type": str(f.type), "nullable": f.nullable} for f in schema],
    }
