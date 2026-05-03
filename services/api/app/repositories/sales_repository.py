from datetime import datetime
from typing import Any
from uuid import UUID

from psycopg.rows import dict_row

from app.db.connection import fetch_all, fetch_one
from app.domain.models import Sale


class SalesRepository:
    """PostgreSQL-backed read repository for product-level sales data."""

    SORT_COLUMNS = {
        "sold_at": "sold_at",
        "created_at": "created_at",
        "quantity": "quantity",
        "unit_price": "unit_price",
        "total_amount": "total_amount",
        "channel": "channel",
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

    def _map_row_to_sale(self, row: dict[str, Any]) -> Sale:
        return Sale(
            id=row["id"],
            product_id=row["product_id"],
            quantity=row["quantity"],
            sold_at=row["sold_at"],
            unit_price=row["unit_price"],
            total_amount=row["total_amount"],
            currency=row["currency"],
            channel=row["channel"],
            created_at=row["created_at"],
        )

    def _build_filters(
        self,
        product_id: UUID | None,
        channel: str | None,
        currency: str | None,
        sold_from: datetime | None,
        sold_to: datetime | None,
    ) -> tuple[str, list[Any]]:
        filters = []
        params: list[Any] = []

        if product_id:
            filters.append("product_id = %s")
            params.append(product_id)

        if channel:
            filters.append("channel = %s")
            params.append(channel.strip())

        if currency:
            filters.append("currency = %s")
            params.append(currency.strip())

        if sold_from:
            filters.append("sold_at >= %s")
            params.append(sold_from)

        if sold_to:
            filters.append("sold_at <= %s")
            params.append(sold_to)

        if not filters:
            return "", params

        return "WHERE " + " AND ".join(filters), params

    def list_sales(
        self,
        product_id: UUID | None = None,
        channel: str | None = None,
        currency: str | None = None,
        sold_from: datetime | None = None,
        sold_to: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "sold_at",
        sort_order: str = "desc",
    ) -> list[Sale]:
        where_clause, params = self._build_filters(
            product_id=product_id,
            channel=channel,
            currency=currency,
            sold_from=sold_from,
            sold_to=sold_to,
        )
        sort_column = self.SORT_COLUMNS.get(sort_by, "sold_at")
        direction = "DESC" if sort_order.lower() == "desc" else "ASC"

        query = f"""
            SELECT
                id,
                product_id,
                quantity,
                sold_at,
                unit_price,
                total_amount,
                currency,
                channel,
                created_at
            FROM sales
            {where_clause}
            ORDER BY {sort_column} {direction}, id ASC
            LIMIT %s OFFSET %s;
        """
        rows = self._fetch_all(query, tuple(params + [limit, offset]))
        return [self._map_row_to_sale(row) for row in rows]

    def count_sales(
        self,
        product_id: UUID | None = None,
        channel: str | None = None,
        currency: str | None = None,
        sold_from: datetime | None = None,
        sold_to: datetime | None = None,
    ) -> int:
        where_clause, params = self._build_filters(
            product_id=product_id,
            channel=channel,
            currency=currency,
            sold_from=sold_from,
            sold_to=sold_to,
        )
        query = f"SELECT COUNT(*) AS total FROM sales {where_clause};"
        row = self._fetch_one(query, tuple(params))
        return int(row["total"]) if row else 0

    def get_sale_by_id(self, sale_id: UUID) -> Sale | None:
        row = self._fetch_one(
            """
            SELECT
                id,
                product_id,
                quantity,
                sold_at,
                unit_price,
                total_amount,
                currency,
                channel,
                created_at
            FROM sales
            WHERE id = %s;
            """,
            (sale_id,),
        )
        return self._map_row_to_sale(row) if row else None
