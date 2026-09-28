"""Package an already qualified snapshot; never copy generator code into the handoff."""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path

from data.export.atomic import publish_directory
from data.export.policy import GENERATED_ROOT, ROOT, generated_target
from data.export.snapshot_validation import read_json, reference, safe_file, verify_snapshot
from data.generator.identity import file_sha256

CONTRACT_PATH = ROOT / "data/contracts/source_snapshot_handoff.v1.json"
FIXTURE_ROOT = ROOT / "data/fixtures/ai-smoke-v1"
CONTRACT_VERSION = "1.0.0"


def expected_manifest(snapshot: Path, manifest: dict) -> dict:
    """Pin physical transport separately from the source/snapshot logical identities."""
    report = json.loads((snapshot / "reports/source_report.json").read_text(encoding="utf-8"))
    return {
        "handoff_contract_version": CONTRACT_VERSION,
        "snapshot_schema_version": manifest["schema_version"],
        "source_schema_version": manifest["source"]["schema_version"],
        "source_dataset_id": manifest["source_dataset_id"],
        "snapshot_id": manifest["snapshot_id"],
        "snapshot_manifest_sha256": file_sha256(snapshot / "snapshot_manifest.json"),
        "resolved_parameters": manifest["source"]["descriptor"]["resolved_parameters"],
        "watermarks": manifest["source"]["watermarks"],
        "readiness": {key: value["status"] for key, value in report["readiness"].items()},
        "inventory_ready": manifest["source"]["inventory_ready"],
        "table_count": len(manifest["tables"]),
        "rows": sum(table["row_count"] for table in manifest["tables"]),
        "tables": [
            {
                key: table[key]
                for key in (
                    "table",
                    "data_class",
                    "row_count",
                    "content_sha256",
                    "grain",
                    "date_range",
                    "field_ranges",
                )
            }
            for table in manifest["tables"]
        ],
        "files": [
            reference(snapshot, path) for path in sorted(snapshot.rglob("*")) if path.is_file()
        ],
    }


def verify_handoff(package: Path) -> dict:
    """Check the frozen contract and expected metadata plus upstream typed parity."""
    if {p.name for p in package.iterdir()} != {
        "contract.json",
        "expected_manifest.json",
        "snapshot",
    }:
        msg = "Handoff package requires exactly contract, expected manifest and snapshot."
        raise ValueError(msg)
    contract = read_json(safe_file(package, "contract.json"))
    if contract != json.loads(CONTRACT_PATH.read_text(encoding="utf-8")):
        msg = "Handoff contract differs from the reviewed v1 contract."
        raise ValueError(msg)
    manifest = verify_snapshot(package / "snapshot")
    if (
        manifest["schema_version"] not in contract["supported_snapshot_versions"]
        or manifest["source"]["schema_version"] not in contract["supported_source_versions"]
    ):
        msg = "Unsupported handoff version."
        raise ValueError(msg)
    if manifest["source"]["descriptor"]["resolved_parameters"]["profile"] != "ai-smoke":
        msg = "The one current fixture must be ai-smoke."
        raise ValueError(msg)
    if manifest["descriptor"]["include_evaluation_truth"]:
        msg = "The reviewed handoff fixture contains facts only."
        raise ValueError(msg)
    for table in manifest["tables"]:
        expected = contract["fact_tables"][table["table"]]
        if any(table[key] != expected[key] for key in ("schema", "grain", "data_class")):
            msg = "Fixture schema/grain/classification differs from the handoff contract."
            raise ValueError(msg)
    expected = read_json(safe_file(package, "expected_manifest.json"))
    if expected != expected_manifest(package / "snapshot", manifest):
        msg = "Fixture differs from its reviewed expected manifest."
        raise ValueError(msg)
    paths = {
        "contract.json",
        "expected_manifest.json",
        *("snapshot/" + ref["path"] for ref in expected["files"]),
    }
    if {p.relative_to(package).as_posix() for p in package.rglob("*") if p.is_file()} != paths:
        msg = "Handoff package contains unreferenced files."
        raise ValueError(msg)
    return expected


def package_fixture(snapshot: Path, output: Path) -> dict:
    output = generated_target(output)
    if output.exists():
        msg = "Handoff output already exists; immutable packages cannot be overwritten."
        raise ValueError(msg)
    manifest = verify_snapshot(snapshot)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".handoff-", dir=output.parent) as temporary:
        staging = Path(temporary) / "package"
        staging.mkdir(mode=0o700)
        shutil.copytree(snapshot, staging / "snapshot")
        shutil.copyfile(CONTRACT_PATH, staging / "contract.json")
        (staging / "expected_manifest.json").write_text(
            json.dumps(expected_manifest(staging / "snapshot", manifest), indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        expected = verify_handoff(staging)
        publish_directory(staging, output)
    return {
        "contract_version": CONTRACT_VERSION,
        "output": str(output),
        "source_dataset_id": expected["source_dataset_id"],
        "snapshot_id": expected["snapshot_id"],
        "snapshot_files": len(expected["files"]),
        "tables": expected["table_count"],
        "rows": expected["rows"],
        "package_bytes": sum(path.stat().st_size for path in output.rglob("*") if path.is_file()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=GENERATED_ROOT / "handoff/ai-smoke-v1")
    args = parser.parse_args()
    print(json.dumps(package_fixture(args.snapshot_dir, args.output_dir), indent=2))  # noqa: T201 - CLI result


if __name__ == "__main__":
    main()
