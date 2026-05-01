from uuid import UUID
from psycopg.rows import dict_row

from app.domain.models import Product


class ProductRepository:
    def __init__(self, connection):
        self.connection = connection

    def _map_row_to_product(self, row) -> Product:
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

    def list_products(self) -> list[Product]:
        with self.connection.cursor(row_factory=dict_row) as cur:
            cur.execute(
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
                ORDER BY sku;
                """
            )
            rows = cur.fetchall()
            return [self._map_row_to_product(row) for row in rows]

    def get_product_by_id(self, product_id: UUID) -> Product | None:
        with self.connection.cursor(row_factory=dict_row) as cur:
            cur.execute(
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
            row = cur.fetchone()
            return self._map_row_to_product(row) if row else None

    def get_product_by_sku(self, sku: str) -> Product | None:
        with self.connection.cursor(row_factory=dict_row) as cur:
            cur.execute(
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
            row = cur.fetchone()
            return self._map_row_to_product(row) if row else None
