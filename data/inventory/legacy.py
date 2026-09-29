from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from data.inventory.ledger import InventoryLedger


def legacy_stock_movements(ledger: InventoryLedger) -> list[dict[str, str]]:
    """Project a validated v1 ledger to the existing, lossy seed/API format."""
    codes = dict(ledger.stock_location_codes)
    aliases = {"opening_stock": "initial_stock", "replenishment_received": "replenishment"}
    return [
        {
            "id": m.inventory_event_id,
            "product_id": m.product_id,
            "warehouse_id": m.stock_location_id,
            "warehouse_code": codes[m.stock_location_id],
            "movement_type": aliases.get(m.movement_type, m.movement_type),
            "quantity": str(m.quantity_delta),
            "unit_of_measure": m.unit_of_measure,
            "source_reference": m.source_reference,
            "occurred_at": m.occurred_at,
            "created_at": m.ingested_at,
        }
        for m in ledger.movements
    ]
