"""Bounded live pages in one read-only transaction; never a multi-page snapshot."""

from __future__ import annotations

from typing import Any

import psycopg
from psycopg.rows import dict_row

from app.api.source_queries import (
    ForecastsQuery,
    InventoryQuery,
    ProductsQuery,
    RisksQuery,
    SalesQuery,
)
from app.db.connection import get_database_url
from app.repositories.forecast_repository import ForecastRepository
from app.repositories.inventory_repository import InventoryRepository
from app.repositories.product_repository import ProductRepository
from app.repositories.sales_repository import SalesRepository
from app.repositories.stock_risk_repository import StockRiskRepository
from app.services.forecast_service import ForecastService
from app.services.inventory_service import InventoryService
from app.services.sales_service import SalesService

PageQuery = ProductsQuery | SalesQuery | InventoryQuery | ForecastsQuery | RisksQuery


def read_page(query: PageQuery) -> dict[str, Any]:
    with psycopg.connect(get_database_url(), connect_timeout=3, row_factory=dict_row) as connection:
        connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        connection.execute("SET LOCAL statement_timeout = '3000ms'")
        arguments = query.model_dump(mode="python", exclude_none=True)
        # Repository/service filters use string enum values, not Enum reprs.
        for key, value in arguments.items():
            if hasattr(value, "value"):
                arguments[key] = value.value
        if isinstance(query, SalesQuery):
            return SalesService(SalesRepository(connection)).list_sales_response(**arguments)
        if isinstance(query, InventoryQuery):
            return InventoryService(
                InventoryRepository(connection)
            ).list_inventory_snapshots_response(**arguments)
        if isinstance(query, ForecastsQuery):
            return ForecastService(ForecastRepository(connection)).list_forecasts_response(
                **arguments
            )
        if isinstance(query, ProductsQuery):
            product = ProductRepository(connection).get_product_by_id(query.product_id)
            items = []
            if product is not None:
                row = product.model_dump(mode="json")
                category_ok = (
                    query.category is None
                    or (row["category"] or "").lower() == query.category.strip().lower()
                )
                status_ok = query.status is None or row["status"] == query.status.value
                searchable = " ".join(
                    str(row.get(k) or "") for k in ("sku", "name", "brand", "category")
                ).lower()
                search_ok = query.search is None or query.search.strip().lower() in searchable
                if category_ok and status_ok and search_ok:
                    items = [row]
            return {
                "items": items[query.offset : query.offset + query.limit],
                "pagination": {"limit": query.limit, "offset": query.offset, "total": len(items)},
            }
        # This is the legacy product heuristic, explicitly granted as a resource.
        # No warehouse-limited principal is implicitly allowed this wider view.
        repository = StockRiskRepository(connection)
        sql = repository._build_risk_view_query()  # noqa: SLF001 - reuse the existing public semantics
        sql += " WHERE product_id::uuid = %s"
        params: list[Any] = [query.product_id]
        if query.risk_status is not None:
            sql += " AND risk_status = %s"
            params.append(query.risk_status.value)
        if query.category is not None:
            sql += " AND LOWER(COALESCE(category, '')) = LOWER(%s)"
            params.append(query.category.strip())
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            risk_row = cursor.fetchone()
        items = [risk_row] if risk_row is not None else []
        return {
            "items": items[query.offset : query.offset + query.limit],
            "pagination": {"limit": query.limit, "offset": query.offset, "total": len(items)},
        }
