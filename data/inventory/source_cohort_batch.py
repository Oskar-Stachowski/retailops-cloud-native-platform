"""Additive source 2.7 execution with indexed event identity checks.

The generator, random streams, chronological inventory rules and validators are
unchanged. Only the generated-movement duplicate lookup uses a set. Upstream
orchestration is copied explicitly and pinned so drift cannot silently alter this
path. Published artifacts still use the ordinary immutable source writer/reader.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import sys
from copy import deepcopy
from datetime import UTC, date, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from data.generator.configuration import (
    SUPPORTED_PROFILES,
    DatasetGenerationConfig,
    ResolvedGenerationConfig,
    resolve_generation_config,
)
from data.generator.csv_writer import TABLE_COLUMNS
from data.generator.demand_quality import validate_demand
from data.generator.main import build_dataset
from data.generator.pricing_plans import daily_price_observations
from data.generator.simulation_schema import fact_columns
from data.inventory.contract import require, utc_timestamp
from data.inventory.ledger import InventoryLedger, InventoryMovement, validate_movement
from data.inventory.legacy import legacy_stock_movements
from data.inventory.projection import project_inventory
from data.inventory.projection_contract import ProjectionConfig
from data.inventory.run_source_dataset import default_inventory_config
from data.inventory.snapshots import daily_snapshots
from data.inventory.source_bridge import COMMERCE_TABLES
from data.inventory.source_commerce import SourceCommerceSimulator
from data.inventory.source_contract import SourceInventoryConfig
from data.inventory.source_dataset_contract import PRIVATE_TABLES
from data.inventory.source_dataset_io import load_json, read_source_dataset, write_source_dataset
from data.inventory.source_foundation import source_foundation
from data.inventory.source_observations import known_commerce_view, rebuild_observations
from data.inventory.source_reconciliation import reconcile_source_commerce
from data.inventory.source_tables import TableContext, tables_from_source

FAST_PATH_VERSION = "inventory-source-indexed-movement-1.0.0"
UPSTREAM_SHA256 = {
    "source_bridge.py": "f1030980fa2cfd297ee1ec5e62434cd1fa56480cf59f7a605783b1ff7e25f61d",
    "run_source_dataset.py": "3c3194a6d197ced1e6c19e93268ef5bac97ae8c01073b05f17e67d9d0027d6bf",
    "simulator.py": "ea9739ebf73c62ea48a076ccf3940c2dbb4f79fdf22049bef97f8e3f2aef3696",
    "source_commerce.py": "c53fefae30abfdf5c48d744cc0c903db449edbc970be3523e8a008dbd0ad7991",
}


def verify_upstream_pins() -> dict[str, str]:
    directory = Path(__file__).resolve().parent
    actual = {
        name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
        for name in UPSTREAM_SHA256
    }
    require(actual == UPSTREAM_SHA256, "Indexed source upstream code changed; review parity first.")
    return actual


def implementation() -> dict[str, Any]:
    return {
        "version": FAST_PATH_VERSION,
        "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "upstream_sha256": verify_upstream_pins(),
        "optimization": "movement_id_set_membership_only",
        "rng_and_chronological_process": "unchanged",
        "source_validation": "ordinary_source_2_7_writer_and_reader_all_gates",
    }


class IndexedSourceCommerceSimulator(SourceCommerceSimulator):
    """Preserve movement order and every physical check, with O(1) ID lookup."""

    def __init__(
        self,
        inputs: dict,
        tables: dict,
        generation: ResolvedGenerationConfig,
        config: SourceInventoryConfig,
    ) -> None:
        verify_upstream_pins()
        super().__init__(inputs, tables, generation, config)
        self._movement_ids = {movement.inventory_event_id for movement in self.movements}

    def _apply(self, record: dict) -> InventoryMovement:
        movement = InventoryMovement.from_record(record)
        validate_movement(movement, self.units, self.scope)
        require(
            movement.inventory_event_id not in self._movement_ids,
            "Duplicate generated inventory event ID.",
        )
        available = max(utc_timestamp(movement.available_at), self.availability[movement.position])
        if movement.movement_type == "transfer_in":
            outbound = next(
                m
                for m in self.movements
                if m.transfer_id == movement.transfer_id and m.movement_type == "transfer_out"
            )
            available = max(available, utc_timestamp(outbound.available_at))
        movement = InventoryMovement.from_record(
            {**movement.record(), "available_at": available.isoformat()}
        )
        quantity = self.balances[movement.position] + movement.quantity_delta
        require(quantity >= 0, "Physical event would produce a negative inventory balance.")
        self.balances[movement.position] = quantity
        self.availability[movement.position] = available
        self.movements.append(movement)
        self._movement_ids.add(movement.inventory_event_id)
        return movement


def simulate_source_commerce_fast(
    candidate: dict, generation: ResolvedGenerationConfig, config: SourceInventoryConfig
) -> dict[str, Any]:
    """Pinned source_bridge orchestration with the indexed simulator constructor."""
    verify_upstream_pins()
    validate_demand(candidate, generation)
    inputs = source_foundation(candidate, generation, config)
    tables = deepcopy(candidate)
    simulator = IndexedSourceCommerceSimulator(inputs, tables, generation, config)
    result = simulator.execute()
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


def build_source_dataset_fast(
    generation: DatasetGenerationConfig,
    config: SourceInventoryConfig,
    *,
    evaluated_at: str | None = None,
) -> tuple[dict, TableContext]:
    """Pinned run_source_dataset construction; no source generation on import."""
    verify_upstream_pins()
    effective = resolve_generation_config(generation)
    require(
        effective.profile.startswith("ai-"),
        "Inventory source 2.7 requires an AI profile; demo remains unchanged.",
    )
    candidate = build_dataset(generation)
    source = simulate_source_commerce_fast(candidate, effective, config)
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
    commerce = source["commerce"]
    view = known_commerce_view(commerce, native["inventory_sales"])
    commerce["daily_price_observations"] = daily_price_observations(
        view["sales"], view["sale_price_references"]
    )
    return {**commerce, **{n: candidate[n] for n in PRIVATE_TABLES}, **native}, context


def run(
    generation: DatasetGenerationConfig,
    output_root: Path,
    inventory_config_path: Path | None = None,
    *,
    evaluated_at: str | None = None,
) -> dict[str, Any]:
    require(not output_root.exists(), "Use a new cohort output root; preserve previous sources.")
    started = perf_counter()
    code = implementation()
    config = (
        SourceInventoryConfig.from_payload(load_json(inventory_config_path))
        if inventory_config_path
        else default_inventory_config(generation)
    )
    tables, context = build_source_dataset_fast(generation, config, evaluated_at=evaluated_at)
    built_seconds = perf_counter() - started
    directory = write_source_dataset(tables, context, generation, config, output_root)
    restored, manifest = read_source_dataset(directory)
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return {
        "verified_at": datetime.now(UTC).isoformat(),
        "scope": "new independent source cohort; no forecast quality evaluation",
        "status": "passed" if manifest["facts_ready"] else "not_ready",
        "implementation": code,
        "dataset_id": manifest["dataset_id"],
        "directory": str(directory),
        "facts_ready": manifest["facts_ready"],
        "source_ready": False,
        "inventory_ready": False,
        "model_ready": False,
        "label_qualification": "not_evaluated",
        "table_count": len(restored),
        "tables": manifest["descriptor"]["tables"],
        "source_build_seconds": built_seconds,
        "seconds": perf_counter() - started,
        "peak_rss_mib": peak / (1024 * 1024) if sys.platform == "darwin" else peak / 1024,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile",
        choices=tuple(p for p in SUPPORTED_PROFILES if p.startswith("ai-")),
        required=True,
    )
    for name in ("days", "products", "stores", "warehouses", "max-daily-rows"):
        parser.add_argument("--" + name, type=int)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--start-date", type=date.fromisoformat)
    parser.add_argument("--end-date", type=date.fromisoformat)
    parser.add_argument("--inventory-config", type=Path)
    parser.add_argument("--evaluated-at")
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), "Use a new report path; preserve previous reports.")
    generation = DatasetGenerationConfig(
        **{
            name: getattr(args, name)
            for name in (
                "profile",
                "days",
                "products",
                "stores",
                "warehouses",
                "max_daily_rows",
                "seed",
                "start_date",
                "end_date",
            )
        }
    )
    result = run(
        generation, args.output_root, args.inventory_config, evaluated_at=args.evaluated_at
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": result["status"], "report": str(args.output)}))  # noqa: T201
    if result["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
