"""AI 06.6a source integration candidate; publication contracts remain unchanged."""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Any

from data.anomalies.physical_process import PhysicalAnomalySimulator
from data.generator.csv_writer import TABLE_COLUMNS
from data.generator.demand_quality import validate_demand
from data.generator.dimension_schema import DIMENSION_COLUMNS
from data.generator.observation_history import HISTORY_TABLE
from data.generator.pricing_schema import PRICING_COLUMNS
from data.generator.return_schema import RETURN_COLUMNS
from data.generator.simulation_schema import fact_columns
from data.inventory.contract import utc_timestamp
from data.inventory.ledger import InventoryLedger
from data.inventory.legacy import legacy_stock_movements
from data.inventory.projection_contract import ProjectionConfig
from data.inventory.snapshots import daily_snapshots
from data.inventory.source_commerce import SourceCommerceSimulator
from data.inventory.source_foundation import source_foundation
from data.inventory.source_observations import rebuild_observations
from data.inventory.source_reconciliation import reconcile_source_commerce

if TYPE_CHECKING:
    from data.anomalies.contract import AnomalyPlan
    from data.anomalies.physical_contract import PhysicalAnomalyPlan
    from data.generator.configuration import ResolvedGenerationConfig
    from data.inventory.source_contract import SourceInventoryConfig

COMMERCE_TABLES = (
    "products",
    "stores",
    "warehouses",
    "orders",
    "order_items",
    "sales",
    "price_history",
    "promotions",
    *DIMENSION_COLUMNS,
    *(n for n in PRICING_COLUMNS if n != "promotion_effect_truth"),
    "daily_demand_observations",
    "daily_demand_exclusions",
    *RETURN_COLUMNS,
    "returns",
    HISTORY_TABLE,
)


def simulate_source_commerce(
    candidate: dict,
    generation: ResolvedGenerationConfig,
    config: SourceInventoryConfig,
    *,
    anomaly_plan: AnomalyPlan | None = None,
    physical_plan: PhysicalAnomalyPlan | None = None,
) -> dict[str, Any]:
    # Only this unpublished path consumes uncapped baskets as private demand input.
    # Never write these candidate rows into an existing source/snapshot directory.
    validate_demand(candidate, generation, anomaly_plan=anomaly_plan)
    inputs = source_foundation(candidate, generation, config)
    tables = deepcopy(candidate)
    if physical_plan is None:
        simulator = SourceCommerceSimulator(inputs, tables, generation, config)
    else:
        simulator = PhysicalAnomalySimulator(inputs, tables, generation, config, physical_plan)
        inputs["scenario"] = simulator.scenario.model_dump()
    result = simulator.execute()
    if physical_plan is not None:
        result["simulation_truth"]["physical_interventions"] = simulator.applied_caps
    tables["sales"] = [
        {field: row[field] for field in fact_columns("sales", TABLE_COLUMNS["sales"])}
        for row in simulator.actual_sales
    ]
    tables["orders"] = simulator.actual_orders()
    tables["order_items"] = simulator.actual_items
    tables["return_events"] = sorted(simulator.financial_returns, key=lambda r: r["id"])
    rebuild_observations(tables, result["operational"]["sales"], generation)
    result["operational"]["history_end_at"] = simulator.end.isoformat()
    result["operational"]["source_route_versions"] = inputs["source_route_versions"]
    output = {
        "inventory": result["operational"],
        "commerce": {name: tables[name] for name in COMMERCE_TABLES},
        "return_inventory_decisions": sorted(
            simulator.return_decisions, key=lambda r: r["return_id"]
        ),
        "simulation_truth": result["simulation_truth"],
    }
    ledger = InventoryLedger.from_payload(output["inventory"]["ledger"])
    projection = ProjectionConfig.from_payload(
        {
            "contract_version": "inventory-projection-config-1.0.0",
            "process_version": "inventory-projection-1.0.0",
            "business_timezone": "UTC",
            "start_at": simulator.start.isoformat(),
            "end_at": simulator.end.isoformat(),
            "snapshot_policy": "utc_day_last_microsecond",
            "reservation_policy": "none",
            "stock_measure": "available_qty",
            "episode_policy": "zero_after_event_including_instantaneous",
            "diagnostic_horizon_days": 7,
            "truth_delay_seconds": 0,
        }
    )
    output["inventory_snapshots"] = daily_snapshots(ledger, projection)
    output["legacy_stock_movements"] = legacy_stock_movements(ledger)
    output["reconciliation"] = reconcile_source_commerce(
        candidate, output, generation, inputs["scenario"]
    )
    output["effective_configuration"] = inputs
    missing = {"config_unavailable", "inventory_unknown", "history_missing", "supplier_missing"}
    ready = (
        not any(
            d["status"] in missing for r in output["inventory"]["reviews"] for d in r["decisions"]
        )
        and all(r["status"] == "known" for r in output["inventory_snapshots"])
        and all(
            utc_timestamp(r["available_at"]) <= simulator.end
            for r in tables["daily_demand_observations"]
        )
    )
    output["status"] = "passed" if ready else "not_ready"
    return output
