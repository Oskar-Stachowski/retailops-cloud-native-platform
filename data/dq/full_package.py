"""Immutable v2 fixture with source-bound full replay and private evaluation."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from data.dq.full_contract import (
    GENERATOR_VERSION,
    MAX_ARTIFACT_BYTES,
    REPLAY_VERSION,
    SCOPE,
    FullFaultPlan,
    parse_full_plan,
)
from data.dq.full_scenarios import capture, evaluate
from data.dq.full_source import full_events, source_binding
from data.dq.package import MANIFEST, PATHS, fingerprint
from data.dq.source import load_source
from data.generator.identity import canonical_json, code_provenance, json_sha256
from data.generator.manifest_v2 import Provenance
from data.inventory.contract import require
from data.inventory.source_dataset_io import artifact, load_json, safe_file

PACKAGE_VERSION = "raw-dq-fixture-2.0.0"


def contents(tables: dict, source: dict, plan: FullFaultPlan) -> dict[str, bytes]:
    events = full_events(tables, source)
    records, truth = capture(events, plan, source["dataset_id"])
    replay, evaluation = evaluate(tables, source, events, records, truth)
    values = {
        "curated/replay.json": replay,
        "source_binding.json": source_binding(source, events),
        "simulation_truth/fault_plan.json": plan.model_dump(),
        "simulation_truth/data_quality_injections.json": truth,
        "simulation_truth/evaluation.json": evaluation,
    }
    return {
        "raw/events.jsonl": b"".join(canonical_json(r) + b"\n" for r in records),
        **{name: canonical_json(value) + b"\n" for name, value in values.items()},
    }


def descriptor(source_id: str, plan: FullFaultPlan, artifacts: dict, provenance: dict) -> dict:
    return {
        "schema_version": PACKAGE_VERSION,
        "generator_version": GENERATOR_VERSION,
        "plan_version": plan.contract_version,
        "replay_version": REPLAY_VERSION,
        "source_dataset_id": source_id,
        "plan_sha256": json_sha256(plan.model_dump()),
        "artifacts": artifacts,
        **{k: provenance[k] for k in ("code_sha256", "dependency_sha256", "python_version")},
        "scope": SCOPE,
        "raw_faults_only": True,
        "curated_completeness": "not_qualified",
        "missing_grain_policy": "unknown_not_zero",
        "transport_durability_proven": False,
        "ai03_handoff_ready": False,
        "model_ready": False,
    }


def read_fixture(directory: Path, source_directory: Path) -> dict:
    require(not directory.is_symlink(), "Symlink fixture root.")
    paths = list(directory.rglob("*"))
    require(not any(p.is_symlink() for p in paths), "Symlink in full fixture.")
    require(
        {p.relative_to(directory).as_posix() for p in paths if p.is_file()} == {*PATHS, MANIFEST},
        "Full fixture file allowlist differs.",
    )
    manifest = load_json(safe_file(directory, MANIFEST, limit=1024 * 1024))
    require(
        set(manifest) == {"fixture_id", "descriptor", "provenance"}, "Full manifest fields differ."
    )
    require(
        (directory / MANIFEST).read_bytes() == canonical_json(manifest) + b"\n",
        "Noncanonical full manifest.",
    )
    tables, source = load_source(source_directory)
    plan = parse_full_plan(
        load_json(safe_file(directory, "simulation_truth/fault_plan.json", limit=1024 * 1024))
    )
    expected = contents(tables, source, plan)
    actual = {}
    for name in PATHS:
        path = safe_file(directory, name, limit=MAX_ARTIFACT_BYTES)
        require(
            path.read_bytes() == expected[name],
            "Full fixture differs from independent source/plan replay: " + name,
        )
        actual[name] = artifact(path, directory)
    provenance = manifest["provenance"]
    require(
        Provenance.model_validate(provenance).model_dump() == provenance,
        "Invalid full DQ provenance.",
    )
    current = fingerprint()
    require(
        set(provenance) == {*current, "git_commit", "code_state"}, "Full provenance fields differ."
    )
    require(
        {k: provenance[k] for k in current} == current,
        "Full DQ implementation/dependencies differ.",
    )
    desc = descriptor(source["dataset_id"], plan, actual, provenance)
    require(
        canonical_json(manifest["descriptor"]) == canonical_json(desc),
        "Full DQ descriptor differs.",
    )
    require(
        manifest["fixture_id"] == "raw-dq-sha256-" + json_sha256(desc),
        "Full fixture identity differs.",
    )
    return manifest


def write_fixture(source_directory: Path, plan: FullFaultPlan, output_root: Path) -> Path:
    require(
        not output_root.resolve().is_relative_to(source_directory.resolve()),
        "Full DQ output must be outside source.",
    )
    plan = parse_full_plan(plan.model_dump())
    tables, source = load_source(source_directory)
    values = contents(tables, source, plan)
    provenance = code_provenance(fingerprint())
    output_root.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".full-dq-", dir=output_root) as temporary:
        staging = Path(temporary) / "fixture"
        staging.mkdir()
        for name, value in values.items():
            require(len(value) <= MAX_ARTIFACT_BYTES, "Full DQ artifact exceeds budget.")
            path = staging / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(value)
        desc = descriptor(
            source["dataset_id"],
            plan,
            {n: artifact(staging / n, staging) for n in PATHS},
            provenance,
        )
        identifier = "raw-dq-sha256-" + json_sha256(desc)
        manifest = {"fixture_id": identifier, "descriptor": desc, "provenance": provenance}
        (staging / MANIFEST).write_bytes(canonical_json(manifest) + b"\n")
        read_fixture(staging, source_directory)
        final = output_root / identifier
        if final.exists():
            require(
                read_fixture(final, source_directory)["fixture_id"] == identifier,
                "Existing full fixture differs.",
            )
        else:
            staging.rename(final)
    return final
