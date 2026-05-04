from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path, Query, status

from app.api.schemas import Product360Response
from app.services.product_360_service import product_360_service


router = APIRouter(prefix="/products", tags=["product-360"])


@router.get(
    "/{product_id}/360",
    response_model=Product360Response,
    status_code=status.HTTP_200_OK,
    summary="Get Product 360 view",
    description=(
        "Returns a read-only product drill-down composed from product, sales, "
        "inventory, forecast, anomaly, alert, recommendation and workflow tables."
    ),
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Product was not found.",
        }
    },
)
def get_product_360(
    product_id: Annotated[UUID, Path(description="Product technical identifier.")],
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=50,
            description="Maximum number of related rows returned per section.",
        ),
    ] = 10,
) -> dict:
    product_360 = product_360_service.get_product_360(product_id, limit=limit)

    if product_360 is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    return product_360
