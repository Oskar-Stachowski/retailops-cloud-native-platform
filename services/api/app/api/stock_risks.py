from enum import Enum
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.schemas import StockRiskListResponse
from app.services.stock_risk_service import StockRiskService


router = APIRouter(prefix="/inventory-risks", tags=["stock-risk"])
stock_risk_service = StockRiskService()


class RiskStatus(str, Enum):
    normal = "normal"
    stockout_risk = "stockout_risk"
    overstock_risk = "overstock_risk"
    unknown = "unknown"


class StockRiskSortBy(str, Enum):
    risk_status = "risk_status"
    sku = "sku"
    current_stock = "current_stock"
    forecast_quantity = "forecast_quantity"
    inventory_updated_at = "inventory_updated_at"


class SortOrder(str, Enum):
    asc = "asc"
    desc = "desc"


@router.get(
    "",
    response_model=StockRiskListResponse,
    status_code=status.HTTP_200_OK,
    summary="List product stock risks",
    description=(
        "Returns product-level stock risk classification based on latest "
        "inventory and forecast signals."
    ),
)
def list_inventory_risks(
    risk_status: Annotated[
        RiskStatus | None,
        Query(description="Filter by stock risk status."),
    ] = None,
    category: Annotated[
        str | None,
        Query(min_length=1, description="Filter by product category."),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    sort_by: Annotated[StockRiskSortBy, Query(description="Sort field.")] = (
        StockRiskSortBy.risk_status
    ),
    sort_order: Annotated[SortOrder, Query(description="Sort direction.")] = SortOrder.asc,
) -> dict:
    return stock_risk_service.list_inventory_risks_response(
        risk_status=risk_status.value if risk_status else None,
        category=category,
        limit=limit,
        offset=offset,
        sort_by=sort_by.value,
        sort_order=sort_order.value,
    )
