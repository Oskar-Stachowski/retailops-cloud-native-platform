"""Fresh source and qualification acceptance, excluding the pending AI03 handoff."""

# ruff: noqa: INP001 - standalone acceptance entry point

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from data.generator.configuration import DatasetGenerationConfig
from data.generator.identity import file_sha256
from data.inventory.contract import require
from data.inventory.qualification_contract import MANIFEST, REPORT
from data.inventory.run_source_dataset import default_inventory_config
from data.inventory.source_dataset_contract import MANIFEST_FILENAME

ROOT = Path(__file__).resolve().parents[2]
LIMIT_SECONDS = 300
LIMIT_RSS_MIB = 1024


def execute(command: list[str], output: Path, expected_exit: int) -> dict:
    completed = subprocess.run(  # noqa: S603 - local CLI without shell
        command, cwd=ROOT, capture_output=True, text=True, check=False, timeout=LIMIT_SECONDS
    )
    receipt = json.loads(output.read_text())
    require(
        completed.returncode == expected_exit and receipt["status"] != "failed",
        "Qualification CLI failed: " + completed.stdout + completed.stderr,
    )
    return receipt


def case(
    directory: Path,
    label: str,
    profile: str,
    commit: str,
    *,
    config: dict | None = None,
    sizing: list[str] | None = None,
) -> dict:
    output = directory / (label + "-source.json")
    command = [
        sys.executable,
        "-m",
        "data.inventory.run_source_dataset",
        "--profile",
        profile,
        "--output-root",
        str(directory / (label + "-sources")),
        "--output",
        str(output),
        *(sizing or []),
    ]
    if config is not None:
        path = directory / (label + "-configuration.json")
        path.write_text(json.dumps(config, indent=2) + "\n")
        command.extend(["--inventory-config", str(path)])
    source = execute(command, output, 1 if label == "late-availability" else 0)
    source_path = Path(source["directory"])
    parent = json.loads((source_path / MANIFEST_FILENAME).read_text())
    source_before = {
        str(p.relative_to(source_path)): file_sha256(p)
        for p in source_path.rglob("*")
        if p.is_file()
    }
    qualified_output = directory / (label + "-qualification.json")
    qualify_command = [
        sys.executable,
        "-m",
        "data.inventory.run_qualification",
        "--source",
        str(source_path),
        "--output-root",
        str(directory / (label + "-qualifications")),
        "--output",
        str(qualified_output),
    ]
    qualified = execute(qualify_command, qualified_output, 0)
    candidate = Path(qualified["directory"])
    manifest = json.loads((candidate / MANIFEST).read_text())
    report = json.loads((candidate / REPORT).read_text())
    require(
        source_before
        == {
            str(p.relative_to(source_path)): file_sha256(p)
            for p in source_path.rglob("*")
            if p.is_file()
        },
        "Qualification altered immutable source.",
    )
    for receipt in (source, qualified):
        require(
            all(receipt[k] is False for k in ("source_ready", "inventory_ready", "model_ready")),
            "Local qualification cannot claim publication/model readiness.",
        )
    for payload in (parent, manifest):
        require(
            payload["provenance"]["git_commit"] == commit
            and payload["provenance"]["code_state"] == "clean",
            "Acceptance requires pinned clean runtime.",
        )
    seconds = source["seconds"] + qualified["seconds"]
    peak = max(source["peak_rss_mib"], qualified["peak_rss_mib"])
    require(
        seconds < LIMIT_SECONDS and peak < LIMIT_RSS_MIB,
        "Source + qualification exceeds bounded local budget.",
    )
    if label.startswith("ai-"):
        require(
            report["label_qualification"] == "qualified"
            and report["positive_labels"] > 0
            and report["negative_labels"] > 0,
            "Full smoke profile lacks qualifying classes.",
        )
    if label == "no-demand":
        require(
            report["positive_labels"] == report["negative_labels"] == 0
            and report["label_qualification"] == "not_evaluable",
            "Immature no-demand source acquired a label.",
        )
    if label == "late-availability":
        require(
            not report["source_facts_ready"] and report["label_qualification"] == "not_evaluable",
            "Unavailable source cannot qualify labels globally.",
        )
    print(  # noqa: T201 - acceptance progress
        f"{label}: {report['label_qualification']}; positive={report['positive_labels']}, negative={report['negative_labels']}; {seconds:.2f}s, {peak:.2f} MiB",
        flush=True,
    )
    return {
        "case": label,
        "profile": profile,
        "commands": [command, qualify_command],
        "source_id": source["dataset_id"],
        "source_facts_ready": source["facts_ready"],
        "source_descriptor": parent["descriptor"],
        "source_artifacts": parent["artifacts"],
        "source_reports": parent["reports"],
        "source_manifest_sha256": file_sha256(source_path / MANIFEST_FILENAME),
        "source_receipt_sha256": file_sha256(output),
        "qualification_id": manifest["qualification_id"],
        "qualification_descriptor": manifest["descriptor"],
        "qualification_artifacts": {"windows": manifest["windows"], "report": manifest["report"]},
        "qualification_manifest_sha256": file_sha256(candidate / MANIFEST),
        "qualification_receipt_sha256": file_sha256(qualified_output),
        "report": report,
        "source_unchanged": True,
        "source_seconds": source["seconds"],
        "qualification_seconds": qualified["seconds"],
        "seconds": seconds,
        "peak_rss_mib": peak,
    }


