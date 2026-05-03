from datetime import datetime
from enum import Enum
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path, Query, status

from app.api.schemas import SaleListResponse, SaleResponse
from app.domain.models import Channel, Currency
from app.services.sales_service import SalesService


router = APIRouter(prefix="/sales", tags=["sales"])
sales_service = SalesService()


class SaleSortBy(str, Enum):
    sold_at = "sold_at"
    created_at = "created_at"
    quantity = "quantity"
    unit_price = "unit_price"
    total_amount = "total_amount"
    channel = "channel"


class SortOrder(str, Enum):
    asc = "asc"
    desc = "desc"


@router.get(
    "",
    response_model=SaleListResponse,
    status_code=status.HTTP_200_OK,
    summary="List sales records",
    description=(
        "Returns product-level sales records using the stable list response "
        "contract with items and pagination metadata."
    ),
)
def list_sales(
    product_id: Annotated[
        UUID | None,
        Query(description="Filter sales for one product."),
    ] = None,
    channel: Annotated[
        Channel | None,
        Query(description="Filter by sales channel."),
    ] = None,
    currency: Annotated[
        Currency | None,
        Query(description="Filter by currency."),
    ] = None,
    sold_from: Annotated[
        datetime | None,
        Query(description="Filter sales sold at or after this timestamp."),
    ] = None,
    sold_to: Annotated[
        datetime | None,
        Query(description="Filter sales sold at or before this timestamp."),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    sort_by: Annotated[SaleSortBy, Query(description="Sort field.")] = SaleSortBy.sold_at,
    sort_order: Annotated[SortOrder, Query(description="Sort direction.")] = SortOrder.desc,
) -> dict:
    return sales_service.list_sales_response(
        product_id=product_id,
        channel=channel.value if channel else None,
        currency=currency.value if currency else None,
        sold_from=sold_from,
        sold_to=sold_to,
        limit=limit,
        offset=offset,
        sort_by=sort_by.value,
        sort_order=sort_order.value,
    )


@router.get(
    "/{sale_id}",
    response_model=SaleResponse,
    status_code=status.HTTP_200_OK,
    summary="Get sale details",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Sale was not found.",
        }
    },
)
def get_sale(
    sale_id: Annotated[UUID, Path(description="Sale technical identifier.")]
) -> dict:
    sale = sales_service.get_sale_detail_response(sale_id)

    if sale is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    return sale
