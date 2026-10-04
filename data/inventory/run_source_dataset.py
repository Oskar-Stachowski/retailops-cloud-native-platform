"""Generate immutable source 2.7; the existing AI03 publication path stays frozen."""

from __future__ import annotations

import argparse
import json
import resource
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from time import perf_counter
from typing import TYPE_CHECKING

from data.generator.configuration import (
    SUPPORTED_PROFILES,
    DatasetGenerationConfig,
    resolve_generation_config,
)
from data.generator.main import build_dataset
from data.generator.pricing_plans import daily_price_observations
from data.inventory.contract import require
from data.inventory.projection import project_inventory
from data.inventory.projection_contract import ProjectionConfig
from data.inventory.source_bridge import simulate_source_commerce
from data.inventory.source_contract import SourceInventoryConfig
from data.inventory.source_dataset_contract import PRIVATE_TABLES
from data.inventory.source_dataset_io import load_json, read_source_dataset, write_source_dataset
from data.inventory.source_observations import known_commerce_view
from data.inventory.source_tables import TableContext, tables_from_source

if TYPE_CHECKING:
    from data.anomalies.contract import AnomalyPlan
    from data.anomalies.physical_contract import PhysicalAnomalyPlan


def default_inventory_config(generation: DatasetGenerationConfig) -> SourceInventoryConfig:
    effective = resolve_generation_config(generation)
    supply_adequate = effective.profile == "ai-07-portfolio-v2"
    return SourceInventoryConfig.from_payload(
        {
            "contract_version": "source-inventory-config-1.0.0",
            "process_version": "source-inventory-commerce-1.0.0",
            "business_timezone": "UTC",
            "reservation_policy": "none",
            "return_quality_policy": "refunded_undamaged_returns_only",
            "return_tail_policy": "financial_tail_without_inventory_extension",
            "stock": {
                "opening_quantity": 256 if supply_adequate else 12,
                "reorder_point": 128 if supply_adequate else 8,
                "safety_stock": 64 if supply_adequate else 4,
                "history_window_days": min(2, effective.days),
                "review_cadence_days": 1,
                "minimum_order_quantity": 64 if supply_adequate else 4,
                "quoted_lead_time_days": 2,
            },
            "sale_ingestion_delay_seconds": 30,
            "sale_availability_delay_seconds": 30,
            "return_inventory_ingestion_delay_seconds": 30,
            "return_inventory_availability_delay_seconds": 30,
            "supplier_parameters": {
                "data_class": "simulation_truth",
                "reliability": "1",
                "lead_time_mean_days": "2",
                "lead_time_std_days": "0",
            },
            "fulfillment": {
                "contract_version": "supplier-fulfillment-config-1.0.0",
                "data_class": "simulation_truth",
                "process_version": "supplier-fulfillment-two-point-1.0.0",
                "seed": effective.seed,
                "lead_time_distribution": "two_point_mean_plus_minus_std",
                "minimum_lead_days": 1,
                "maximum_lead_days": 30,
                "disruption_delay_days": 3,
                "partial_fraction": "0.5",
                "partial_receipt_gap_days": 2,
                "ingestion_delay_seconds": 60,
                "availability_delay_seconds": 60,
            },
        }
    )


def build_source_dataset(
    generation: DatasetGenerationConfig,
    config: SourceInventoryConfig,
    *,
    evaluated_at: str | None = None,
    anomaly_plan: AnomalyPlan | None = None,
    physical_plan: PhysicalAnomalyPlan | None = None,
) -> tuple[dict, TableContext]:
    effective = resolve_generation_config(generation)
    require(
        effective.profile.startswith("ai-"),
        "Inventory source 2.7 requires an AI profile; demo remains unchanged.",
    )
    candidate = build_dataset(generation, anomaly_plan=anomaly_plan)
    source = simulate_source_commerce(
        candidate, effective, config, anomaly_plan=anomaly_plan, physical_plan=physical_plan
    )
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
) -> dict:
    started = perf_counter()
    config = (
        SourceInventoryConfig.from_payload(load_json(inventory_config_path))
        if inventory_config_path
        else default_inventory_config(generation)
    )
    tables, context = build_source_dataset(generation, config, evaluated_at=evaluated_at)
    directory = write_source_dataset(tables, context, generation, config, output_root)
    restored, manifest = read_source_dataset(directory)
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return {
        "verified_at": datetime.now(UTC).isoformat(),
        "scope": "AI 06.6b.2a versioned inventory source",
        "status": "passed" if manifest["facts_ready"] else "not_ready",
        "dataset_id": manifest["dataset_id"],
        "directory": str(directory),
        "facts_ready": manifest["facts_ready"],
        "source_ready": False,
        "inventory_ready": False,
        "model_ready": False,
        "label_qualification": "not_evaluated",
        "table_count": len(restored),
        "operational_table_count": sum(
            a["data_class"] != "simulation_truth" for a in manifest["descriptor"]["tables"].values()
        ),
        "truth_table_count": sum(
            a["data_class"] == "simulation_truth" for a in manifest["descriptor"]["tables"].values()
        ),
        "tables": manifest["descriptor"]["tables"],
        "seconds": perf_counter() - started,
        "peak_rss_mib": peak / (1024 * 1024) if sys.platform == "darwin" else peak / 1024,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate and verify immutable inventory source 2.7; AI03 handoff is pending."
    )
    parser.add_argument(
        "--profile",
        choices=tuple(profile for profile in SUPPORTED_PROFILES if profile.startswith("ai-")),
        default="ai-smoke",
    )
    for name in ("days", "products", "stores", "warehouses", "max-daily-rows"):
        parser.add_argument("--" + name, type=int)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--start-date", type=date.fromisoformat)
    parser.add_argument("--end-date", type=date.fromisoformat)
    parser.add_argument("--inventory-config", type=Path)
    parser.add_argument("--evaluated-at")
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        generation = DatasetGenerationConfig(
            **{
                k: getattr(args, k)
                for k in (
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
    except (ValueError, KeyError, TypeError, OSError, ArithmeticError) as error:
        result = {
            "status": "failed",
            "facts_ready": False,
            "source_ready": False,
            "inventory_ready": False,
            "model_ready": False,
            "error": str(error),
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"status": result["status"], "report": str(args.output)}))  # noqa: T201 - CLI receipt
    if result["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
