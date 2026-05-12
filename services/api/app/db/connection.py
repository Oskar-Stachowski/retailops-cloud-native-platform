"""Small PostgreSQL connection helper used by repository/query layer.

This module intentionally stays lightweight for the MVP. It uses the existing
DATABASE_URL environment variable and returns dictionary-like rows so repository
code can expose stable API payloads without adding a heavy abstraction layer.
"""

import os
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from typing import Any, Protocol

import psycopg
from psycopg.rows import dict_row

from app.db.instrumentation import instrument_database_call

QueryParams = Mapping[str, Any] | Sequence[Any] | None


class CursorLike(Protocol):
    def execute(self, query: object, params: QueryParams = None) -> object: ...

    def fetchone(self) -> object: ...

    def fetchall(self) -> Sequence[Mapping[str, Any]]: ...


def get_database_url() -> str:
    """Return DATABASE_URL or fail early with a clear local-dev message."""
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        msg = (
            "DATABASE_URL is not set. Configure it in your shell, .env, "
            "Docker Compose, or GitHub Actions before using DB-backed endpoints."
        )
        raise RuntimeError(
            msg,
        )

    return database_url


def check_database_connection() -> bool:
    try:
        with (
            psycopg.connect(get_database_url(), connect_timeout=3) as connection,
            connection.cursor() as cursor,
        ):
            query = "SELECT 1"
            result = instrument_database_call(
                operation="health_check",
                query=query,
                callback=lambda: _fetch_health_check(cursor, query),
                row_count=lambda row: 1 if row is not None else 0,
            )

        return result is not None and result[0] == 1

    except (psycopg.Error, RuntimeError):
        return False


@contextmanager
def get_connection() -> Iterator[psycopg.Connection]:
    """Open a PostgreSQL connection with rows returned as dictionaries."""
    with psycopg.connect(get_database_url(), row_factory=dict_row) as connection:
        yield connection


def fetch_all(query: object, params: QueryParams = None) -> list[dict[str, Any]]:
    """Execute a SELECT query and return all rows as plain dictionaries."""
    with get_connection() as connection, connection.cursor() as cursor:
        return instrument_database_call(
            operation="fetch_all",
            query=query,
            callback=lambda: _fetch_all(cursor, query, params),
            row_count=len,
        )


def fetch_one(query: object, params: QueryParams = None) -> dict[str, Any] | None:
    """Execute a SELECT query and return one row as a plain dictionary."""
    with get_connection() as connection, connection.cursor() as cursor:
        return instrument_database_call(
            operation="fetch_one",
            query=query,
            callback=lambda: _fetch_one(cursor, query, params),
            row_count=lambda row: 1 if row is not None else 0,
        )


def _fetch_health_check(cursor: CursorLike, query: object) -> object:
    cursor.execute(query)
    return cursor.fetchone()


def _fetch_all(
    cursor: CursorLike,
    query: object,
    params: QueryParams,
) -> list[dict[str, Any]]:
    cursor.execute(query, params)
    return [dict(row) for row in cursor.fetchall()]


def _fetch_one(
    cursor: CursorLike,
    query: object,
    params: QueryParams,
) -> dict[str, Any] | None:
    cursor.execute(query, params)
    row = cursor.fetchone()
    return dict(row) if row is not None else None
