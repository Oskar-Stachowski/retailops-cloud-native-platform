"""Generate or verify explicit source 2.8; preserve qualified canonical facts under raw faults."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from data.anomalies.example import example_plan
from data.anomalies.physical_scenarios import physical_example_plan
from data.anomalies.source_process import build_tables
from data.generator.configuration import DatasetGenerationConfig
from data.inventory.contract import require
from data.inventory.run_source_dataset import default_inventory_config
from data.inventory.source_dataset_io import (
    load_json,
    read_source_dataset,
    safe_file,
    write_source_dataset,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("ai-smoke", "ai-temporal-smoke"), default="ai-smoke")
    for field in ("days", "products", "stores", "warehouses"):
        parser.add_argument("--" + field, type=int)
    parser.add_argument("--seed", type=int, default=42)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--example", action="store_true")
    mode.add_argument("--physical-example", action="store_true")
    mode.add_argument("--plan", type=Path)
    mode.add_argument("--verify", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    protected = args.verify or args.output_root
    if protected and args.output.resolve().is_relative_to(protected.resolve()):
        parser.error("Verification receipt must be outside source storage")
    if args.plan and args.output.resolve() == args.plan.resolve():
        parser.error("Receipt must not overwrite the private input plan")
    try:
        if args.verify:
            directory = args.verify
        else:
            require(args.output_root is not None, "Generation requires --output-root.")
            generation = DatasetGenerationConfig(
                **{
                    field: getattr(args, field)
                    for field in ("profile", "days", "products", "stores", "warehouses", "seed")
                }
            )
            config = default_inventory_config(generation)
            plan = (
                load_json(safe_file(args.plan.parent, args.plan.name, limit=1024 * 1024))
                if args.plan
                else (physical_example_plan if args.physical_example else example_plan)(generation)
            )
            tables, context = build_tables(generation, plan, config)
            directory = write_source_dataset(
                tables, context, generation, config, args.output_root, scenario_plan=plan
            )
        tables, manifest = read_source_dataset(directory)
        require(
            manifest["schema_version"] == "2.8.0" and manifest["facts_ready"],
            "Source 2.8 facts are not qualified.",
        )
        result = {
            "status": "passed",
            "directory": str(directory),
            "dataset_id": manifest["dataset_id"],
            "source_schema_version": "2.8.0",
            "facts_ready": True,
            "table_count": len(tables),
            "source_ready": False,
            "anomaly_ready": False,
            "model_ready": False,
        }
    except (ValueError, KeyError, TypeError, OSError, ArithmeticError) as error:
        result = {
            "status": "failed",
            "error": str(error),
            "source_ready": False,
            "anomaly_ready": False,
            "model_ready": False,
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "report": str(args.output)}))  # noqa: T201 - CLI receipt
    if result["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
