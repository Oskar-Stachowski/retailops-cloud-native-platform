"""Source-compatible multiset hashing with a bounded SQLite disk sort."""

from __future__ import annotations

import hashlib
import sqlite3
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from data.generator.identity import canonical_cell, canonical_json

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator
    from typing import Self


def canonical_records(rows: Iterable[dict], columns: list[str]) -> Iterator[bytes]:
    for row in rows:
        yield canonical_json({field: canonical_cell(field, row[field]) for field in columns})


class ContentHash:
    """Keep duplicate rows and the existing byte sort without loading the table."""

    def __init__(self, columns: list[str], scratch: Path) -> None:
        self.columns = columns
        self.temporary = tempfile.TemporaryDirectory(prefix=".hash-", dir=scratch)
        self.connection = sqlite3.connect(Path(self.temporary.name) / "records.sqlite")
        self.connection.execute("PRAGMA cache_size=-2048")
        self.connection.execute("PRAGMA temp_store=FILE")
        self.connection.execute("CREATE TABLE records (value BLOB NOT NULL)")
        self.rows = 0

    def add(self, rows: list[dict]) -> None:
        self.connection.executemany(
            "INSERT INTO records VALUES (?)",
            ((record,) for record in canonical_records(rows, self.columns)),
        )
        self.rows += len(rows)

    def digest(self) -> str:
        digest = hashlib.sha256(canonical_json(self.columns) + b"\n")
        for (record,) in self.connection.execute("SELECT value FROM records ORDER BY value"):
            digest.update(record + b"\n")
        return digest.hexdigest()

    def close(self) -> None:
        self.connection.close()
        self.temporary.cleanup()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()
