from datetime import datetime
from enum import Enum
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path, Query, status

from app.api.schemas import InventorySnapshotListResponse, InventorySnapshotResponse
from app.domain.models import UnitOfMeasure
from app.services.inventory_service import InventoryService


router = APIRouter(prefix="/inventory-snapshots", tags=["inventory"])
inventory_service = InventoryService()


class InventorySortBy(str, Enum):
    recorded_at = "recorded_at"
    ingested_at = "ingested_at"
    created_at = "created_at"
    stock_quantity = "stock_quantity"
    warehouse_code = "warehouse_code"


class SortOrder(str, Enum):
    asc = "asc"
    desc = "desc"


@router.get(
    "",
    response_model=InventorySnapshotListResponse,
    status_code=status.HTTP_200_OK,
    summary="List inventory snapshots",
    description=(
        "Returns inventory snapshots using the stable list response contract "
        "with items and pagination metadata."
    ),
)
def list_inventory_snapshots(
    product_id: Annotated[
        UUID | None,
        Query(description="Filter inventory snapshots for one product."),
    ] = None,
    warehouse_code: Annotated[
        str | None,
        Query(min_length=1, description="Filter by warehouse/location code."),
    ] = None,
    unit_of_measure: Annotated[
        UnitOfMeasure | None,
        Query(description="Filter by inventory unit of measure."),
    ] = None,
    recorded_from: Annotated[
        datetime | None,
        Query(description="Filter snapshots recorded at or after this timestamp."),
    ] = None,
    recorded_to: Annotated[
        datetime | None,
        Query(description="Filter snapshots recorded at or before this timestamp."),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    sort_by: Annotated[InventorySortBy, Query(description="Sort field.")] = (
        InventorySortBy.recorded_at
    ),
    sort_order: Annotated[SortOrder, Query(description="Sort direction.")] = SortOrder.desc,
) -> dict:
    return inventory_service.list_inventory_snapshots_response(
        product_id=product_id,
        warehouse_code=warehouse_code,
        unit_of_measure=unit_of_measure.value if unit_of_measure else None,
        recorded_from=recorded_from,
        recorded_to=recorded_to,
        limit=limit,
        offset=offset,
        sort_by=sort_by.value,
        sort_order=sort_order.value,
    )


@router.get(
    "/{inventory_snapshot_id}",
    response_model=InventorySnapshotResponse,
    status_code=status.HTTP_200_OK,
    summary="Get inventory snapshot details",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Inventory snapshot was not found.",
        }
    },
)
def get_inventory_snapshot(
    inventory_snapshot_id: Annotated[
        UUID,
        Path(description="Inventory snapshot technical identifier."),
    ]
) -> dict:
    inventory_snapshot = inventory_service.get_inventory_snapshot_detail_response(
        inventory_snapshot_id
    )

    if inventory_snapshot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    return inventory_snapshot
