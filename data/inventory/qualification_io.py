"""Immutable private qualification sidecar; recheck source and every derived label."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from data.generator.identity import (
    canonical_file_matches,
    canonical_json,
    canonical_json_chunks,
    code_provenance,
    json_sha256,
)
from data.inventory.contract import require
from data.inventory.qualification import qualification_report, qualify_windows
from data.inventory.qualification_contract import (
    GRAIN,
    MANIFEST,
    QUALIFICATION_POLICY,
    QUALIFICATION_VERSION,
    REPORT,
    WINDOWS,
    QualificationManifest,
    qualification_schema,
)
from data.inventory.source_dataset_io import (
    MAX_METADATA_BYTES,
    artifact,
    fingerprint,
    load_json,
    read_source_dataset,
    safe_file,
    verify_artifact,
)
from data.inventory.source_tables import TableContext


def build_qualification(source: Path) -> tuple[list[dict], dict, dict]:
    tables, parent = read_source_dataset(source)
    context = TableContext.model_validate(parent["descriptor"]["context"])
    rows = qualify_windows(tables, context)
    return rows, qualification_report(rows, parent), parent


def descriptor(rows: list[dict], report: dict, parent: dict, provenance: dict) -> dict:
    return {
        "role": "inventory_label_qualification",
        "schema_version": QUALIFICATION_VERSION,
        "policy_version": QUALIFICATION_POLICY,
        "data_class": "simulation_truth",
        "parent_source_id": parent["dataset_id"],
        "evaluated_at": parent["descriptor"]["context"]["evaluated_at"],
        "horizon_days": 7,
        "grain": list(GRAIN),
        "qualification_schema_sha256": json_sha256(qualification_schema()),
        "rows": len(rows),
        "windows_sha256": json_sha256(rows),
        "report_sha256": json_sha256(report),
        **{k: provenance[k] for k in ("code_sha256", "dependency_sha256", "python_version")},
    }


def read_qualification(directory: Path, source: Path) -> tuple[list[dict], dict, dict]:
    tables, parent = read_source_dataset(source)
    return read_sealed_qualification(directory, tables, parent)


def read_sealed_qualification(
    directory: Path, tables: dict, parent: dict
) -> tuple[list[dict], dict, dict]:
    """Requalify an immutable, private source already fully verified by its caller.

    Export seals source files and calls read_source_dataset on that copy first.
    Reuse those verified in-memory tables instead of reading/rechecking all 58
    source files again. The public path-based reader still verifies its source.
    """
    require(
        not directory.is_symlink() and not any(p.is_symlink() for p in directory.rglob("*")),
        "Symlink in inventory qualification.",
    )
    payload = load_json(safe_file(directory, MANIFEST, limit=MAX_METADATA_BYTES))
    manifest = QualificationManifest.model_validate(payload).model_dump()
    require(manifest == payload, "Noncanonical qualification manifest.")
    desc, provenance = manifest["descriptor"], manifest["provenance"]
    require(
        manifest["qualification_id"] == "inventory-labels-sha256-" + json_sha256(desc),
        "Qualification identity differs.",
    )
    for kind in ("code", "dependency"):
        require(
            json_sha256(provenance[kind + "_files"])
            == provenance[kind + "_sha256"]
            == desc[kind + "_sha256"],
            "Qualification provenance differs.",
        )
    require(provenance["python_version"] == desc["python_version"], "Qualification Python differs.")
    context = TableContext.model_validate(parent["descriptor"]["context"])
    rows = qualify_windows(tables, context)
    report = qualification_report(rows, parent)
    require(
        desc == descriptor(rows, report, parent, provenance),
        "Qualification differs from verified parent facts.",
    )
    for field, path, expected in (("windows", WINDOWS, rows), ("report", REPORT, report)):
        target = verify_artifact(directory, manifest[field], path)
        # Exact canonical bytes reject malformed types, duplicate keys and changed ordering too.
        require(
            canonical_file_matches(target, expected),
            "Qualification artifact differs from recomputation.",
        )
    require(
        {p.relative_to(directory).as_posix() for p in directory.rglob("*") if p.is_file()}
        == {MANIFEST, WINDOWS, REPORT},
        "Unallowlisted qualification file.",
    )
    return rows, report, manifest


def write_qualification(source: Path, output_root: Path) -> Path:
    rows, report, parent = build_qualification(source)
    provenance = code_provenance(fingerprint())
    desc = descriptor(rows, report, parent, provenance)
    identifier = "inventory-labels-sha256-" + json_sha256(desc)
    output_root.mkdir(parents=True, exist_ok=True)
    final = output_root / identifier
    if final.exists():
        read_qualification(final, source)
        return final
    with TemporaryDirectory(prefix=".inventory-labels-", dir=output_root) as temporary:
        staging = Path(temporary) / "qualification"
        (staging / "simulation_truth").mkdir(parents=True)
        with (staging / WINDOWS).open("xb") as stream:
            for chunk in canonical_json_chunks(rows):
                stream.write(chunk)
            stream.write(b"\n")
        (staging / REPORT).write_bytes(canonical_json(report) + b"\n")
        payload = {
            "schema_version": QUALIFICATION_VERSION,
            "qualification_id": identifier,
            "descriptor": desc,
            "provenance": provenance,
            "windows": artifact(staging / WINDOWS, staging),
            "report": artifact(staging / REPORT, staging),
            "source_ready": False,
            "inventory_ready": False,
            "model_ready": False,
        }
        (staging / MANIFEST).write_bytes(canonical_json(payload) + b"\n")
        read_qualification(staging, source)
        staging.rename(final)
    return final
