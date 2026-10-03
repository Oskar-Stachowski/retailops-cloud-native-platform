"""Generate or verify the explicitly versioned full parent-fact offline fixture."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from data.dq.full_contract import FullFaultPlan
from data.dq.full_package import read_fixture, write_fixture
from data.dq.full_scenarios import example_plan
from data.dq.full_source import full_events
from data.dq.package import receipt
from data.dq.source import load_source
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
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    protected = [args.source_dir, *(p for p in (args.verify, args.output_root) if p)]
    if any(args.output.resolve().is_relative_to(p.resolve()) for p in protected):
        parser.error("Receipt must be outside source and fixture storage")
    if args.plan and args.output.resolve() == args.plan.resolve():
        parser.error("Receipt must not overwrite the private input plan")
    try:
        if args.verify:
            directory = args.verify
        else:
            require(args.output_root is not None, "Full DQ generation requires --output-root.")
            if args.plan:
                plan = FullFaultPlan.from_payload(
                    load_json(safe_file(args.plan.parent, args.plan.name, limit=1024 * 1024))
                )
            else:
                tables, source = load_source(args.source_dir)
                plan = example_plan(
                    full_events(tables, source), source["dataset_id"], seed=args.seed
                )
            directory = write_fixture(args.source_dir, plan, args.output_root)
        result = receipt(directory, read_fixture(directory, args.source_dir))
    except (ValueError, KeyError, TypeError, OSError, ArithmeticError) as error:
        result = {
            "status": "failed",
            "error": str(error),
            "ai03_handoff_ready": False,
            "model_ready": False,
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "report": str(args.output)}))  # noqa: T201 - CLI receipt
    if result["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
