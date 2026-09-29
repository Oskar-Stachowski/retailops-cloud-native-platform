"""Bounded local acceptance of the unpublished AI 06.6b.1 inventory extension."""

# ruff: noqa: INP001 - standalone acceptance script, not an application package

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from data.generator.identity import file_sha256
from data.inventory.contract import require

ROOT = Path(__file__).resolve().parents[2]
LIMIT_SECONDS = 300
LIMIT_RSS_MIB = 1024


def _execute(command: list[str], output: Path, expected: str) -> dict:
    completed = subprocess.run(  # noqa: S603 - controlled local CLIs, argument list without shell
        command, cwd=ROOT, capture_output=True, text=True, check=False, timeout=LIMIT_SECONDS
    )
    report = json.loads(output.read_text())
    require(
        report["status"] == expected and completed.returncode == (0 if expected == "passed" else 1),
        "CLI status/exit differs: " + completed.stdout + completed.stderr,
    )
    require(
        all(report[k] is False for k in ("source_ready", "inventory_ready", "model_ready")),
        "Candidate acceptance cannot claim source/model readiness.",
    )
    return report


def _case(
    directory: Path,
    label: str,
    profile: str,
    config: dict,
    producer_commit: str,
    *,
    expected: str = "passed",
    bounded: bool = False,
) -> dict:
    config_path, source_path, table_path = (
        directory / (label + suffix) for suffix in ("-config.json", "-source.json", "-tables.json")
    )
    config_path.write_text(json.dumps(config, indent=2) + "\n")
    source_command = [
        sys.executable,
        "-m",
        "data.inventory.run_source_commerce",
        "--profile",
        profile,
        "--inventory-config",
        str(config_path),
        "--output",
        str(source_path),
    ]
    if bounded:
        source_command.extend(
            ["--days", "8", "--products", "8", "--stores", "3", "--warehouses", "2"]
        )
    source = _execute(source_command, source_path, expected)
    require(
        source["code_provenance"]["git_commit"] == producer_commit
        and source["code_provenance"]["code_state"] == "clean",
        "Acceptance requires the pinned clean producer runtime.",
    )
    command = [
        sys.executable,
        "-m",
        "data.inventory.run_source_tables",
        "--candidate",
        str(source_path),
        "--output-root",
        str(directory / (label + "-artifacts")),
        "--output",
        str(table_path),
    ]
    tables = _execute(command, table_path, expected)
    require(
        tables["parent_execution_id"] == source["execution_id"],
        "Inventory extension lost parent execution lineage.",
    )
    require(
        source["seconds"] + tables["seconds"] < LIMIT_SECONDS
        and max(source["peak_rss_mib"], tables["peak_rss_mib"]) < LIMIT_RSS_MIB,
        "Local source plus native-table stage exceeded bounded budget.",
    )
    print(  # noqa: T201 - acceptance progress
        f"{label}: {expected}; source {source['seconds']:.2f}s, tables {tables['seconds']:.2f}s",
        flush=True,
    )
    return {
        "case": label,
        "profile": profile,
        "expected_status": expected,
        "source_command": source_command,
        "table_command": command,
        "source_receipt_sha256": file_sha256(source_path),
        "table_receipt_sha256": file_sha256(table_path),
        "parent_execution_id": source["execution_id"],
        "candidate_id": tables["candidate_id"],
        "input_tables_sha256": source["input_tables_sha256"],
        "operational_sha256": source["operational_sha256"],
        "simulation_sha256": source["simulation_sha256"],
        "reconciliation": tables["reconciliation"],
        "tables": tables["tables"],
        "source_seconds": source["seconds"],
        "table_seconds": tables["seconds"],
        "source_peak_rss_mib": source["peak_rss_mib"],
        "table_peak_rss_mib": tables["peak_rss_mib"],
    }


def run(output: Path) -> dict:
    output.parent.mkdir(parents=True, exist_ok=True)
    directory = output.parent / "acceptance"
    directory.mkdir(exist_ok=True)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()  # noqa: S607 - fixed read-only git invocation
    normal = json.loads((ROOT / "data/tests/fixtures/source-inventory-config-v1.json").read_text())
    cases = []
    for profile in ("ai-smoke", "ai-temporal-smoke"):
        pair = [
            _case(directory, profile + "-" + suffix, profile, normal, commit)
            for suffix in ("first", "repeat")
        ]
        for field in (
            "parent_execution_id",
            "candidate_id",
            "input_tables_sha256",
            "operational_sha256",
            "simulation_sha256",
            "reconciliation",
            "tables",
        ):
            require(pair[0][field] == pair[1][field], "Repeated candidate differs: " + field)
        cases.extend(pair)
    for label in ("supply-poor", "zero-opening", "late-availability"):
        config = json.loads(json.dumps(normal))
        if label == "supply-poor":
            config["supplier_parameters"]["reliability"] = "0"
        elif label == "zero-opening":
            config["stock"]["opening_quantity"] = 0
        else:
            config["sale_availability_delay_seconds"] = 9 * 86400
        cases.append(
            _case(
                directory,
                label,
                "ai-smoke",
                config,
                commit,
                expected="not_ready" if label == "late-availability" else "passed",
                bounded=True,
            )
        )
    damaged_path = directory / "corrupted-parent.json"
    damaged = json.loads((directory / "ai-smoke-first-source.json").read_text())
    damaged["inventory_snapshots"][0]["on_hand"] += 1
    damaged_path.write_text(json.dumps(damaged))
    failed_path = directory / "corrupted-parent-tables.json"
    _execute(
        [
            sys.executable,
            "-m",
            "data.inventory.run_source_tables",
            "--candidate",
            str(damaged_path),
            "--output-root",
            str(directory / "corrupted-artifacts"),
            "--output",
            str(failed_path),
        ],
        failed_path,
        "failed",
    )
    require(
        not (directory / "corrupted-artifacts").exists(), "Corrupted parent produced artifacts."
    )
    result = {
        "scope": "AI 06.6b.1 native inventory tables only",
        "producer_commit": commit,
        "acceptance_script_sha256": file_sha256(Path(__file__)),
        "source_ready": False,
        "inventory_ready": False,
        "model_ready": False,
        "status": "passed",
        "cases": cases,
        "cli_cases": len(cases) + 1,
        "corrupted_parent_rejected": True,
        "profiles_repeated_identically": True,
        "budget": {
            "seconds": LIMIT_SECONDS,
            "peak_rss_mib": LIMIT_RSS_MIB,
            "scope": "source-commerce candidate plus native inventory tables; excludes source quality/export/import/curated",
        },
    }
    output.write_text(json.dumps(result, indent=2) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.output)
    print(str(args.output))  # noqa: T201 - acceptance receipt


if __name__ == "__main__":
    main()
