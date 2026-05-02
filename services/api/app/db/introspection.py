"""PostgreSQL schema introspection helpers for MVP repository queries.

Why this exists:
- Sprint 3 schema is still evolving.
- CS-013 should prove DB-backed dashboard/analytics reads without making the
  API fragile when a column name changes during early development.
- The repository layer can choose the first matching known column safely.
"""

from functools import lru_cache

from psycopg import sql

from app.db.connection import fetch_all, fetch_one


@lru_cache(maxsize=128)
def table_exists(table_name: str) -> bool:
    row = fetch_one(
        "SELECT to_regclass(%s) IS NOT NULL AS exists",
        (f"public.{table_name}",),
    )
    return bool(row and row["exists"])


@lru_cache(maxsize=128)
def get_columns(table_name: str) -> set[str]:
    if not table_exists(table_name):
        return set()

    rows = fetch_all(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
        """,
        (table_name,),
    )
    return {str(row["column_name"]) for row in rows}


def pick_column(table_name: str, candidates: list[str]) -> str | None:
    columns = get_columns(table_name)

    for candidate in candidates:
        if candidate in columns:
            return candidate

    return None


def count_rows(table_name: str) -> int:
    if not table_exists(table_name):
        return 0

    query = sql.SQL("SELECT COUNT(*) AS count FROM {}").format(
        sql.Identifier(table_name)
    )
    row = fetch_one(query)
    return int(row["count"]) if row else 0
