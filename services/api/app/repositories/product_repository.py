from typing import Any
from uuid import UUID

from psycopg.rows import dict_row

from app.db.connection import fetch_all, fetch_one
from app.domain.models import Product


class ProductRepository:
    """PostgreSQL-backed read repository for product data.

    The optional connection keeps compatibility with older unit tests and
    service-layer code. When no connection is provided, the repository uses the
    shared DB helpers from app.db.connection, which is convenient for FastAPI
    route/service usage.
    """

    SORT_COLUMNS = {
        "sku": "sku",
        "name": "name",
        "category": "category",
        "status": "status",
        "created_at": "created_at",
    }

    def __init__(self, connection=None):
        self.connection = connection

    def _fetch_all(self, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        if self.connection is None:
            return fetch_all(query, params)

        with self.connection.cursor(row_factory=dict_row) as cur:
            cur.execute(query, params)
            return cur.fetchall()

    def _fetch_one(self, query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        if self.connection is None:
            return fetch_one(query, params)

        with self.connection.cursor(row_factory=dict_row) as cur:
            cur.execute(query, params)
            return cur.fetchone()

    def _map_row_to_product(self, row: dict[str, Any]) -> Product:
        return Product(
            id=row["id"],
            sku=row["sku"],
            name=row["name"],
            category=row["category"],
            brand=row["brand"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _build_filters(
        self,
        category: str | None,
        status: str | None,
        search: str | None,
    ) -> tuple[str, list[Any]]:
        filters = []
        params: list[Any] = []

        if category:
            filters.append("LOWER(category) = LOWER(%s)")
            params.append(category.strip())

        if status:
            filters.append("status = %s")
            params.append(status.strip())

        if search:
            filters.append(
                "(" 
                "LOWER(sku) LIKE LOWER(%s) OR "
                "LOWER(name) LIKE LOWER(%s) OR "
                "LOWER(COALESCE(category, '')) LIKE LOWER(%s)"
                ")"
            )
            pattern = f"%{search.strip()}%"
            params.extend([pattern, pattern, pattern])

        if not filters:
            return "", params

        return "WHERE " + " AND ".join(filters), params

    def list_products(
        self,
        category: str | None = None,
        status: str | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "sku",
        sort_order: str = "asc",
    ) -> list[Product]:
        where_clause, params = self._build_filters(category, status, search)
        sort_column = self.SORT_COLUMNS.get(sort_by, "sku")
        direction = "DESC" if sort_order.lower() == "desc" else "ASC"

        query = f"""
            SELECT
                id,
                sku,
                name,
                category,
                brand,
                status,
                created_at,
                updated_at
            FROM products
            {where_clause}
            ORDER BY {sort_column} {direction}, sku ASC
            LIMIT %s OFFSET %s;
        """
        rows = self._fetch_all(query, tuple(params + [limit, offset]))
        return [self._map_row_to_product(row) for row in rows]

    def count_products(
        self,
        category: str | None = None,
        status: str | None = None,
        search: str | None = None,
    ) -> int:
        where_clause, params = self._build_filters(category, status, search)
        query = f"SELECT COUNT(*) AS total FROM products {where_clause};"
        row = self._fetch_one(query, tuple(params))
        return int(row["total"]) if row else 0

    def get_product_by_id(self, product_id: UUID) -> Product | None:
        row = self._fetch_one(
            """
            SELECT
                id,
                sku,
                name,
                category,
                brand,
                status,
                created_at,
                updated_at
            FROM products
            WHERE id = %s;
            """,
            (product_id,),
        )
        return self._map_row_to_product(row) if row else None

    def get_product_by_sku(self, sku: str) -> Product | None:
        row = self._fetch_one(
            """
            SELECT
                id,
                sku,
                name,
                category,
                brand,
                status,
                created_at,
                updated_at
            FROM products
            WHERE sku = %s;
            """,
            (sku,),
        )
        return self._map_row_to_product(row) if row else None
