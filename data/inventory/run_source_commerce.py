from __future__ import annotations

import argparse
import json
import resource
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from time import perf_counter

from data.generator.configuration import DatasetGenerationConfig, resolve_generation_config
from data.generator.identity import code_fingerprint, code_provenance, file_sha256, json_sha256
from data.generator.main import build_dataset
from data.inventory.source_bridge import simulate_source_commerce
from data.inventory.source_contract import SOURCE_INVENTORY_VERSION, SourceInventoryConfig


def run(generation: DatasetGenerationConfig, inventory_config_path: Path) -> dict:
    started = perf_counter()
    effective = resolve_generation_config(generation)
    inventory = SourceInventoryConfig.from_payload(json.loads(inventory_config_path.read_text()))
    candidate = build_dataset(generation)
    result = simulate_source_commerce(candidate, effective, inventory)
    files = tuple(
        str(p.relative_to(Path(__file__).resolve().parents[2]))
        for p in sorted(Path(__file__).resolve().parent.glob("*.py"))
    )
    contracts = (
        "inventory_ledger",
        "replenishment",
        "supplier_simulation_truth",
        "reorder_config",
        "inventory_history_coverage",
        "supplier_fulfillment_config",
        "chronological_scenario",
        "inventory_fulfillment_routes",
        "inventory_commerce_output",
        "inventory_projection_config",
        "inventory_projection",
        "source_inventory_config",
        "inventory_source_tables",
    )
    fingerprint = code_fingerprint(
        (*files, *(f"data/contracts/{name}.v1.schema.json" for name in contracts))
    )
    facts = {
        name: result[name]
        for name in (
            "inventory",
            "commerce",
            "return_inventory_decisions",
            "inventory_snapshots",
            "legacy_stock_movements",
        )
    }
    operational_hash = json_sha256(facts)
    truth_hash = json_sha256(result["simulation_truth"])
    candidate_hash = json_sha256(candidate)
    execution_id = "source-inventory-candidate-sha256-" + json_sha256(
        {
            "process_version": SOURCE_INVENTORY_VERSION,
            "generation": effective.parameters(),
            "inventory_configuration": inventory.model_dump(),
            "input_tables_sha256": candidate_hash,
            "code_fingerprint": fingerprint,
            "operational_sha256": operational_hash,
            "simulation_sha256": truth_hash,
        }
    )
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return {
        "verified_at": datetime.now(UTC).isoformat(),
        "scope": "AI 06.6a unpublished source-commerce integration",
        "inventory_ready": False,
        "source_ready": False,
        "model_ready": False,
        "process_version": SOURCE_INVENTORY_VERSION,
        "execution_id": execution_id,
        "generation_configuration": effective.parameters(),
        "inventory_configuration": inventory.model_dump(),
        "input_configuration_sha256": file_sha256(inventory_config_path),
        "input_tables_sha256": candidate_hash,
        "operational_sha256": operational_hash,
        "simulation_sha256": truth_hash,
        "code_provenance": code_provenance(fingerprint),
        **result,
        "seconds": perf_counter() - started,
        "peak_rss_mib": peak / (1024 * 1024) if sys.platform == "darwin" else peak / 1024,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run AI 06.6a source baskets through chronological inventory; private report only."
    )
    parser.add_argument(
        "--profile",
        choices=("ai-smoke", "ai-temporal-smoke", "ai-dev", "ai-training", "ai-load"),
        default="ai-smoke",
    )
    for name in ("days", "products", "stores", "warehouses", "max-daily-rows"):
        parser.add_argument("--" + name, type=int)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--start-date", type=date.fromisoformat)
    parser.add_argument("--end-date", type=date.fromisoformat)
    parser.add_argument("--inventory-config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        generation = DatasetGenerationConfig(
            **{
                key: getattr(args, key)
                for key in (
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
        result = run(generation, args.inventory_config)
    except (ValueError, KeyError, TypeError, OSError, OverflowError) as error:
        result = {
            "status": "failed",
            "inventory_ready": False,
            "source_ready": False,
            "scope": "AI 06.6a unpublished source-commerce integration",
            "error": str(error),
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"status": result["status"], "report": str(args.output)}))  # noqa: T201 - CLI receipt
    if result["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
