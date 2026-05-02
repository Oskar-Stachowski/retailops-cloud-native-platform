from enum import Enum
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path, Query, status

from app.api.schemas import ProductListResponse, ProductResponse
from app.domain.models import ProductStatus
from app.services.product_service import ProductService


router = APIRouter(prefix="/products", tags=["products"])
product_service = ProductService()


class ProductSortBy(str, Enum):
    sku = "sku"
    name = "name"
    category = "category"
    status = "status"
    created_at = "created_at"


class SortOrder(str, Enum):
    asc = "asc"
    desc = "desc"


@router.get(
    "",
    response_model=ProductListResponse,
    status_code=status.HTTP_200_OK,
    summary="List products",
    description=(
        "Returns products using a stable list response contract with "
        "items and pagination metadata. Supports MVP filters and sorting."
    ),
)
def list_products(
    category: Annotated[str | None, Query(description="Filter by product category.")] = None,
    status_filter: Annotated[
        ProductStatus | None,
        Query(alias="status", description="Filter by product lifecycle status."),
    ] = None,
    search: Annotated[
        str | None,
        Query(min_length=1, description="Search in SKU, name or category."),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    sort_by: Annotated[ProductSortBy, Query(description="Sort field.")] = ProductSortBy.sku,
    sort_order: Annotated[SortOrder, Query(description="Sort direction.")] = SortOrder.asc,
) -> dict:
    return product_service.list_products_response(
        category=category,
        status=status_filter.value if status_filter else None,
        search=search,
        limit=limit,
        offset=offset,
        sort_by=sort_by.value,
        sort_order=sort_order.value,
    )


@router.get(
    "/{product_id}",
    response_model=ProductResponse,
    status_code=status.HTTP_200_OK,
    summary="Get product details",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Product was not found.",
        }
    },
)
def get_product(
    product_id: Annotated[UUID, Path(description="Product technical identifier.")]
) -> dict:
    product = product_service.get_product_detail_response(product_id)

    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    return product
