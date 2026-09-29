from __future__ import annotations

import argparse
import json
import resource
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from data.generator.identity import code_fingerprint, code_provenance, file_sha256, json_sha256
from data.inventory.contract import require, utc_timestamp
from data.inventory.projection import project_inventory, reconcile_projection
from data.inventory.projection_contract import ProjectionConfig


def run(simulation_path: Path, config_path: Path, *, evaluated_at: str) -> dict:
    started = perf_counter()
    parent = json.loads(simulation_path.read_text(encoding="utf-8"))
    config = ProjectionConfig.from_payload(json.loads(config_path.read_text(encoding="utf-8")))
    require(
        parent["status"] in {"passed", "not_ready"},
        "Projection requires a valid chronological execution.",
    )
    require(
        parent["operational_sha256"] == json_sha256(parent["operational"])
        and parent["simulation_sha256"] == json_sha256(parent["simulation_truth"]),
        "Parent execution content hash mismatch.",
    )
    chronology = parent["effective_configuration"]["chronology"]
    require(
        utc_timestamp(config.start_at) == utc_timestamp(chronology["start_at"])
        and utc_timestamp(config.end_at) == utc_timestamp(chronology["end_at"]),
        "Projection window differs from parent execution.",
    )
    projection = project_inventory(
        parent["operational"], parent["simulation_truth"], config, evaluated_at=evaluated_at
    )
    counts = reconcile_projection(projection, parent["operational"], parent["simulation_truth"])
    require(
        counts["lost_sales_quantity"] == parent["demand_reconciliation"]["lost_sales_quantity"]
        and len(parent["simulation_truth"]["demand_outcomes"])
        == parent["demand_reconciliation"]["arrivals"],
        "Parent demand reconciliation mismatch.",
    )
    diagnostics = projection["simulation_truth"]["window_diagnostics"]
    classes = Counter(r["incident_stockout"] for r in diagnostics if r["status"] == "evaluable")
    files = tuple(
        str(p.relative_to(Path(__file__).resolve().parents[2]))
        for p in sorted(Path(__file__).resolve().parent.glob("*.py"))
    )
    schemas = tuple(
        f"data/contracts/{name}.v1.schema.json"
        for name in (
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
        )
    )
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return {
        "verified_at": datetime.now(UTC).isoformat(),
        "status": "not_ready"
        if parent["status"] == "not_ready"
        or any(r["status"] == "not_available" for r in projection["operational"])
        else "passed",
        "scope": "AI 06.5 standalone ledger snapshots and private stockout diagnostics; not source publication or model acceptance",
        "inventory_ready": False,
        "input_sha256": {
            "simulation": file_sha256(simulation_path),
            "configuration": file_sha256(config_path),
        },
        "parent_execution": {
            "implementation_commit": parent["code_provenance"]["git_commit"],
            "operational_sha256": parent["operational_sha256"],
            "simulation_sha256": parent["simulation_sha256"],
        },
        "evaluated_at": utc_timestamp(evaluated_at).isoformat(),
        "projection": projection,
        "reconciliation": counts,
        "operational_sha256": json_sha256(projection["operational"]),
        "simulation_sha256": json_sha256(projection["simulation_truth"]),
        "stockout_model_readiness": {
            "model_ready": False,
            "label_diagnostics_status": "evaluable" if set(classes) == {0, 1} else "not_evaluable",
            "reason": None
            if set(classes) == {0, 1}
            else "single_class"
            if classes
            else "no_eligible_windows",
            "eligible_windows": sum(classes.values()),
            "class_0": classes[0],
            "class_1": classes[1],
        },
        "seconds": perf_counter() - started,
        "peak_rss_mib": peak / (1024 * 1024) if sys.platform == "darwin" else peak / 1024,
        "code_provenance": code_provenance(code_fingerprint((*files, *schemas))),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Project AI 06.5 snapshots and private stockout diagnostics."
    )
    for name in ("simulation", "config", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--evaluated-at", required=True)
    args = parser.parse_args()
    try:
        result = run(args.simulation, args.config, evaluated_at=args.evaluated_at)
    except (ValueError, OSError, OverflowError, KeyError, TypeError) as error:
        result = {"status": "failed", "scope": "AI 06.5 inventory projection", "error": str(error)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": result["status"], "report": str(args.output)}))  # noqa: T201 - CLI receipt
    if result["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
