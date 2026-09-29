"""Materialize an unpublished inventory extension from a verified 06.6a receipt."""

from __future__ import annotations

import argparse
import json
import resource
import sys
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from data.generator.identity import json_sha256
from data.inventory.contract import require
from data.inventory.projection import project_inventory
from data.inventory.projection_contract import ProjectionConfig
from data.inventory.source_contract import SOURCE_INVENTORY_VERSION, SourceInventoryConfig
from data.inventory.source_tables import reconcile_tables, tables_from_source
from data.inventory.source_tables_io import read_tables, write_tables


def validate_parent(source: dict) -> None:
    require(
        source["process_version"] == SOURCE_INVENTORY_VERSION
        and source["status"] in {"passed", "not_ready"},
        "Unsupported or failed source-commerce candidate.",
    )
    require(
        all(source[k] is False for k in ("source_ready", "inventory_ready", "model_ready")),
        "Parent candidate claims unsupported readiness.",
    )
    SourceInventoryConfig.from_payload(source["inventory_configuration"])
    facts = {
        n: source[n]
        for n in (
            "inventory",
            "commerce",
            "return_inventory_decisions",
            "inventory_snapshots",
            "legacy_stock_movements",
        )
    }
    require(
        json_sha256(facts) == source["operational_sha256"]
        and json_sha256(source["simulation_truth"]) == source["simulation_sha256"],
        "Parent candidate facts/truth checksum differs.",
    )
    expected = "source-inventory-candidate-sha256-" + json_sha256(
        {
            "process_version": SOURCE_INVENTORY_VERSION,
            "generation": source["generation_configuration"],
            "inventory_configuration": source["inventory_configuration"],
            "input_tables_sha256": source["input_tables_sha256"],
            "code_fingerprint": {
                k: v
                for k, v in source["code_provenance"].items()
                if k not in {"git_commit", "code_state"}
            },
            "operational_sha256": source["operational_sha256"],
            "simulation_sha256": source["simulation_sha256"],
        }
    )
    require(expected == source["execution_id"], "Parent candidate execution identity differs.")


def run(candidate: Path, output_root: Path, evaluated_at: str | None = None) -> dict:
    started = perf_counter()
    source = json.loads(candidate.read_text())
    validate_parent(source)
    settings = source["effective_configuration"]["scenario"]["settings"]
    configuration = ProjectionConfig.from_payload(
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
        configuration,
        evaluated_at=evaluated_at or configuration.end_at,
    )
    tables, context = tables_from_source(source, projection)
    counts = reconcile_tables(tables, context)
    path = write_tables(tables, context, output_root, source["execution_id"])
    restored, receipt, restored_context = read_tables(path)
    require(
        tables == restored and context == restored_context,
        "Inventory extension roundtrip differs from producer inputs.",
    )
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return {
        "verified_at": datetime.now(UTC).isoformat(),
        "scope": "AI 06.6b.1 unpublished native inventory tables",
        "status": source["status"],
        "source_ready": False,
        "inventory_ready": False,
        "model_ready": False,
        "lifecycle_label_qualification": "not_evaluated",
        "parent_execution_id": source["execution_id"],
        "candidate_id": receipt["candidate_id"],
        "table_contract_sha256": receipt["table_contract_sha256"],
        "directory": str(path),
        "reconciliation": counts,
        "tables": receipt["tables"],
        "seconds": perf_counter() - started,
        "peak_rss_mib": peak / (1024 * 1024) if sys.platform == "darwin" else peak / 1024,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify and materialize native inventory tables; this is not a source/snapshot export."
    )
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--evaluated-at")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = run(args.candidate, args.output_root, args.evaluated_at)
    except (ValueError, KeyError, TypeError, OSError, OverflowError) as error:
        result = {
            "status": "failed",
            "scope": "AI 06.6b.1 unpublished native inventory tables",
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
