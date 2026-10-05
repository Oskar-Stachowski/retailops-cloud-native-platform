"""Seal a separately versioned declaration and verify it by native reconstruction."""

from __future__ import annotations

import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory

from data.day_coverage.contract import MAX_BYTES, POLICY, TABLES, VERSION, Descriptor, Manifest
from data.day_coverage.projection import days
from data.dq.source import load_source
from data.generator.identity import ROOT, canonical_json, code_fingerprint, json_sha256
from data.inventory.contract import require
from data.inventory.source_dataset_io import load_json, safe_file

FILES = {"days.jsonl", "coverage_manifest.json", "manifest.sha256"}


def material(source_directory: Path) -> tuple[Manifest, bytes]:
    tables, source = load_source(source_directory)
    rows = days({name: tables[name] for name in TABLES}, source)
    payload = b"".join(canonical_json(row) + b"\n" for row in rows)
    require(len(payload) <= MAX_BYTES, "Day coverage exceeds byte budget.")
    paths = tuple(
        str(p.relative_to(ROOT))
        for p in sorted((ROOT / "data/day_coverage").rglob("*"))
        if p.is_file() and p.suffix in {".py", ".json"}
    )
    fp = code_fingerprint((*paths, "data/dq/source.py", "data/inventory/source_dataset_io.py"))
    descriptor = Descriptor(
        contract_version=VERSION,
        policy_version=POLICY,
        owner="retailops-cloud-native-platform",
        source_dataset_id=source["dataset_id"],
        source_descriptor_sha256=json_sha256(source["descriptor"]),
        source_tables={name: source["descriptor"]["tables"][name] for name in TABLES},
        return_scope="purchases_in_parent_source_only",
        return_closure_basis="verified_complete_synthetic_export_and_bounded_native_ingestion",
        missing_grain_policy="unknown_not_zero",
        cohort_maturity_is_day_closure=False,
        transport_durability_proven=False,
        **{k: fp[k] for k in ("code_sha256", "dependency_sha256", "python_version")},
        rows_sha256=hashlib.sha256(payload).hexdigest(),
        row_count=len(rows),
    )
    return Manifest(
        coverage_id="day-coverage-sha256-" + json_sha256(descriptor.model_dump()),
        descriptor=descriptor,
    ), payload


def verify(directory: Path, source_directory: Path) -> Manifest:
    require(
        not any(p.is_symlink() for p in (directory, *directory.parents)), "Symlink coverage root."
    )
    paths = list(directory.rglob("*"))
    require(
        not any(p.is_symlink() or (p.is_file() and p.stat().st_nlink != 1) for p in paths),
        "Unsafe coverage file.",
    )
    require(
        {p.relative_to(directory).as_posix() for p in paths} == FILES, "Coverage inventory differs."
    )
    raw = safe_file(directory, "coverage_manifest.json", limit=1024**2).read_bytes()
    parsed = Manifest.model_validate(load_json(directory / "coverage_manifest.json"))
    expected, rows = material(source_directory)
    require(
        parsed == expected and raw == canonical_json(expected.model_dump()) + b"\n",
        "Coverage identity or native semantics differ.",
    )
    require(
        safe_file(directory, "days.jsonl", limit=MAX_BYTES).read_bytes() == rows,
        "Coverage days differ from native source.",
    )
    require(
        safe_file(directory, "manifest.sha256", limit=128).read_bytes()
        == (hashlib.sha256(raw).hexdigest() + "\n").encode(),
        "Coverage seal differs.",
    )
    return parsed


def build(source_directory: Path, output_root: Path) -> dict:
    root = output_root.absolute()
    require(not any(p.is_symlink() for p in (root, *root.parents)), "Symlink coverage output root.")
    require(
        not root.is_relative_to(source_directory.absolute())
        and not source_directory.absolute().is_relative_to(root),
        "Separate coverage output required.",
    )
    manifest, rows = material(source_directory)
    root.mkdir(parents=True, exist_ok=True)
    destination = root / manifest.coverage_id
    if destination.exists():
        require(verify(destination, source_directory) == manifest, "Immutable coverage conflict.")
        return {
            "directory": str(destination),
            "coverage_id": manifest.coverage_id,
            "status": "reused",
        }
    with TemporaryDirectory(prefix=".coverage-", dir=root) as tmp:
        stage = Path(tmp) / "payload"
        stage.mkdir()
        document = canonical_json(manifest.model_dump()) + b"\n"
        (stage / "days.jsonl").write_bytes(rows)
        (stage / "coverage_manifest.json").write_bytes(document)
        (stage / "manifest.sha256").write_bytes(
            (hashlib.sha256(document).hexdigest() + "\n").encode()
        )
        verify(stage, source_directory)
        stage.rename(destination)
    return {"directory": str(destination), "coverage_id": manifest.coverage_id, "status": "created"}
