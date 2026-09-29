from __future__ import annotations

import argparse
import json
import resource
import sys
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from data.generator.identity import code_fingerprint, code_provenance, file_sha256, json_sha256
from data.inventory.simulation_reconciliation import reconcile_simulation, verify_demand_outcomes
from data.inventory.simulator import ChronologicalSimulator


def run(
    scenario_path: Path,
    ledger_path: Path,
    supply_path: Path,
    policy_path: Path,
    fulfillment_path: Path,
    truth_path: Path,
) -> dict:
    started = perf_counter()
    paths = {
        "scenario": scenario_path,
        "ledger": ledger_path,
        "supply": supply_path,
        "policy": policy_path,
        "fulfillment": fulfillment_path,
        "supplier_truth": truth_path,
    }
    inputs = {k: json.loads(p.read_text(encoding="utf-8")) for k, p in paths.items()}
    engine = ChronologicalSimulator(
        inputs["ledger"],
        inputs["supply"],
        inputs["scenario"],
        inputs["policy"],
        inputs["fulfillment"],
        inputs["supplier_truth"],
    )
    result = engine.execute()
    commerce = reconcile_simulation(result["operational"])
    demand = verify_demand_outcomes(
        result["operational"], result["simulation_truth"], tuple(engine.scenario.demand_arrivals)
    )
    missing = {"config_unavailable", "inventory_unknown", "history_missing", "supplier_missing"}
    status = (
        "not_ready"
        if any(
            d["status"] in missing for r in result["operational"]["reviews"] for d in r["decisions"]
        )
        else "passed"
    )
    files = tuple(
        str(p.relative_to(Path(__file__).resolve().parents[2]))
        for p in sorted(Path(__file__).resolve().parent.glob("*.py"))
    )
    names = (
        "inventory_ledger",
        "replenishment",
        "supplier_simulation_truth",
        "reorder_config",
        "inventory_history_coverage",
        "supplier_fulfillment_config",
        "chronological_scenario",
        "inventory_fulfillment_routes",
        "inventory_commerce_output",
    )
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return {
        "verified_at": datetime.now(UTC).isoformat(),
        "status": status,
        "scope": "AI 06.4 bounded chronological execution; not source/snapshot/inventory readiness acceptance",
        "inventory_ready": False,
        "input_sha256": {k: file_sha256(p) for k, p in paths.items()},
        "effective_configuration": {
            "chronology": engine.scenario.settings.model_dump(),
            "operational_policy": engine.policy.model_dump(),
            "simulation_truth": {
                "fulfillment": engine.fulfillment.model_dump(),
                "supplier_parameters": [
                    t.model_dump()
                    for t in sorted(engine.parameters.values(), key=lambda t: t.supplier_id)
                ],
            },
        },
        **result,
        "commerce_reconciliation": commerce,
        "demand_reconciliation": demand,
        "operational_sha256": json_sha256(result["operational"]),
        "simulation_sha256": json_sha256(result["simulation_truth"]),
        "seconds": perf_counter() - started,
        "peak_rss_mib": peak / (1024 * 1024) if sys.platform == "darwin" else peak / 1024,
        "code_provenance": code_provenance(
            code_fingerprint((*files, *(f"data/contracts/{n}.v1.schema.json" for n in names)))
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the AI 06.4 chronological shared-stock generator."
    )
    for name in (
        "scenario",
        "ledger",
        "supply",
        "policy",
        "fulfillment-config",
        "supplier-truth",
        "output",
    ):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    try:
        result = run(
            args.scenario,
            args.ledger,
            args.supply,
            args.policy,
            args.fulfillment_config,
            args.supplier_truth,
        )
    except (ValueError, OSError, OverflowError) as error:
        result = {
            "status": "failed",
            "scope": "AI 06.4 chronological execution",
            "error": str(error),
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
