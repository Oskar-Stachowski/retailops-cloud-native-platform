"""Source 2.7 with cached validation of immutable movement objects.

The source process and RNG are unchanged. Every ledger view still checks its
complete identity/order/opening/transfer/balance invariants. Schemas for immutable
masters and movements are checked once; ordinary publication fully revalidates
all serialized source records and all source quality gates.
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
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

from data.generator.configuration import (
    SUPPORTED_PROFILES,
    DatasetGenerationConfig,
    ResolvedGenerationConfig,
    resolve_generation_config,
)
from data.generator.csv_writer import TABLE_COLUMNS
from data.generator.demand_quality import validate_demand
from data.generator.identity import canonical_json
from data.generator.main import build_dataset
from data.generator.pricing_plans import daily_price_observations
from data.generator.simulation_schema import fact_columns
from data.inventory.contract import MovementRecord, require, utc_timestamp
from data.inventory.ledger import (
    InventoryLedger,
    InventoryMovement,
    transfer_pairs,
    validate_movement,
)
from data.inventory.legacy import legacy_stock_movements
from data.inventory.projection import project_inventory
from data.inventory.projection_contract import ProjectionConfig
from data.inventory.run_source_dataset import default_inventory_config
from data.inventory.snapshots import daily_snapshots
from data.inventory.source_bridge import COMMERCE_TABLES
from data.inventory.source_cohort_batch import IndexedSourceCommerceSimulator
from data.inventory.source_contract import SourceInventoryConfig
from data.inventory.source_dataset_contract import PRIVATE_TABLES
from data.inventory.source_dataset_io import load_json, read_source_dataset, write_source_dataset
from data.inventory.source_foundation import source_foundation
from data.inventory.source_observations import known_commerce_view, rebuild_observations
from data.inventory.source_reconciliation import reconcile_source_commerce
from data.inventory.source_tables import TableContext, tables_from_source

FAST_PATH_VERSION = "inventory-source-cached-ledger-2.0.0"
UPSTREAM_SHA256 = {
    "source_cohort_batch.py": "01ef8c37047437c2056d681b312a0fdc4e55587adcad65f214ef441bf11b57f2",
    "ledger.py": "3e50ac30d3732789680461d96d5855f01619d0978de56e774d11565df884565f",
    "source_bridge.py": "b3cd35d1269a09b7b44c5eaab6ff22c17c00dcc085e7c60bed90d7f2c4ba74ff",
    "run_source_dataset.py": "b169472c350b88c267cd2fd32132d41d70eef3fb81e7097dc518af4d5d9e4261",
    "simulator.py": "f387f5a374f3cc452d16fcf1f8b64919e29087275da33b95f81e594ea03c2fa1",
    "source_commerce.py": "9322d5240b1762db498929febed872bd207bd683ec3b1785cc0a0674f43e09c7",
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
        "optimization": "movement_id_set_and_cached_immutable_record_schema_validation",
        "rng_and_chronological_process": "unchanged",
        "source_validation": "ordinary_source_2_7_writer_and_reader_all_gates",
    }


class CachedLedgerSourceCommerceSimulator(IndexedSourceCommerceSimulator):
    """Reuse validated records while rechecking every ledger-wide invariant."""

    def __init__(
        self,
        inputs: dict,
        tables: dict,
        generation: ResolvedGenerationConfig,
        config: SourceInventoryConfig,
    ) -> None:
        verify_upstream_pins()
        super().__init__(inputs, tables, generation, config)
        self._master_ledger = InventoryLedger.from_payload(self.inventory_base)
        self._master_bytes = self._master_document()
        self._master_units = dict(self.units)
        self._master_scope = set(self.scope)
        self._validated_objects: dict[int, tuple[InventoryMovement, InventoryMovement]] = {
            id(m): (m, m) for m in self.movements
        }

    def _master_document(self) -> bytes:
        return canonical_json({k: v for k, v in self.inventory_base.items() if k != "movements"})

    def _checked(self, movement: InventoryMovement) -> InventoryMovement:
        cached = self._validated_objects.get(id(movement))
        if cached is not None and cached[0] is movement:
            return cached[1]
        # An untracked replacement must pass the same strict single-row schema,
        # normalization and semantic checks that ordinary from_payload performs.
        record = movement.record()
        MovementRecord.model_validate(record)
        normalized = InventoryMovement.from_record(record)
        validate_movement(normalized, self.units, self.scope)
        self._validated_objects[id(movement)] = (movement, normalized)
        return normalized

    def _apply(self, record: dict) -> InventoryMovement:
        MovementRecord.model_validate(record)
        movement = super()._apply(record)
        self._validated_objects[id(movement)] = (movement, movement)
        return movement

    def _ledger(self) -> InventoryLedger:
        require(
            self._master_document() == self._master_bytes
            and self.units == self._master_units
            and self.scope == self._master_scope,
            "Cached ledger master context changed.",
        )
        present = {m.inventory_event_id for m in self.movements}
        pending = []
        for outbound in self.movements:
            if outbound.movement_type == "transfer_out":
                inbound = self.transfer_inbounds[outbound.transfer_id]
                if inbound.inventory_event_id not in present:
                    record = inbound.record()
                    record["available_at"] = max(
                        utc_timestamp(inbound.available_at),
                        utc_timestamp(outbound.available_at),
                        self.availability[inbound.position],
                    ).isoformat()
                    movement = InventoryMovement.from_record(record)
                    MovementRecord.model_validate(movement.record())
                    validate_movement(movement, self.units, self.scope)
                    pending.append(movement)
        movements = tuple(self._checked(m) for m in self.movements) + tuple(pending)
        require(
            len({m.inventory_event_id for m in movements}) == len(movements),
            "Duplicate inventory event ID.",
        )
        require(
            len({m.ordering_key for m in movements}) == len(movements),
            "Duplicate timestamp/sequence.",
        )
        openings = [m for m in movements if m.movement_type == "opening_stock"]
        require(
            len(openings) == len(self.scope) and {m.position for m in openings} == self.scope,
            "Require exactly one opening movement per inventory position.",
        )
        opening_at = utc_timestamp(self.inventory_base["opening_at"])
        require(
            all(m.occurred_time == opening_at for m in openings),
            "Opening timestamp differs from declared opening_at.",
        )
        ordered = tuple(sorted(movements, key=lambda m: m.ordering_key))
        result = InventoryLedger(
            ordered,
            self._master_ledger.scope,
            self._master_ledger.stock_location_codes,
            transfer_pairs(ordered),
        )
        result._balances(ordered)  # noqa: SLF001 - retain the ordinary full-ledger validation
        return result


def simulate_source_commerce_fast(
    candidate: dict, generation: ResolvedGenerationConfig, config: SourceInventoryConfig
) -> dict[str, Any]:
    """Pinned source_bridge orchestration with the indexed simulator constructor."""
    verify_upstream_pins()
    validate_demand(candidate, generation)
    inputs = source_foundation(candidate, generation, config)
    tables = deepcopy(candidate)
    simulator = CachedLedgerSourceCommerceSimulator(inputs, tables, generation, config)
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
    on_stage: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    require(not output_root.exists(), "Use a new cohort output root; preserve previous sources.")
    started = perf_counter()
    code = implementation()
    config = (
        SourceInventoryConfig.from_payload(load_json(inventory_config_path))
        if inventory_config_path
        else default_inventory_config(generation)
    )

    def record_stage(name: str) -> None:
        if on_stage is not None:
            on_stage({"stage": name, "elapsed_seconds": perf_counter() - started})

    record_stage("source_build_started")
    tables, context = build_source_dataset_fast(generation, config, evaluated_at=evaluated_at)
    built_seconds = perf_counter() - started
    record_stage("source_built")
    directory = write_source_dataset(tables, context, generation, config, output_root)
    del tables, context
    written_seconds = perf_counter() - started
    record_stage("source_written_and_staging_verified")
    restored, manifest = read_source_dataset(directory)
    verified_seconds = perf_counter() - started
    record_stage("published_source_verified")
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
        "stage_seconds": {
            "source_build": built_seconds,
            "source_write_and_staging_verify": written_seconds - built_seconds,
            "published_source_verify": verified_seconds - written_seconds,
        },
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
        generation,
        args.output_root,
        args.inventory_config,
        evaluated_at=args.evaluated_at,
        on_stage=lambda event: print(json.dumps(event), flush=True),  # noqa: T201
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
