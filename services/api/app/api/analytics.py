"""Analytics API endpoints backed by PostgreSQL read models."""

from fastapi import APIRouter, Query

from app.services.analytics_service import analytics_service

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/products", summary="Get product-level performance summary")
def get_product_performance(
    limit: int = Query(default=50, ge=1, le=200),
) -> dict:
    return analytics_service.get_product_performance(limit=limit)


@router.get("/inventory-risk", summary="Get product inventory risk summary")
def get_inventory_risk(
    limit: int = Query(default=50, ge=1, le=200),
) -> dict:
    return analytics_service.get_inventory_risk(limit=limit)
