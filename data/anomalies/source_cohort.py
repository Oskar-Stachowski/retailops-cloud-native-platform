"""Pinned cached execution of the existing demand and physical Source 2.8 plans.

Ordinary simulation, plans, schemas and publication validators stay unchanged.
The complete physical scenario is captured before queued typed rows can expire;
its doubled demand sequences and every stock-cap/return intervention are retained.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TYPE_CHECKING, Any

from data.anomalies.candidate_io import parse_candidate_plan
from data.anomalies.contract import AnomalyPlan
from data.anomalies.physical_contract import PhysicalAnomalyPlan
from data.anomalies.physical_process import PhysicalAnomalySimulator
from data.anomalies.source_scope import require_source_scenario_scope
from data.generator.configuration import resolve_generation_config
from data.generator.csv_writer import TABLE_COLUMNS
from data.generator.demand_quality import validate_demand
from data.generator.main import build_dataset
from data.generator.pricing_plans import daily_price_observations
from data.generator.progress import stage
from data.generator.simulation_schema import fact_columns
from data.inventory.contract import require, utc_timestamp
from data.inventory.ledger import InventoryLedger, InventoryMovement
from data.inventory.legacy import legacy_stock_movements
from data.inventory.projection import project_inventory
from data.inventory.projection_contract import ProjectionConfig
from data.inventory.snapshots import daily_snapshots
from data.inventory.source_bridge import COMMERCE_TABLES
from data.inventory.source_cohort_batch_v2 import (
    CachedLedgerSourceCommerceSimulator,
    _copy_commerce_inputs,
)
from data.inventory.source_cohort_batch_v2 import (
    verify_upstream_pins as verify_cached_pins,
)
from data.inventory.source_commerce import SourceCommerceSimulator
from data.inventory.source_dataset_contract import PRIVATE_TABLES
from data.inventory.source_foundation import source_foundation
from data.inventory.source_observations import known_commerce_view, rebuild_observations
from data.inventory.source_reconciliation import reconcile_source_commerce
from data.inventory.source_tables import tables_from_source

if TYPE_CHECKING:
    from data.generator.configuration import DatasetGenerationConfig, ResolvedGenerationConfig
    from data.inventory.source_contract import SourceInventoryConfig
    from data.inventory.source_tables import TableContext

VERSION = "planned-source-cached-execution-1.1.4"
UPSTREAM_SHA256 = {
    "inventory/source_cohort_batch_v2.py": "b3e73b461b8d2753f286ce84574909061d5e978c4fbe84f3bc646bf360f6425c",
    "inventory/source_bridge.py": "f1030980fa2cfd297ee1ec5e62434cd1fa56480cf59f7a605783b1ff7e25f61d",
    "inventory/run_source_dataset.py": "3c3194a6d197ced1e6c19e93268ef5bac97ae8c01073b05f17e67d9d0027d6bf",
    "anomalies/physical_process.py": "e8290df0c179b2796c339c0ee3268369b0fd67687c52f8355e23202cd38de93c",
    "anomalies/source_process.py": "6d84e4686c82f9a8db6a9843ab37e6b4fa68ed447175a54de201a0f4fd980b2c",
    "anomalies/scenarios.py": "6f035821ce37479fba31e6da107791aa30940487d35cda1c381706867e06080c",
    "anomalies/physical_scenarios.py": "de57f8f66d9533456b743834f81598033087615417977db41d9ee05f56dc5650",
    "anomalies/source_scope.py": "ef7bcd833ef010653da4136adf18c387669227bd24d451aacd2027cf5356ad1d",
    "anomalies/candidate_io.py": "80bd7af07e107d46b114fdeac3e1e54dca2cf3353648e88fffbfd7805e2ad7e1",
}


def verify_upstream_pins() -> dict[str, str]:
    verify_cached_pins()
    directory = Path(__file__).resolve().parents[1]
    actual = {
        name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
        for name in UPSTREAM_SHA256
    }
    require(
        actual == UPSTREAM_SHA256, "Planned cached source upstream changed; review parity first."
    )
    return actual


def implementation() -> dict[str, Any]:
    return {
        "version": VERSION,
        "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "upstream_sha256": verify_upstream_pins(),
        "rng_physical_rules_and_scenario_interventions": "unchanged",
        "source_validation": "ordinary_source_2_8_writer_reader_and_independent_plan_replay",
    }


class CachedPlannedSimulator(CachedLedgerSourceCommerceSimulator):
    """Reuse the frozen caches with return factors and defer event-list release."""

    def __init__(
        self,
        inputs: dict,
        tables: dict,
        generation: ResolvedGenerationConfig,
        config: SourceInventoryConfig,
        *,
        return_factors: dict[tuple[str, ...], str] | None = None,
    ) -> None:
        verify_upstream_pins()
        # The closed indexed/cached constructors do not accept return factors.
        # Initialize the same original commerce process, then their exact caches.
        SourceCommerceSimulator.__init__(
            self, inputs, tables, generation, config, return_factors=return_factors
        )
        self._movement_ids = {movement.inventory_event_id for movement in self.movements}
        self._master_ledger = InventoryLedger.from_payload(self.inventory_base)
        self._master_bytes = self._master_document()
        self._master_units = dict(self.units)
        self._master_scope = set(self.scope)
        self._validated_objects: dict[int, InventoryMovement] = {id(m): m for m in self.movements}

    def execute(self) -> dict:
        # The bridge first captures the complete, validated physical scenario.
        self._release_queued_scenario_events()
        return super().execute()


class CachedPhysicalSimulator(PhysicalAnomalySimulator, CachedPlannedSimulator):
    """Keep the original physical constructor and demand intervention methods."""


def simulate_planned_source(
    candidate: dict,
    generation: ResolvedGenerationConfig,
    config: SourceInventoryConfig,
    *,
    anomaly_plan: AnomalyPlan | None,
    physical_plan: PhysicalAnomalyPlan | None,
) -> dict[str, Any]:
    """Mirror the pinned bridge, changing only the simulator construction."""
    verify_upstream_pins()
    require((anomaly_plan is None) != (physical_plan is None), "Exactly one Source plan required.")
    validate_demand(candidate, generation, anomaly_plan=anomaly_plan)
    inputs = source_foundation(candidate, generation, config)
    tables = _copy_commerce_inputs(candidate)
    if physical_plan is None:
        simulator = CachedPlannedSimulator(inputs, tables, generation, config)
    else:
        simulator = CachedPhysicalSimulator(inputs, tables, generation, config, physical_plan)
        # Includes all demand rows with the original physical sequence transform.
        inputs["scenario"] = simulator.scenario.model_dump()
    result = simulator.execute()
    start, end = simulator.start, simulator.end
    if isinstance(simulator, CachedPhysicalSimulator):
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
    del simulator, result
    ledger = InventoryLedger.from_payload(output["inventory"]["ledger"])
    projection = ProjectionConfig.from_payload(
        {
            "contract_version": "inventory-projection-config-1.0.0",
            "process_version": "inventory-projection-1.0.0",
            "business_timezone": "UTC",
            "start_at": start.isoformat(),
            "end_at": end.isoformat(),
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
    del ledger
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
            utc_timestamp(r["available_at"]) <= end for r in tables["daily_demand_observations"]
        )
    )
    output["status"] = "passed" if ready else "not_ready"
    return output


@stage("planned_source_build")
def build_tables(
    generation: DatasetGenerationConfig,
    payload: dict,
    config: SourceInventoryConfig,
    *,
    evaluated_at: str | None = None,
) -> tuple[dict, TableContext]:
    """Build every ordinary Source 2.8 table, without writing or opening truth."""
    require_source_scenario_scope(generation)
    verify_upstream_pins()
    plan = parse_candidate_plan(payload)
    effective = resolve_generation_config(generation)
    require(effective.profile.startswith("ai-"), "Planned source requires an AI profile.")
    demand = plan if isinstance(plan, AnomalyPlan) else None
    physical = plan if isinstance(plan, PhysicalAnomalyPlan) else None
    candidate = {
        name: rows
        for name, rows in build_dataset(generation, anomaly_plan=demand).items()
        if name in set(COMMERCE_TABLES) | set(PRIVATE_TABLES)
    }
    source = simulate_planned_source(
        candidate, effective, config, anomaly_plan=demand, physical_plan=physical
    )
    # Full independent reconciliation has consumed the original request rows.
    private_tables = {name: candidate[name] for name in PRIVATE_TABLES}
    del candidate
    settings = source["effective_configuration"]["scenario"]["settings"]
    projection_config = ProjectionConfig.from_payload(
        {
            "contract_version": "inventory-projection-config-1.0.0",
            "process_version": "inventory-projection-1.0.0",
            "business_timezone": "UTC",
            "start_at": settings["start_at"],
            "end_at": settings["end_at"],
            "snapshot_policy": "utc_day_last_microsecond",
            "reservation_policy": "none",
            "stock_measure": "available_qty",
            "episode_policy": "zero_after_event_including_instantaneous",
            "diagnostic_horizon_days": 7,
            "truth_delay_seconds": 0,
        }
    )
    projection = project_inventory(
        source["inventory"],
        source["simulation_truth"],
        projection_config,
        evaluated_at=evaluated_at or projection_config.end_at,
    )
    native, context = tables_from_source(source, projection)
    del source["effective_configuration"]
    commerce = source["commerce"]
    view = known_commerce_view(commerce, native["inventory_sales"])
    commerce["daily_price_observations"] = daily_price_observations(
        view["sales"], view["sale_price_references"]
    )
    return {**commerce, **private_tables, **native}, context
