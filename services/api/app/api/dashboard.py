from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.schemas import (
    DashboardOperationalVisibilityResponse,
    DashboardRecommendationResponse,
    DashboardSalesTrendResponse,
    DashboardStockRiskSummary,
    DashboardSummaryResponse,
    DashboardWorkItemsResponse,
)
from app.services.dashboard_service import DashboardService


router = APIRouter(prefix="/dashboard", tags=["dashboard"])
dashboard_service = DashboardService()


@router.get(
    "/summary",
    response_model=DashboardSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get dashboard summary",
    description=(
        "Returns compact operational counters for the RetailOps dashboard, "
        "including product, sales, inventory, forecast, anomaly and "
        "recommendation counts."
    ),
)
def get_dashboard_summary():
    return dashboard_service.get_summary()


@router.get(
    "/operational-visibility",
    response_model=DashboardOperationalVisibilityResponse,
    status_code=status.HTTP_200_OK,
    summary="Get operational visibility overview",
    description=(
        "Returns a compact dashboard-ready payload with summary counters, "
        "stock-risk counters, sales trend and open work items. This endpoint "
        "is intentionally read-only and presentation-oriented."
    ),
)
def get_operational_visibility(
    sales_trend_days: Annotated[
        int,
        Query(ge=1, le=90, description="Number of days included in the sales trend."),
    ] = 14,
    work_items_limit: Annotated[
        int,
        Query(ge=1, le=100, description="Maximum number of work items to return."),
    ] = 10,
):
    return dashboard_service.get_operational_visibility(
        sales_trend_days=sales_trend_days,
        work_items_limit=work_items_limit,
    )


@router.get(
    "/sales-trend",
    response_model=DashboardSalesTrendResponse,
    status_code=status.HTTP_200_OK,
    summary="Get dashboard sales trend",
    description="Returns daily sales units and revenue for dashboard charting.",
)
def get_sales_trend(
    days: Annotated[
        int,
        Query(ge=1, le=90, description="Number of trailing days to aggregate."),
    ] = 14,
):
    return dashboard_service.get_sales_trend(days=days)


@router.get(
    "/alerts",
    response_model=DashboardWorkItemsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get dashboard alerts",
    description=(
        "Returns open anomaly-like items for dashboard visibility. The endpoint "
        "keeps the historical /dashboard/alerts contract used after Sprint 3."
    ),
)
def get_dashboard_alerts(
    limit: Annotated[
        int,
        Query(ge=1, le=100, description="Maximum number of alerts to return."),
    ] = 10,
):
    return dashboard_service.get_open_alerts(limit=limit)


@router.get(
    "/recommendations",
    response_model=DashboardRecommendationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get dashboard recommendations",
    description=(
        "Returns recent recommendation-like items for dashboard decision support."
    ),
)
def get_dashboard_recommendations(
    limit: Annotated[
        int,
        Query(ge=1, le=100, description="Maximum number of recommendations to return."),
    ] = 10,
):
    return dashboard_service.get_top_recommendations(limit=limit)


@router.get(
    "/open-work-items",
    response_model=DashboardWorkItemsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get open dashboard work items",
    description=(
        "Returns a combined operational backlog from anomalies and "
        "recommendations. This is useful for a single dashboard widget."
    ),
)
def get_open_work_items(
    limit: Annotated[
        int,
        Query(ge=1, le=100, description="Maximum number of work items to return."),
    ] = 10,
):
    return dashboard_service.get_open_work_items(limit=limit)


@router.get(
    "/stock-risk-summary",
    response_model=DashboardStockRiskSummary,
    status_code=status.HTTP_200_OK,
    summary="Get stock-risk summary",
    description="Returns stock-risk counters for operational dashboard cards.",
)
def get_stock_risk_summary():
    return dashboard_service.get_stock_risk_summary()
