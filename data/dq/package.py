"""Immutable offline fixture, independently rebuilt against a verified source parent."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from data.dq.contract import GENERATOR_VERSION, PLAN_VERSION, REPLAY_VERSION, FaultPlan
from data.dq.scenarios import capture, evaluate
from data.dq.source import load_source, sales_events, source_binding
from data.generator.identity import (
    ROOT,
    canonical_json,
    code_fingerprint,
    code_provenance,
    json_sha256,
)
from data.generator.manifest_v2 import Provenance
from data.inventory.contract import require
from data.inventory.source_dataset_io import artifact, load_json, safe_file

PACKAGE_VERSION = "raw-dq-fixture-1.0.0"
MANIFEST = "dq_manifest.json"
PATHS = (
    "raw/events.jsonl",
    "curated/replay.json",
    "source_binding.json",
    "simulation_truth/fault_plan.json",
    "simulation_truth/data_quality_injections.json",
    "simulation_truth/evaluation.json",
)
MAX_ARTIFACT_BYTES = 8 * 1024 * 1024


def fingerprint() -> dict:
    extras = tuple(
        str(p.relative_to(ROOT))
        for directory, pattern in (
            (ROOT / "data/dq", "*.py"),
            (ROOT / "data/inventory", "*.py"),
            (ROOT / "data/contracts", "*.schema.json"),
        )
        for p in sorted(directory.glob(pattern))
    )
    return code_fingerprint(
        (
            *extras,
            "data/export/schema.py",
            "services/api/app/services/realtime_contract.py",
            "services/api/app/contracts/retailops-realtime-events.v1.contract.json",
            "services/api/app/contracts/realtime-events.v1.schema.json",
        )
    )


def contents(tables: dict, source: dict, plan: FaultPlan) -> dict[str, bytes]:
    events = sales_events(tables, source, plan.event_limit)
    records, truth = capture(events, plan, source["dataset_id"])
    replay, evaluation = evaluate(events, records, truth)
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


def descriptor(source_id: str, plan: FaultPlan, artifacts: dict, provenance: dict) -> dict:
    return {
        "schema_version": PACKAGE_VERSION,
        "generator_version": GENERATOR_VERSION,
        "plan_version": PLAN_VERSION,
        "replay_version": REPLAY_VERSION,
        "source_dataset_id": source_id,
        "plan_sha256": json_sha256(plan.model_dump()),
        "artifacts": artifacts,
        **{key: provenance[key] for key in ("code_sha256", "dependency_sha256", "python_version")},
        "scope": "offline_selected_sales_only",
        "raw_faults_only": True,
        "curated_completeness": "not_qualified",
        "transport_durability_proven": False,
        "ai03_handoff_ready": False,
        "model_ready": False,
    }


def read_fixture(directory: Path, source_directory: Path) -> dict:
    require(not directory.is_symlink(), "Symlink fixture root.")
    paths = list(directory.rglob("*"))
    require(not any(p.is_symlink() for p in paths), "Symlink in fixture.")
    require(
        {p.relative_to(directory).as_posix() for p in paths if p.is_file()} == {*PATHS, MANIFEST},
        "Fixture file allowlist differs.",
    )
    manifest = load_json(safe_file(directory, MANIFEST, limit=1024 * 1024))
    require(
        set(manifest) == {"fixture_id", "descriptor", "provenance"},
        "Fixture manifest fields differ.",
    )
    require(
        (directory / MANIFEST).read_bytes() == canonical_json(manifest) + b"\n",
        "Noncanonical fixture manifest.",
    )
    tables, source = load_source(source_directory)
    plan = FaultPlan.from_payload(
        load_json(safe_file(directory, "simulation_truth/fault_plan.json"))
    )
    expected = contents(tables, source, plan)
    actual = {}
    for name in PATHS:
        path = safe_file(directory, name, limit=MAX_ARTIFACT_BYTES)
        require(
            path.read_bytes() == expected[name],
            "Fixture differs from independent source/plan replay: " + name,
        )
        actual[name] = artifact(path, directory)
    provenance = manifest["provenance"]
    require(
        Provenance.model_validate(provenance).model_dump() == provenance, "Invalid DQ provenance."
    )
    current = fingerprint()
    require(
        set(provenance) == {*current, "git_commit", "code_state"}, "DQ provenance fields differ."
    )
    require(
        {k: provenance[k] for k in current} == current, "DQ implementation/dependencies differ."
    )
    desc = descriptor(source["dataset_id"], plan, actual, provenance)
    require(
        canonical_json(manifest["descriptor"]) == canonical_json(desc), "DQ descriptor differs."
    )
    require(
        manifest["fixture_id"] == "raw-dq-sha256-" + json_sha256(desc),
        "DQ fixture identity differs.",
    )
    return manifest


def write_fixture(source_directory: Path, plan: FaultPlan, output_root: Path) -> Path:
    require(
        not output_root.resolve().is_relative_to(source_directory.resolve()),
        "DQ output must be outside the source dataset.",
    )
    plan = FaultPlan.from_payload(plan.model_dump())
    tables, source = load_source(source_directory)
    values = contents(tables, source, plan)
    provenance = code_provenance(fingerprint())
    output_root.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".raw-dq-", dir=output_root) as temporary:
        staging = Path(temporary) / "fixture"
        staging.mkdir()
        for name, value in values.items():
            require(len(value) <= MAX_ARTIFACT_BYTES, "DQ artifact exceeds budget.")
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
            prior = read_fixture(final, source_directory)
            require(prior["fixture_id"] == identifier, "Existing immutable fixture differs.")
        else:
            staging.rename(final)
    return final


def receipt(directory: Path, manifest: dict) -> dict:
    replay = json.loads((directory / "curated/replay.json").read_text(encoding="utf-8"))
    evaluation = json.loads(
        (directory / "simulation_truth/evaluation.json").read_text(encoding="utf-8")
    )
    return {
        "status": "passed",
        "fixture_id": manifest["fixture_id"],
        "directory": str(directory),
        "source_dataset_id": manifest["descriptor"]["source_dataset_id"],
        "report": replay["report"],
        "checks": evaluation["checks"],
        "injections": [
            {
                k: r[k]
                for k in (
                    "issue_type",
                    "expected_action",
                    "observed_action",
                    "observed_reason",
                    "passed",
                )
            }
            for r in evaluation["injections"]
        ],
        "fault_prevalence": evaluation["fault_prevalence"],
        "provenance": manifest["provenance"],
        "ai03_handoff_ready": False,
        "model_ready": False,
    }
