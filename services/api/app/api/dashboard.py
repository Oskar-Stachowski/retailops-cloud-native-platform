"""Dashboard API endpoints backed by repository/query layer."""

from fastapi import APIRouter, Query

from app.services.dashboard_service import dashboard_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", summary="Get dashboard summary metrics")
def get_dashboard_summary() -> dict:
    return dashboard_service.get_summary()


@router.get("/sales-trend", summary="Get daily sales trend for dashboard chart")
def get_sales_trend(
    days: int = Query(default=14, ge=1, le=90),
) -> dict:
    return dashboard_service.get_sales_trend(days=days)


@router.get("/alerts", summary="Get open dashboard alerts")
def get_open_alerts(
    limit: int = Query(default=10, ge=1, le=100),
) -> dict:
    return dashboard_service.get_open_alerts(limit=limit)


@router.get("/recommendations", summary="Get top dashboard recommendations")
def get_top_recommendations(
    limit: int = Query(default=10, ge=1, le=100),
) -> dict:
    return dashboard_service.get_top_recommendations(limit=limit)
