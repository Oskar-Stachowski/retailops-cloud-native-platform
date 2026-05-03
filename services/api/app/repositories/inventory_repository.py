from datetime import datetime
from typing import Any
from uuid import UUID

from psycopg.rows import dict_row

from app.db.connection import fetch_all, fetch_one
from app.domain.models import InventorySnapshot


class InventoryRepository:
    """PostgreSQL-backed read repository for inventory snapshot data."""

    SORT_COLUMNS = {
        "recorded_at": "recorded_at",
        "ingested_at": "ingested_at",
        "created_at": "created_at",
        "stock_quantity": "stock_quantity",
        "warehouse_code": "warehouse_code",
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

    def _map_row_to_inventory_snapshot(self, row: dict[str, Any]) -> InventorySnapshot:
        return InventorySnapshot(
            id=row["id"],
            product_id=row["product_id"],
            stock_quantity=row["stock_quantity"],
            unit_of_measure=row["unit_of_measure"],
            warehouse_code=row["warehouse_code"],
            recorded_at=row["recorded_at"],
            ingested_at=row["ingested_at"],
            created_at=row["created_at"],
        )

    def _build_filters(
        self,
        product_id: UUID | None,
        warehouse_code: str | None,
        unit_of_measure: str | None,
        recorded_from: datetime | None,
        recorded_to: datetime | None,
    ) -> tuple[str, list[Any]]:
        filters = []
        params: list[Any] = []

        if product_id:
            filters.append("product_id = %s")
            params.append(product_id)

        if warehouse_code:
            filters.append("LOWER(warehouse_code) = LOWER(%s)")
            params.append(warehouse_code.strip())

        if unit_of_measure:
            filters.append("unit_of_measure = %s")
            params.append(unit_of_measure.strip())

        if recorded_from:
            filters.append("recorded_at >= %s")
            params.append(recorded_from)

        if recorded_to:
            filters.append("recorded_at <= %s")
            params.append(recorded_to)

        if not filters:
            return "", params

        return "WHERE " + " AND ".join(filters), params

    def list_inventory_snapshots(
        self,
        product_id: UUID | None = None,
        warehouse_code: str | None = None,
        unit_of_measure: str | None = None,
        recorded_from: datetime | None = None,
        recorded_to: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "recorded_at",
        sort_order: str = "desc",
    ) -> list[InventorySnapshot]:
        where_clause, params = self._build_filters(
            product_id=product_id,
            warehouse_code=warehouse_code,
            unit_of_measure=unit_of_measure,
            recorded_from=recorded_from,
            recorded_to=recorded_to,
        )
        sort_column = self.SORT_COLUMNS.get(sort_by, "recorded_at")
        direction = "DESC" if sort_order.lower() == "desc" else "ASC"

        query = f"""
            SELECT
                id,
                product_id,
                stock_quantity,
                unit_of_measure,
                warehouse_code,
                recorded_at,
                ingested_at,
                created_at
            FROM inventory_snapshots
            {where_clause}
            ORDER BY {sort_column} {direction}, id ASC
            LIMIT %s OFFSET %s;
        """
        rows = self._fetch_all(query, tuple(params + [limit, offset]))
        return [self._map_row_to_inventory_snapshot(row) for row in rows]

    def count_inventory_snapshots(
        self,
        product_id: UUID | None = None,
        warehouse_code: str | None = None,
        unit_of_measure: str | None = None,
        recorded_from: datetime | None = None,
        recorded_to: datetime | None = None,
    ) -> int:
        where_clause, params = self._build_filters(
            product_id=product_id,
            warehouse_code=warehouse_code,
            unit_of_measure=unit_of_measure,
            recorded_from=recorded_from,
            recorded_to=recorded_to,
        )
        query = f"SELECT COUNT(*) AS total FROM inventory_snapshots {where_clause};"
        row = self._fetch_one(query, tuple(params))
        return int(row["total"]) if row else 0

    def get_inventory_snapshot_by_id(
        self,
        inventory_snapshot_id: UUID,
    ) -> InventorySnapshot | None:
        row = self._fetch_one(
            """
            SELECT
                id,
                product_id,
                stock_quantity,
                unit_of_measure,
                warehouse_code,
                recorded_at,
                ingested_at,
                created_at
            FROM inventory_snapshots
            WHERE id = %s;
            """,
            (inventory_snapshot_id,),
        )
        return self._map_row_to_inventory_snapshot(row) if row else None
