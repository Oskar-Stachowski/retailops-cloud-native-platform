"""Generate a local, independently replayed business anomaly candidate."""

from __future__ import annotations

import argparse
import json
import resource
import sys
from datetime import date
from pathlib import Path
from time import perf_counter

from data.anomalies.candidate_io import read_candidate, write_candidate
from data.anomalies.example import example_plan
from data.anomalies.scenarios import build_scenario
from data.generator.configuration import DatasetGenerationConfig
from data.inventory.source_contract import SourceInventoryConfig
from data.inventory.source_dataset_io import load_json


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AI 07.1a demand scenario candidate; not an AI03 handoff."
    )
    parser.add_argument("--profile", choices=("ai-smoke", "ai-temporal-smoke"), default="ai-smoke")
    for name in ("days", "products", "stores", "warehouses", "max-daily-rows"):
        parser.add_argument("--" + name, type=int)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--start-date", type=date.fromisoformat)
    parser.add_argument("--end-date", type=date.fromisoformat)
    plan = parser.add_mutually_exclusive_group(required=True)
    plan.add_argument("--plan", type=Path)
    plan.add_argument("--example", action="store_true")
    parser.add_argument("--inventory-config", type=Path)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    started = perf_counter()
    try:
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
        payload = example_plan(generation) if args.example else load_json(args.plan)
        inventory_config = (
            SourceInventoryConfig.from_payload(load_json(args.inventory_config))
            if args.inventory_config
            else None
        )
        candidate = build_scenario(generation, payload, inventory_config)
        directory = write_candidate(candidate, args.output_root)
        manifest = read_candidate(directory, replay=False)
        result = {
            "status": "passed",
            "scope": candidate["scope"],
            "candidate_id": manifest["candidate_id"],
            "directory": str(directory),
            "episode_count": len(candidate["effects"]["episodes"]),
            "control_count": len(candidate["effects"]["controls"]),
            "facts_status": candidate["facts_status"],
            "source_ready": False,
            "anomaly_ready": False,
            "model_ready": False,
            "publication_status": candidate["publication_status"],
        }
    except (ValueError, KeyError, TypeError, OSError, ArithmeticError) as error:
        result = {
            "status": "failed",
            "source_ready": False,
            "anomaly_ready": False,
            "model_ready": False,
            "error": str(error),
        }
    result["seconds"] = perf_counter() - started
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    result["peak_rss_mib"] = peak / (1024 * 1024) if sys.platform == "darwin" else peak / 1024
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(result))  # noqa: T201 - CLI receipt
    if result["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
