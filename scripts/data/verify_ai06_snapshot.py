"""AI06.6b.2c.1 fresh cross-repo export/import acceptance; curated remains pending."""

# ruff: noqa: INP001 - standalone acceptance CLI

from __future__ import annotations

import argparse
import json
import resource
import subprocess
import sys
from pathlib import Path
from time import perf_counter

from scripts.data.verify_ai06_qualification import ROOT, case

from data.export.inventory_snapshot import export_inventory_snapshot
from data.generator.identity import file_sha256
from data.inventory.contract import require


def export_worker(args: argparse.Namespace) -> dict:
    started = perf_counter()
    result = export_inventory_snapshot(
        args.source,
        args.source.name,
        args.qualification,
        args.snapshot_root,
        include_truth=args.truth,
    )
    return {
        "publication": result["publication"],
        "path": result["path"],
        "source_id": result["manifest"]["source_dataset_id"],
        "snapshot_id": result["manifest"]["snapshot_id"],
        "descriptor": result["manifest"]["descriptor"],
        "tables": len(result["manifest"]["tables"]),
        "seconds": perf_counter() - started,
        "peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        / (1024**2 if sys.platform == "darwin" else 1024),
    }


def execute(command: list[str], cwd: Path) -> dict:
    completed = subprocess.run(  # noqa: S603 - fixed local CLI, individual arguments
        command, cwd=cwd, text=True, capture_output=True, timeout=300, check=False
    )
    require(
        completed.returncode == 0, "Cross-repo CLI failed: " + completed.stdout + completed.stderr
    )
    return json.loads(completed.stdout)


def run(args: argparse.Namespace) -> dict:
    report_root = args.output.parent / "acceptance"
    report_root.mkdir(parents=True, exist_ok=True)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()  # noqa: S607 - fixed read-only Git
    ai_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"],  # noqa: S607 - read-only Git
        cwd=args.ai_repo,
        text=True,
    ).strip()
    results = []
    for profile in ("ai-smoke", "ai-temporal-smoke"):
        repeats = []
        for suffix in ("first", "repeat"):
            label = profile + "-" + suffix
            source = case(report_root, label, profile, commit)
            parent = json.loads((report_root / (label + "-source.json")).read_text())
            qualification = json.loads((report_root / (label + "-qualification.json")).read_text())
            command = [
                sys.executable,
                "-m",
                "scripts.data.verify_ai06_snapshot",
                "--worker-export",
                "--source",
                str(Path(parent["directory"]).absolute()),
                "--qualification",
                str(Path(qualification["directory"]).absolute()),
                "--snapshot-root",
                str(ROOT / "data/generated" / args.output.parent.name / label / "snapshots"),
            ]
            exported = execute(command, ROOT)
            imported = execute(
                [
                    str(args.ai_python),
                    "scripts/check_snapshot_import.py",
                    "--worker",
                    "--snapshot-dir",
                    exported["path"],
                    "--workspace",
                    str(args.ai_repo / args.output.parent.name / label / "data/generated"),
                ],
                args.ai_repo,
            )
            import_seconds = imported["seconds"]
            total = source["seconds"] + exported["seconds"] + import_seconds
            require(
                exported["tables"] == imported["tables"] == 43
                and imported["snapshot_id"] == exported["snapshot_id"]
                and imported["typed_parity"] == "passed",
                "Cross-repo typed import differs.",
            )
            item = {
                "case": label,
                "profile": profile,
                "source_id": source["source_id"],
                "qualification_id": source["qualification_id"],
                "snapshot_id": exported["snapshot_id"],
                "source_seconds": source["source_seconds"],
                "qualification_seconds": source["qualification_seconds"],
                "export_seconds": exported["seconds"],
                "import_seconds": import_seconds,
                "seconds": total,
                "producer_peak_rss_mib": max(source["peak_rss_mib"], exported["peak_rss_mib"]),
                "consumer_peak_rss_mib": imported["peak_rss_mib"],
                "export": exported,
                "import": imported,
                "source_receipt_sha256": file_sha256(report_root / (label + "-source.json")),
                "qualification_receipt_sha256": file_sha256(
                    report_root / (label + "-qualification.json")
                ),
            }
            peak = max(item["producer_peak_rss_mib"], item["consumer_peak_rss_mib"])
            item["status"] = "passed" if total < 300 and peak < 1024 else "failed"
            (report_root / (label + "-pipeline.json")).write_text(json.dumps(item, indent=2) + "\n")
            require(
                item["status"] == "passed",
                f"Fresh export/import budget failed: {total:.2f}s, {peak:.2f} MiB.",
            )
            repeats.append(item)
            print(  # noqa: T201 - acceptance progress
                f"{label}: source -> qualification -> snapshot -> import passed in {total:.2f}s",
                flush=True,
            )
        require(
            all(
                repeats[0][k] == repeats[1][k]
                for k in ("source_id", "qualification_id", "snapshot_id")
            )
            and repeats[0]["export"]["descriptor"] == repeats[1]["export"]["descriptor"],
            "Fresh cross-repo repeats differ.",
        )
        results.extend(repeats)
    return {
        "status": "passed",
        "scope": "AI06.6b.2c.1 source/qualification/export/import; curated and default switch pending",
        "producer_commit": commit,
        "consumer_commit": ai_commit,
        "cases": results,
        "limits": {"seconds": 300, "rss_mib": 1024},
        "curated": "not_evaluated",
        "default_ai_source": "2.6.0",
        "source_ready": False,
        "inventory_ready": False,
        "model_ready": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ai-repo", type=Path)
    parser.add_argument("--ai-python", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--worker-export", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--qualification", type=Path)
    parser.add_argument("--snapshot-root", type=Path)
    parser.add_argument("--truth", action="store_true")
    args = parser.parse_args()
    if args.worker_export:
        result = export_worker(args)
        print(json.dumps(result))  # noqa: T201 - worker receipt
    else:
        require(
            all((args.ai_repo, args.ai_python, args.output)),
            "AI repo, Python and output are required.",
        )
        result = run(args)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
