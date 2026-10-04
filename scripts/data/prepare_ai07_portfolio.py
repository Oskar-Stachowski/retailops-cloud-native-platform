"""Verify native source, export public parents and reconcile the complete offline DQ replay."""

# ruff: noqa: INP001 - executable script beside the existing data scripts

from __future__ import annotations

import argparse
import json
import resource
import time
from pathlib import Path

from data.day_coverage.package import build
from data.dq.full_package import write_fixture
from data.dq.full_scenarios import example_plan
from data.dq.full_source import full_events
from data.dq.source import load_source
from data.export.inventory_snapshot import export_inventory_snapshot
from data.inventory.contract import require
from data.inventory.qualification_io import write_qualification


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve()
    root = args.output_root.resolve()
    require(not root.is_relative_to(source), "Parents must be outside immutable source storage.")
    require(not args.bundle.resolve().is_relative_to(source), "Bundle must be outside source.")
    started = time.monotonic()
    tables, manifest = load_source(source)
    parameters = manifest["descriptor"]["resolved_parameters"]
    require(
        parameters["profile"] in {"ai-07-portfolio-v1", "ai-07-portfolio-v2"}
        and parameters["seed"] in (42, 137, 2026),
        "AI 07 requires the frozen portfolio profile and seed inventory.",
    )
    events = full_events(tables, manifest)
    qualification = write_qualification(source, root / "qualifications")
    public = export_inventory_snapshot(
        source,
        source.name,
        qualification,
        root / "public",
        required_use_cases=("anomaly_source",),
        chunk_rows=127,
        partition_by_day=True,
    )
    coverage = build(source, root / "coverage")
    plan = example_plan(events, source.name, seed=parameters["seed"])
    capture = write_fixture(source, plan, root / "capture")
    bundle = {
        "status": "passed",
        "source_dataset_id": source.name,
        "source": str(source),
        "public": public["path"],
        "coverage": coverage["directory"],
        "capture": str(capture),
        "private_scenario": str(source / "simulation_truth/anomaly_scenario.json"),
        "canonical_events": len(events),
        "partitioned_tables": [
            t["table"] for t in public["manifest"]["tables"] if t["partition_source_field"]
        ],
        "delivery_clock": "native_availability_with_causal_day_frontiers_v1",
        "dq_scope_selection": "lowest_volume_public_product_supporting_both_fault_types_v1",
        "elapsed_seconds": time.monotonic() - started,
        "peak_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "model_quality": "not_evaluated",
        "transport_durability": "offline_only",
    }
    args.bundle.parent.mkdir(parents=True, exist_ok=True)
    args.bundle.write_text(json.dumps(bundle, indent=2) + "\n")
    print(json.dumps(bundle), flush=True)  # noqa: T201 - CLI receipt
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
