"""Fresh-process acceptance of full source-bound fixtures, twice for both cases."""

from __future__ import annotations

import argparse
import json
import resource
import subprocess
import sys
from pathlib import Path
from time import perf_counter

from data.anomalies.example import example_plan as demand_plan
from data.anomalies.physical_scenarios import physical_example_plan
from data.anomalies.source_process import build_tables
from data.dq.full_package import read_fixture, write_fixture
from data.dq.full_scenarios import example_plan
from data.dq.full_source import full_events, source_binding
from data.dq.package import receipt
from data.dq.source import load_source
from data.generator.configuration import DatasetGenerationConfig
from data.generator.identity import ROOT, file_sha256
from data.inventory.contract import require
from data.inventory.run_source_dataset import default_inventory_config
from data.inventory.source_dataset_io import write_source_dataset


def hashes(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): file_sha256(p) for p in root.rglob("*") if p.is_file()}


def worker(case: str, workspace: Path) -> dict:
    started = perf_counter()
    require(not workspace.exists(), "Full DQ acceptance requires a fresh workspace.")
    generation = DatasetGenerationConfig(
        profile="ai-smoke", days=30, products=8, stores=3, warehouses=2, seed=42
    )
    config = default_inventory_config(generation)
    scenario = (demand_plan if case == "demand" else physical_example_plan)(generation)
    tables, context = build_tables(generation, scenario, config)
    source = write_source_dataset(
        tables, context, generation, config, workspace / "sources", scenario_plan=scenario
    )
    before = hashes(source)
    tables, manifest = load_source(source)
    events = full_events(tables, manifest)
    plan = example_plan(events, manifest["dataset_id"])
    fixture = write_fixture(source, plan, workspace / "fixtures")
    published = hashes(fixture)
    result = receipt(fixture, read_fixture(fixture, source))
    require(
        write_fixture(source, plan, workspace / "fixtures") == fixture,
        "Full immutable fixture reuse differs.",
    )
    require(
        hashes(source) == before and hashes(fixture) == published,
        "Source or immutable publication changed.",
    )
    require(
        all(result["checks"].values()) and len(result["injections"]) == 16,
        "Full acceptance reconciliation differs.",
    )
    return {
        "status": "passed",
        "case": case,
        "source_id": manifest["dataset_id"],
        "fixture_id": result["fixture_id"],
        "source_binding": source_binding(manifest, events),
        "report": result["report"],
        "checks": result["checks"],
        "injections": result["injections"],
        "source_hashes": before,
        "publication_hashes": published,
        "seconds": perf_counter() - started,
        "peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        / (1024**2 if sys.platform == "darwin" else 1024),
    }


def run(workspace: Path) -> dict:
    require(not workspace.exists(), "Full DQ acceptance requires a fresh workspace.")
    results = []
    for case in ("demand", "physical"):
        pair = []
        for suffix in ("first", "repeat"):
            started = perf_counter()
            completed = subprocess.run(  # noqa: S603 - fixed local module, individual arguments
                [
                    sys.executable,
                    "-m",
                    "data.dq.full_check",
                    "--worker",
                    "--case",
                    case,
                    "--workspace",
                    str(workspace / (case + "-" + suffix)),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )
            require(
                completed.returncode == 0,
                "Full DQ acceptance worker failed: " + completed.stdout + completed.stderr,
            )
            result = json.loads(completed.stdout)
            result["process_seconds"] = perf_counter() - started
            require(
                result["process_seconds"] < 300 and result["peak_rss_mib"] < 1024,
                "Full DQ fresh-process budget exceeded.",
            )
            pair.append(result)
            print(  # noqa: T201 - acceptance progress
                f"{case}-{suffix}: {result['report']['accepted']} accepted in {result['process_seconds']:.2f}s",
                file=sys.stderr,
                flush=True,
            )
        require(
            all(
                pair[0][k] == pair[1][k]
                for k in (
                    "source_id",
                    "fixture_id",
                    "source_hashes",
                    "publication_hashes",
                    "source_binding",
                    "report",
                )
            ),
            "Fresh full DQ bytes or identities differ.",
        )
        results.append({"case": case, "runs": pair})
    return {
        "status": "passed",
        "fresh_processes": 4,
        "max_seconds": 300,
        "max_rss_mib": 1024,
        "cases": results,
        "business_event_day_completeness": "not_qualified",
        "model_ready": False,
        "transport_durability_proven": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--case", choices=("demand", "physical"), default="demand")
    args = parser.parse_args()
    if args.output and args.output.resolve().is_relative_to(args.workspace.resolve()):
        parser.error("Receipt must be outside immutable acceptance storage")
    result = worker(args.case, args.workspace) if args.worker else run(args.workspace)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))  # noqa: T201 - structured worker receipt


if __name__ == "__main__":
    main()
