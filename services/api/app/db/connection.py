"""Small PostgreSQL connection helper used by repository/query layer.

This module intentionally stays lightweight for the MVP. It uses the existing
DATABASE_URL environment variable and returns dictionary-like rows so repository
code can expose stable API payloads without adding a heavy abstraction layer.
"""

from collections.abc import Mapping, Sequence
from contextlib import contextmanager
import os
from typing import Any, Iterator

import psycopg
from psycopg.rows import dict_row

QueryParams = Mapping[str, Any] | Sequence[Any] | None


def get_database_url() -> str:
    """Return DATABASE_URL or fail early with a clear local-dev message."""
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is not set. Configure it in your shell, .env, "
            "Docker Compose, or GitHub Actions before using DB-backed endpoints."
        )

    return database_url


def check_database_connection() -> bool:
    try:
        with psycopg.connect(get_database_url(), connect_timeout=3) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()

        return result is not None and result[0] == 1

    except (psycopg.Error, RuntimeError):
        return False


@contextmanager
def get_connection() -> Iterator[psycopg.Connection]:
    """Open a PostgreSQL connection with rows returned as dictionaries."""
    with psycopg.connect(get_database_url(), row_factory=dict_row) as connection:
        yield connection


def fetch_all(query: Any, params: QueryParams = None) -> list[dict[str, Any]]:
    """Execute a SELECT query and return all rows as plain dictionaries."""
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]


def fetch_one(query: Any, params: QueryParams = None) -> dict[str, Any] | None:
    """Execute a SELECT query and return one row as a plain dictionary."""
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            row = cursor.fetchone()
            return dict(row) if row is not None else None
