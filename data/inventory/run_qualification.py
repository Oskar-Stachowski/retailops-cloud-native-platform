"""Qualify an existing verified source 2.7 without altering its immutable files."""

from __future__ import annotations

import argparse
import json
import resource
import sys
from pathlib import Path
from time import perf_counter

from data.inventory.qualification_contract import MANIFEST, REPORT
from data.inventory.qualification_io import write_qualification
from data.inventory.source_dataset_io import load_json


def run(source: Path, output_root: Path) -> dict:
    started = perf_counter()
    directory = write_qualification(source, output_root)
    manifest, report = load_json(directory / MANIFEST), load_json(directory / REPORT)
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return {
        "status": "passed",
        "scope": "AI 06.6b.2b source lifecycle/coverage qualification",
        "qualification_id": manifest["qualification_id"],
        "parent_source_id": manifest["descriptor"]["parent_source_id"],
        "directory": str(directory),
        "report": report,
        "source_ready": False,
        "inventory_ready": False,
        "model_ready": False,
        "seconds": perf_counter() - started,
        "peak_rss_mib": peak / (1024 * 1024) if sys.platform == "darwin" else peak / 1024,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        receipt = run(args.source, args.output_root)
    except (ValueError, OSError, json.JSONDecodeError) as error:
        receipt = {"status": "failed", "error": str(error)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))  # noqa: T201 - explicit CLI receipt
    raise SystemExit(0 if receipt["status"] == "passed" else 1)


if __name__ == "__main__":
    main()
