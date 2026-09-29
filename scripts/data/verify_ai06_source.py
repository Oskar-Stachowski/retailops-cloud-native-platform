"""Local source 2.7 acceptance; excludes the still-pending AI03 handoff budget."""

# ruff: noqa: INP001 - standalone acceptance script

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
from data.inventory.run_source_dataset import default_inventory_config
from data.inventory.source_dataset_contract import MANIFEST_FILENAME

ROOT = Path(__file__).resolve().parents[2]
LIMIT_SECONDS = 300
LIMIT_RSS_MIB = 1024


def case(
    directory: Path,
    label: str,
    profile: str,
    commit: str,
    *,
    config: dict | None = None,
    expected: str = "passed",
    sizing: list[str] | None = None,
) -> dict:
    output = directory / (label + ".json")
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
    ]
    if config is not None:
        config_path = directory / (label + "-configuration.json")
        config_path.write_text(json.dumps(config, indent=2) + "\n")
        command.extend(["--inventory-config", str(config_path)])
    command.extend(sizing or [])
    completed = subprocess.run(  # noqa: S603 - fixed local CLI without shell
        command, cwd=ROOT, capture_output=True, text=True, check=False, timeout=LIMIT_SECONDS
    )
    receipt = json.loads(output.read_text())
    require(
        receipt["status"] == expected
        and completed.returncode == (0 if expected == "passed" else 1),
        "Source CLI status/exit differs: "
        + json.dumps(receipt.get("error"))
        + completed.stdout
        + completed.stderr,
    )
    require(
        all(receipt[k] is False for k in ("source_ready", "inventory_ready", "model_ready")),
        "Local source scope cannot claim publication/model readiness.",
    )
    source = Path(receipt["directory"])
    manifest = json.loads((source / MANIFEST_FILENAME).read_text())
    require(
        manifest["provenance"]["git_commit"] == commit
        and manifest["provenance"]["code_state"] == "clean",
        "Source acceptance requires pinned clean runtime.",
    )
    require(
        receipt["seconds"] < LIMIT_SECONDS and receipt["peak_rss_mib"] < LIMIT_RSS_MIB,
        "Local source stage exceeds its bounded budget.",
    )
    report = json.loads((source / "source_report.json").read_text())
    print(  # noqa: T201 - acceptance progress
        f"{label}: {expected}; {receipt['seconds']:.2f}s, {receipt['peak_rss_mib']:.2f} MiB",
        flush=True,
    )
    return {
        "case": label,
        "profile": profile,
        "command": command,
        "status": expected,
        "dataset_id": receipt["dataset_id"],
        "facts_ready": receipt["facts_ready"],
        "receipt_sha256": file_sha256(output),
        "manifest_sha256": file_sha256(source / MANIFEST_FILENAME),
        "descriptor": manifest["descriptor"],
        "artifacts": manifest["artifacts"],
        "reports": manifest["reports"],
        "checks": report["checks"],
        "seconds": receipt["seconds"],
        "peak_rss_mib": receipt["peak_rss_mib"],
    }


def run(output: Path) -> dict:
    directory = output.parent / "acceptance"
    directory.mkdir(parents=True, exist_ok=True)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()  # noqa: S607 - fixed read-only git call
    cases = []
    for profile in ("ai-smoke", "ai-temporal-smoke"):
        first = case(directory, profile + "-first", profile, commit)
        second = case(directory, profile + "-repeat", profile, commit)
        require(
            all(
                first[k] == second[k]
                for k in ("dataset_id", "descriptor", "artifacts", "reports", "checks")
            ),
            "Fresh source repeat identity/content/quality differs.",
        )
        cases.extend([first, second])
    default = default_inventory_config(DatasetGenerationConfig(profile="ai-smoke")).model_dump()
    sizing = ["--days", "10", "--products", "4", "--stores", "2", "--warehouses", "2"]
    for label in ("supplier-poor", "zero-opening", "late-availability"):
        config = json.loads(json.dumps(default))
        expected = "passed"
        if label == "supplier-poor":
            config["supplier_parameters"].update(reliability="0", lead_time_mean_days="5")
        elif label == "zero-opening":
            config["stock"]["opening_quantity"] = 0
        else:
            config["sale_availability_delay_seconds"] = 86400
            expected = "not_ready"
        cases.append(
            case(
                directory,
                label,
                "ai-smoke",
                commit,
                config=config,
                expected=expected,
                sizing=sizing,
            )
        )
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
    no_demand = cases[-1]["descriptor"]["tables"]
    require(
        no_demand["inventory_demand_arrivals"]["row_count"]
        == no_demand["sales"]["row_count"]
        == no_demand["stockout_episodes"]["row_count"]
        == 0,
        "No-demand source cannot acquire fictitious sales or stockout events.",
    )
    return {
        "verified_at": datetime.now(UTC).isoformat(),
        "scope": "AI 06.6b.2a versioned inventory source",
        "status": "passed",
        "producer_commit": commit,
        "source_ready": False,
        "inventory_ready": False,
        "model_ready": False,
        "label_qualification": "not_evaluated",
        "cases": cases,
        "repeat_identity_and_bytes": True,
        "budget": {
            "stage": "fresh generator + inventory source CSV + recomputed quality/readback",
            "limit_seconds": LIMIT_SECONDS,
            "limit_rss_mib": LIMIT_RSS_MIB,
            "ai03_export_import_curated_included": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = run(args.output)
    args.output.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"status": receipt["status"], "report": str(args.output)}))  # noqa: T201 - CLI receipt


if __name__ == "__main__":
    main()