def run(output: Path) -> dict:
    directory = output.parent / "acceptance"
    directory.mkdir(parents=True, exist_ok=True)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()  # noqa: S607 - fixed read-only Git
    cases = []
    for profile in ("ai-smoke", "ai-temporal-smoke"):
        first = case(directory, profile + "-first", profile, commit)
        repeat = case(directory, profile + "-repeat", profile, commit)
        require(
            all(
                first[k] == repeat[k]
                for k in (
                    "source_id",
                    "source_descriptor",
                    "source_artifacts",
                    "source_reports",
                    "qualification_id",
                    "qualification_descriptor",
                    "qualification_artifacts",
                    "report",
                )
            ),
            "Fresh source/qualification repeats differ.",
        )
        cases.extend([first, repeat])
    sizing = ["--days", "10", "--products", "4", "--stores", "2", "--warehouses", "2"]
    default = default_inventory_config(
        DatasetGenerationConfig(profile="ai-smoke", days=10)
    ).model_dump()
    for label in ("supplier-poor", "zero-opening", "late-availability"):
        config = json.loads(json.dumps(default))
        if label == "supplier-poor":
            config["supplier_parameters"].update(reliability="0", lead_time_mean_days="5")
        elif label == "zero-opening":
            config["stock"]["opening_quantity"] = 0
        else:
            config["sale_availability_delay_seconds"] = 86400
        cases.append(case(directory, label, "ai-smoke", commit, config=config, sizing=sizing))
    cases.append(
        case(
            directory,
            "no-demand",
            "ai-smoke",
            commit,
            sizing=[
                "--days",
                "1",
                "--products",
                "1",
                "--stores",
                "1",
                "--warehouses",
                "1",
                "--end-date",
                "2026-07-26",
            ],
        )
    )
    require(
        cases[-3]["report"]["statuses"].get("already_stockout", 0) > 0,
        "Zero opening lost already-stockout status.",
    )
    return {
        "verified_at": datetime.now(UTC).isoformat(),
        "scope": "AI 06.6b.2b local lifecycle/coverage acceptance",
        "status": "passed",
        "runtime_commit": commit,
        "fresh_repeats": "both standard profiles, identical source/qualification IDs, descriptors, artifacts and reports",
        "budgets": {
            "seconds": LIMIT_SECONDS,
            "peak_rss_mib": LIMIT_RSS_MIB,
            "scope": "fresh generation + source CSV + gates/readback + qualification/readback; excludes exporter/importer/curated03",
        },
        "source_ready": False,
        "inventory_ready": False,
        "model_ready": False,
        "cases": cases,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result = run(args.output)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print("Qualification acceptance passed.", flush=True)  # noqa: T201


if __name__ == "__main__":
    main()
