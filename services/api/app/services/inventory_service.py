from datetime import datetime
from uuid import UUID

from app.domain.models import InventorySnapshot
from app.repositories.inventory_repository import InventoryRepository
from app.services.serialization import make_json_safe


class InventoryService:
    """Application service for inventory snapshot reads."""

    def __init__(self, inventory_repository: InventoryRepository | None = None):
        self.inventory_repository = inventory_repository or InventoryRepository()

    def list_inventory_snapshots(
        self,
        product_id: UUID | None = None,
        warehouse_code: str | None = None,
        unit_of_measure: str | None = None,
        recorded_from: datetime | None = None,
        recorded_to: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "recorded_at",
        sort_order: str = "desc",
    ) -> list[InventorySnapshot]:
        return self.inventory_repository.list_inventory_snapshots(
            product_id=product_id,
            warehouse_code=warehouse_code,
            unit_of_measure=unit_of_measure,
            recorded_from=recorded_from,
            recorded_to=recorded_to,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
        )

    def get_inventory_snapshot_by_id(
        self,
        inventory_snapshot_id: UUID,
    ) -> InventorySnapshot | None:
        return self.inventory_repository.get_inventory_snapshot_by_id(
            inventory_snapshot_id
        )

    def list_inventory_snapshots_response(
        self,
        product_id: UUID | None = None,
        warehouse_code: str | None = None,
        unit_of_measure: str | None = None,
        recorded_from: datetime | None = None,
        recorded_to: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "recorded_at",
        sort_order: str = "desc",
    ) -> dict:
        inventory_snapshots = self.inventory_repository.list_inventory_snapshots(
            product_id=product_id,
            warehouse_code=warehouse_code,
            unit_of_measure=unit_of_measure,
            recorded_from=recorded_from,
            recorded_to=recorded_to,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        total = self.inventory_repository.count_inventory_snapshots(
            product_id=product_id,
            warehouse_code=warehouse_code,
            unit_of_measure=unit_of_measure,
            recorded_from=recorded_from,
            recorded_to=recorded_to,
        )

        return {
            "items": [
                make_json_safe(inventory_snapshot.model_dump())
                for inventory_snapshot in inventory_snapshots
            ],
            "pagination": {
                "limit": limit,
                "offset": offset,
                "total": total,
            },
        }

    def get_inventory_snapshot_detail_response(
        self,
        inventory_snapshot_id: UUID,
    ) -> dict | None:
        inventory_snapshot = self.get_inventory_snapshot_by_id(inventory_snapshot_id)

        if inventory_snapshot is None:
            return None

        return make_json_safe(inventory_snapshot.model_dump())
