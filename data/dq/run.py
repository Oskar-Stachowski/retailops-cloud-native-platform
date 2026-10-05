"""Generate or independently verify bounded raw DQ fixtures (never a live broker)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from data.dq.contract import FaultPlan
from data.dq.package import read_fixture, receipt, write_fixture
from data.dq.scenarios import example_plan
from data.dq.source import load_source, sales_events
from data.inventory.contract import require
from data.inventory.source_dataset_io import load_json, safe_file


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--example", action="store_true")
    mode.add_argument("--plan", type=Path)
    mode.add_argument("--verify", type=Path)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--event-limit", type=int, default=256)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    protected = [args.source_dir, *([args.verify] if args.verify else [])]
    if any(args.output.resolve().is_relative_to(p.resolve()) for p in protected):
        parser.error("--output must be outside the source and fixture directories")
    try:
        if args.verify:
            directory = args.verify
        else:
            require(args.output_root is not None, "Generation requires --output-root.")
            if args.plan:
                plan = FaultPlan.from_payload(
                    load_json(safe_file(args.plan.parent, args.plan.name, limit=1024 * 1024))
                )
            else:
                tables, source = load_source(args.source_dir)
                plan = example_plan(
                    sales_events(tables, source, args.event_limit),
                    source["dataset_id"],
                    seed=args.seed,
                    limit=args.event_limit,
                )
            directory = write_fixture(args.source_dir, plan, args.output_root)
        manifest = read_fixture(directory, args.source_dir)
        result = receipt(directory, manifest)
    except (ValueError, KeyError, TypeError, OSError, ArithmeticError) as error:
        result = {
            "status": "failed",
            "error": str(error),
            "ai03_handoff_ready": False,
            "model_ready": False,
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": result["status"], "report": str(args.output)}))  # noqa: T201 - CLI receipt
    if result["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
