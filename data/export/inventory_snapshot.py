"""Publish source 2.7 facts and opt-in private evaluation as immutable snapshot 1.1."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import pyarrow as pa
import pyarrow.parquet as pq

from data.export.ai_snapshot import exporter_provenance, publication_lock
from data.export.atomic import publish_directory, sync_bundle
from data.export.inventory_contract import (
    FACT_TABLES,
    FORMAT,
    GATES,
    LEGACY_SCHEMAS,
    POLICY,
    SCHEMAS,
    TRUTH_TABLES,
    InventorySnapshot,
    columns,
    handoff_contract,
    table_schema,
)
from data.export.inventory_typed import logical, source_row, typed_row
from data.export.policy import ROOT, generated_target
from data.export.schema import typed_row as commerce_typed
from data.export.snapshot_contract import MANIFEST_NAME
from data.export.snapshot_validation import reference, safe_file
from data.generator.identity import canonical_json, file_sha256, json_sha256
from data.inventory.contract import require
from data.inventory.ledger import InventoryLedger
from data.inventory.qualification import qualification_report, qualify_windows
from data.inventory.qualification_contract import MANIFEST as QUAL_MANIFEST
from data.inventory.qualification_contract import REPORT as QUAL_REPORT
from data.inventory.qualification_contract import WINDOWS as QUAL_WINDOWS
from data.inventory.qualification_io import read_sealed_qualification
from data.inventory.simulation_reconciliation import reconcile_simulation
from data.inventory.snapshots import daily_snapshots
from data.inventory.source_dataset_contract import (
    MANIFEST_FILENAME,
    SourceManifest,
    data_class,
    grain,
)
from data.inventory.source_dataset_io import (
    CONFIG_PATH,
    REPORT_NAMES,
    load_json,
    read_source_dataset,
    table_identity,
)
from data.inventory.source_tables import TableContext, operational_from_tables, reconcile_tables
from data.inventory.source_tables_contract import TABLES

USE_CASES = {"forecast_source", "inventory_source"}
CHUNK_ROWS = 8192
MAX_CHUNK_ROWS = 65536


def copy_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream, target.open("xb") as destination:
        shutil.copyfileobj(stream, destination, length=1024 * 1024)
    target.chmod(0o600)


def export_schema_file(name: str, parent: dict) -> Path:
    """Keep ordinary exports compatible with the pinned pre-planning consumer."""
    filename = (
        LEGACY_SCHEMAS.get(name, name)
        if parent["descriptor"]["generator_version"] == "0.9.0"
        else name
    )
    return ROOT / "data/contracts" / filename


def seal_source(source: Path, target: Path, dataset_id: str) -> tuple[dict, dict]:
    require(
        not source.is_symlink() and not any(p.is_symlink() for p in source.rglob("*")),
        "Symlink in source input.",
    )
    payload = load_json(safe_file(source, MANIFEST_FILENAME))
    original = SourceManifest.model_validate(payload).model_dump()
    require(original == payload, "Noncanonical source input manifest.")
    require(original["dataset_id"] == dataset_id, "Explicit source ID differs.")
    names = [
        MANIFEST_FILENAME,
        CONFIG_PATH,
        *REPORT_NAMES,
        *(r["path"] for r in original["artifacts"].values()),
    ]
    require(
        {p.relative_to(source).as_posix() for p in source.rglob("*") if p.is_file()} == set(names),
        "Unallowlisted source input file.",
    )
    for name in names:
        copy_file(safe_file(source, name), target / name)
    tables, sealed = read_source_dataset(target)
    require(sealed == original, "Source changed during sealing.")
    require(sealed["facts_ready"], "Inventory snapshot requires passed source facts gates.")
    return tables, sealed


def seal_qualification(
    source: Path, target: Path, tables: dict, parent: dict
) -> tuple[list[dict], dict, dict]:
    require(
        not source.is_symlink() and not any(p.is_symlink() for p in source.rglob("*")),
        "Symlink in qualification input.",
    )
    require(
        {p.relative_to(source).as_posix() for p in source.rglob("*") if p.is_file()}
        == {QUAL_MANIFEST, QUAL_REPORT, QUAL_WINDOWS},
        "Unallowlisted qualification input file.",
    )
    for name in (QUAL_MANIFEST, QUAL_REPORT, QUAL_WINDOWS):
        copy_file(safe_file(source, name), target / name)
    return read_sealed_qualification(target, tables, parent)


def metadata_names(manifest: dict) -> set[str]:
    desc = manifest["descriptor"]
    names = {
        "manifests/" + MANIFEST_FILENAME,
        *("reports/" + n for n in REPORT_NAMES),
        *("schemas/" + n for n in (*SCHEMAS, "source_snapshot_handoff.v1_1.json")),
        *("schemas/" + t["table"] + ".arrow.json" for t in manifest["tables"]),
    }
    if desc["include_evaluation_truth"]:
        names |= {
            "evaluation_truth/qualification/" + n
            for n in (QUAL_MANIFEST, QUAL_REPORT, QUAL_WINDOWS)
        }
    return names


def verify_inventory_snapshot(  # noqa: PLR0915 - sequential independent validation gates
    root: Path, *, allow_evaluation_truth: bool = False, scratch: Path | None = None
) -> dict:
    require(
        not root.is_symlink() and not any(p.is_symlink() for p in root.rglob("*")),
        "Symlink in inventory snapshot.",
    )
    payload = load_json(safe_file(root, MANIFEST_NAME))
    manifest = InventorySnapshot.model_validate(payload).model_dump(by_alias=True)
    require(manifest == payload, "Noncanonical inventory snapshot manifest.")
    desc, parent = manifest["descriptor"], manifest["source"]
    require(
        manifest["snapshot_id"] == "snapshot-sha256-" + json_sha256(desc),
        "Snapshot identity differs.",
    )
    require(
        parent["dataset_id"]
        == manifest["source_dataset_id"]
        == desc["parent_source_dataset_id"]
        == "source-sha256-" + json_sha256(parent["descriptor"]),
        "Snapshot source lineage differs.",
    )
    qdesc = desc["qualification"]
    require(
        desc["parent_qualification_id"] == "inventory-labels-sha256-" + json_sha256(qdesc)
        and qdesc["parent_source_id"] == parent["dataset_id"],
        "Snapshot qualification lineage differs.",
    )
    require(
        qdesc["evaluated_at"] == parent["descriptor"]["context"]["evaluated_at"]
        and qdesc["horizon_days"] == 7,
        "Qualification time/horizon differs.",
    )
    require(
        parent["facts_ready"]
        and desc["required_use_cases"]
        and len(set(desc["required_use_cases"])) == len(desc["required_use_cases"])
        and set(desc["required_use_cases"]) <= USE_CASES,
        "Unqualified/unsupported inventory snapshot use case.",
    )
    require(
        not desc["include_evaluation_truth"] or allow_evaluation_truth,
        "Evaluation truth requires explicit opt-in.",
    )
    selected = (*FACT_TABLES, *(TRUTH_TABLES if desc["include_evaluation_truth"] else ()))
    require(
        [t["table"] for t in manifest["tables"]] == list(selected),
        "Inventory snapshot table allowlist differs.",
    )
    require(
        {r["path"] for r in manifest["metadata_files"]} == metadata_names(manifest),
        "Inventory metadata allowlist differs.",
    )
    refs = [*manifest["metadata_files"], *(r for t in manifest["tables"] for r in t["files"])]
    require(len(refs) == len({r["path"] for r in refs}), "Duplicate snapshot file reference.")
    for ref in refs:
        path = safe_file(root, ref["path"])
        require(
            reference(root, path) == {k: ref[k] for k in ("path", "bytes", "sha256")},
            "Inventory snapshot byte checksum differs.",
        )
    require(
        {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
        == {MANIFEST_NAME, "manifest.sha256", *(r["path"] for r in refs)},
        "Extra inventory snapshot file.",
    )
    require(
        (root / "manifest.sha256").read_text() == file_sha256(root / MANIFEST_NAME) + "\n",
        "Inventory manifest checksum differs.",
    )
    require(
        load_json(root / "manifests" / MANIFEST_FILENAME) == parent, "Source manifest copy differs."
    )
    require(
        desc["schemas"]
        == {
            r["path"]: r["sha256"]
            for r in manifest["metadata_files"]
            if r["path"].startswith("schemas/")
        },
        "Schema identity differs.",
    )
    checked_schemas = {name: (root / "schemas" / name).read_bytes() for name in SCHEMAS}
    allowed_schemas = [{name: (ROOT / "data/contracts" / name).read_bytes() for name in SCHEMAS}]
    if parent["descriptor"]["generator_version"] == "0.9.0":
        allowed_schemas.append(
            {
                name: (ROOT / "data/contracts" / LEGACY_SCHEMAS.get(name, name)).read_bytes()
                for name in SCHEMAS
            }
        )
    require(checked_schemas in allowed_schemas, "Unreviewed snapshot schema.")
    require(
        load_json(root / "schemas/source_snapshot_handoff.v1_1.json") == handoff_contract(),
        "Unreviewed inventory handoff.",
    )
    for name in REPORT_NAMES:
        ref = parent["reports"][name]
        path = root / "reports" / name
        require(
            file_sha256(path) == ref["sha256"] and path.stat().st_size == ref["size_bytes"],
            "Source report copy differs.",
        )
    require(
        desc["source_qualification_sha256"] == file_sha256(root / "reports/source_report.json"),
        "Source qualification fingerprint differs.",
    )
    report = load_json(root / "reports/source_report.json")
    require(
        report["status"] == "passed"
        and report["facts_ready"]
        and len(report["checks"]) == len(GATES)
        and {c["check_id"] for c in report["checks"]} == set(GATES)
        and all(
            c["status"] == "passed"
            and c["severity"] == "hard"
            and c.get("value", 0) == 0
            and c.get("threshold", 0) == 0
            for c in report["checks"]
        ),
        "Source hard gate is not passed.",
    )
    for kind in ("code", "dependency"):
        require(
            json_sha256(parent["provenance"][kind + "_files"])
            == parent["descriptor"][kind + "_sha256"],
            "Source provenance differs.",
        )
    require(
        json_sha256(manifest["exporter"]["code_files"]) == desc["exporter_code_sha256"]
        and manifest["exporter"]["dependency_sha256"] == desc["dependency_sha256"],
        "Exporter provenance differs.",
    )
    restored = {}
    with TemporaryDirectory(prefix=".inventory-snapshot-verify-", dir=scratch) as temporary:
        work = Path(temporary)
        logical_tables = []
        for table in manifest["tables"]:
            name, schema = table["table"], table_schema(table["table"])
            require(
                table["schema"] == columns(name)
                and table["grain"] == grain(name)
                and table["data_class"] == data_class(name)
                and table["partition_source_field"] is None,
                "Inventory schema/grain/class differs.",
            )
            require(
                load_json(root / "schemas" / (name + ".arrow.json"))
                == {"table": name, "schema": columns(name)},
                "Arrow schema declaration differs.",
            )
            namespace = "evaluation_truth" if data_class(name) == "simulation_truth" else "facts"
            rows = []
            for index, ref in enumerate(table["files"]):
                require(
                    ref["path"] == f"{namespace}/{name}/part-{index:06d}.parquet",
                    "Inventory Parquet placement differs.",
                )
                parquet = pq.ParquetFile(root / ref["path"])
                require(
                    parquet.schema_arrow.equals(schema, check_metadata=True)
                    and parquet.metadata.num_rows == ref["row_count"],
                    "Inventory Parquet schema/count differs.",
                )
                for batch in parquet.iter_batches(batch_size=CHUNK_ROWS, use_threads=False):
                    require(
                        batch.nbytes <= 64 * 1024 * 1024, "Inventory Parquet batch exceeds budget."
                    )
                    rows.extend(batch.to_pylist())
            computed = logical(name, rows, schema, grain(name), data_class(name), work)
            require(
                computed == {k: table[k] for k in computed},
                "Typed inventory content/ranges differ.",
            )
            source_rows = [source_row(r, native=name in TABLES) for r in rows]
            require(
                len({tuple(r[k] for k in grain(name)) for r in source_rows}) == len(source_rows),
                "Duplicate inventory snapshot grain.",
            )
            source_rows.sort(key=lambda r: tuple(r[k] for k in grain(name)))
            require(
                table_identity(name, source_rows) == parent["descriptor"]["tables"][name],
                "Inventory source projection content differs.",
            )
            restored[name] = source_rows
            logical_tables.append(computed)
        require(logical_tables == desc["tables"], "Snapshot descriptor table projection differs.")
        context = TableContext.model_validate(parent["descriptor"]["context"])
        operational = operational_from_tables(restored, context)
        reconcile_simulation(operational)
        ledger = InventoryLedger.from_payload(operational["ledger"])
        expected = sorted(
            daily_snapshots(ledger, context.projection),
            key=lambda r: tuple(r[k] for k in grain("inventory_daily_snapshots")),
        )
        require(
            restored["inventory_daily_snapshots"] == expected,
            "Known inventory snapshots differ from ledger.",
        )
        if desc["include_evaluation_truth"]:
            reconcile_tables({n: restored[n] for n in TABLES}, context)
            qualification_root = root / "evaluation_truth/qualification"
            qmanifest = load_json(qualification_root / QUAL_MANIFEST)
            require(
                qmanifest["qualification_id"] == desc["parent_qualification_id"]
                and qmanifest["descriptor"] == qdesc,
                "Evaluation qualification parent differs.",
            )
            rows = qualify_windows(restored, context)
            require(
                (qualification_root / QUAL_WINDOWS).read_bytes() == canonical_json(rows) + b"\n",
                "Evaluation labels differ from physical/lifecycle/coverage qualification.",
            )
            require(
                (qualification_root / QUAL_REPORT).read_bytes()
                == canonical_json(qualification_report(rows, parent)) + b"\n",
                "Evaluation qualification report differs.",
            )
    return manifest


def export_inventory_snapshot(
    source: Path,
    dataset_id: str,
    qualification: Path,
    output_root: Path,
    *,
    include_truth: bool = False,
    chunk_rows: int = CHUNK_ROWS,
    required_use_cases: tuple[str, ...] = ("forecast_source", "inventory_source"),
) -> dict:
    root = generated_target(output_root)
    require(
        1 <= chunk_rows <= MAX_CHUNK_ROWS
        and bool(required_use_cases)
        and set(required_use_cases) <= USE_CASES,
        "Invalid inventory export options.",
    )
    require(
        dataset_id.startswith("source-sha256-")
        and len(dataset_id) == 78
        and all(c in "0123456789abcdef" for c in dataset_id[14:]),
        "Invalid explicit source ID.",
    )
    destination = generated_target(root / dataset_id)
    require(
        not source.absolute().is_relative_to(root)
        and not qualification.absolute().is_relative_to(root),
        "Inputs must be separate from snapshot storage.",
    )
    staging = generated_target(root / ".staging")
    staging.mkdir(parents=True, mode=0o700, exist_ok=True)
    with TemporaryDirectory(prefix="inventory-export-", dir=staging) as temporary:
        work = Path(temporary)
        tables, parent = seal_source(source, work / "source", dataset_id)
        _, _, qmanifest = seal_qualification(qualification, work / "qualification", tables, parent)
        bundle = work / "bundle"
        bundle.mkdir(mode=0o700)
        for name in REPORT_NAMES:
            copy_file(work / "source" / name, bundle / "reports" / name)
        copy_file(work / "source" / MANIFEST_FILENAME, bundle / "manifests" / MANIFEST_FILENAME)
        for name in SCHEMAS:
            copy_file(export_schema_file(name, parent), bundle / "schemas" / name)
        (bundle / "schemas/source_snapshot_handoff.v1_1.json").write_bytes(
            canonical_json(handoff_contract()) + b"\n"
        )
        if include_truth:
            for name in (QUAL_MANIFEST, QUAL_REPORT, QUAL_WINDOWS):
                copy_file(
                    work / "qualification" / name, bundle / "evaluation_truth/qualification" / name
                )
        selected = (*FACT_TABLES, *(TRUTH_TABLES if include_truth else ()))
        artifacts = []
        for name in selected:
            schema = table_schema(name)
            convert = typed_row if name in TABLES else commerce_typed
            rows = [convert(r, schema) for r in tables[name]]
            table = logical(name, rows, schema, grain(name), data_class(name), work)
            namespace = "evaluation_truth" if data_class(name) == "simulation_truth" else "facts"
            directory = bundle / namespace / name
            directory.mkdir(parents=True, mode=0o700)
            files = []
            for index, offset in enumerate(range(0, max(len(rows), 1), chunk_rows)):
                chunk = rows[offset : offset + chunk_rows]
                path = directory / f"part-{index:06d}.parquet"
                pq.write_table(
                    pa.Table.from_pylist(chunk, schema=schema),
                    path,
                    compression="zstd",
                    row_group_size=chunk_rows,
                    write_page_checksum=True,
                )
                path.chmod(0o600)
                files.append({**reference(bundle, path), "row_count": len(chunk)})
            artifacts.append({**table, "partition_source_field": None, "files": files})
            (bundle / "schemas" / (name + ".arrow.json")).write_bytes(
                canonical_json({"table": name, "schema": columns(name)}) + b"\n"
            )
        metadata = [
            reference(bundle, p)
            for p in sorted(bundle.rglob("*"))
            if p.is_file() and not p.name.endswith(".parquet")
        ]
        provenance = exporter_provenance()
        descriptor = {
            "role": "source_snapshot",
            "identity_version": "1.1.0",
            "policy_version": POLICY,
            "format_version": FORMAT,
            "parent_source_dataset_id": dataset_id,
            "parent_qualification_id": qmanifest["qualification_id"],
            "qualification": qmanifest["descriptor"],
            "required_use_cases": sorted(set(required_use_cases)),
            "include_evaluation_truth": include_truth,
            "exporter_code_sha256": json_sha256(provenance["code_files"]),
            "dependency_sha256": provenance["dependency_sha256"],
            "source_qualification_sha256": parent["reports"]["source_report.json"]["sha256"],
            "schemas": {
                r["path"]: r["sha256"] for r in metadata if r["path"].startswith("schemas/")
            },
            "tables": [
                {
                    k: t[k]
                    for k in (
                        "table",
                        "data_class",
                        "row_count",
                        "content_sha256",
                        "grain",
                        "date_range",
                        "field_ranges",
                        "schema",
                    )
                }
                for t in artifacts
            ],
        }
        payload = {
            "schema_version": "1.1.0",
            "snapshot_id": "snapshot-sha256-" + json_sha256(descriptor),
            "source_dataset_id": dataset_id,
            "source_repository": "retailops-cloud-native-platform",
            "generated_at": datetime.now(UTC).isoformat(),
            "snapshot_ready": True,
            "descriptor": descriptor,
            "source": parent,
            "exporter": provenance,
            "tables": artifacts,
            "metadata_files": metadata,
        }
        (bundle / MANIFEST_NAME).write_bytes(canonical_json(payload) + b"\n")
        (bundle / "manifest.sha256").write_text(file_sha256(bundle / MANIFEST_NAME) + "\n")
        for path in bundle.rglob("*"):
            path.chmod(0o700 if path.is_dir() else 0o600)
        verified = verify_inventory_snapshot(
            bundle, allow_evaluation_truth=include_truth, scratch=work
        )
        with publication_lock(root, dataset_id):
            if destination.exists():
                previous = verify_inventory_snapshot(
                    destination, allow_evaluation_truth=include_truth, scratch=work
                )
                require(
                    previous["descriptor"] == descriptor,
                    "Immutable inventory snapshot variant conflict.",
                )
                return {"publication": "reused", "path": str(destination), "manifest": previous}
            sync_bundle(bundle)
            publish_directory(bundle, destination)
            return {"publication": "published", "path": str(destination), "manifest": verified}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--qualification-dir", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--include-evaluation-truth", action="store_true")
    args = parser.parse_args()
    result = export_inventory_snapshot(
        args.source_dir,
        args.dataset_id,
        args.qualification_dir,
        args.output_root,
        include_truth=args.include_evaluation_truth,
    )
    print(json.dumps({k: result[k] for k in ("publication", "path")}))  # noqa: T201 - CLI publication receipt


if __name__ == "__main__":
    main()
