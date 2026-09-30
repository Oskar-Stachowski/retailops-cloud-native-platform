"""Immutable local scenario candidates, deliberately separate from AI03 source exports."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal

from data.anomalies.contract import AnomalyPlan, plan_schema
from data.anomalies.scenarios import build_scenario
from data.generator.configuration import resolve_generation_config
from data.generator.identity import canonical_json, code_fingerprint, code_provenance, json_sha256
from data.generator.manifest_v2 import config_from_parameters, unique_keys
from data.inventory.contract import require
from data.inventory.replenishment_contract import SupplyRecord
from data.inventory.source_contract import SourceInventoryConfig
from data.inventory.source_dataset_contract import Artifact  # noqa: TC001 - Pydantic schema
from data.inventory.source_dataset_io import artifact, verify_artifact

VERSION = "anomaly-scenario-candidate-1.0.0"
MANIFEST = "scenario_manifest.json"
PATHS = (
    "facts/commerce.json",
    "facts/inventory.json",
    "simulation_truth/anomaly_injections.json",
    "simulation_truth/process.json",
)
MAX_ARTIFACT_BYTES = 64 * 1024 * 1024


class CandidateManifest(SupplyRecord):
    schema_version: Literal["anomaly-scenario-candidate-1.0.0"]
    candidate_id: str
    descriptor: dict
    requested_generation: dict
    artifacts: dict[str, Artifact]
    provenance: dict
    source_ready: Literal[False]
    anomaly_ready: Literal[False]
    model_ready: Literal[False]
    publication_status: Literal["candidate_only_awaiting_versioned_ai03_handoff"]


def fingerprint() -> dict:
    root = Path(__file__).resolve().parents[2]
    extra = tuple(
        str(p.relative_to(root))
        for directory, pattern in (
            (root / "data/anomalies", "*.py"),
            (root / "data/inventory", "*.py"),
            (root / "data/contracts", "*.schema.json"),
        )
        for p in sorted(directory.glob(pattern))
    )
    return code_fingerprint(extra)


def documents(candidate: dict) -> dict[str, dict]:
    return {
        PATHS[0]: candidate["commerce"],
        PATHS[1]: candidate["inventory"],
        PATHS[2]: {
            "data_class": "simulation_truth",
            "plan": candidate["plan"],
            **candidate["effects"],
        },
        PATHS[3]: {
            "data_class": "simulation_truth",
            "inventory_configuration": candidate["inventory_configuration"],
            "normal_candidate_sha256": candidate["normal_candidate_sha256"],
            "normal_commerce_sha256": candidate["normal_commerce_sha256"],
            "reconciliation": candidate["reconciliation"],
            "facts_status": candidate["facts_status"],
            **candidate["simulation_truth"],
        },
    }


def read_candidate(directory: Path, *, replay: bool = True) -> dict:
    require(
        not directory.is_symlink() and not any(p.is_symlink() for p in directory.rglob("*")),
        "Symlink in anomaly candidate.",
    )
    manifest_path = directory / MANIFEST
    require(
        manifest_path.is_file() and manifest_path.stat().st_size <= 1024 * 1024,
        "Invalid candidate manifest.",
    )
    payload = json.loads(manifest_path.read_text(), object_pairs_hook=unique_keys)
    manifest = CandidateManifest.model_validate(payload).model_dump()
    require(manifest == payload, "Noncanonical candidate manifest.")
    desc = manifest["descriptor"]
    require(
        set(desc)
        == {
            "schema_version",
            "generation",
            "plan_sha256",
            "plan_schema_sha256",
            "code_sha256",
            "dependency_sha256",
            "python_version",
            "artifacts",
        },
        "Candidate descriptor allowlist differs.",
    )
    require(
        manifest["candidate_id"] == "anomaly-candidate-sha256-" + json_sha256(desc)
        and desc["schema_version"] == VERSION
        and desc["plan_schema_sha256"] == json_sha256(plan_schema()),
        "Candidate identity or schema differs.",
    )
    require(set(manifest["artifacts"]) == set(PATHS), "Candidate artifact allowlist differs.")
    require(desc["artifacts"] == manifest["artifacts"], "Candidate descriptor artifacts differ.")
    require(
        {p.relative_to(directory).as_posix() for p in directory.rglob("*") if p.is_file()}
        == {MANIFEST, *PATHS},
        "Unallowlisted candidate file.",
    )
    restored = {}
    for relative in PATHS:
        declared = manifest["artifacts"][relative]
        require(declared == desc["artifacts"][relative], "Artifact identity binding differs.")
        path = verify_artifact(directory, declared, relative, limit=MAX_ARTIFACT_BYTES)
        restored[relative] = json.loads(path.read_text(), object_pairs_hook=unique_keys)
        require(
            path.read_bytes() == canonical_json(restored[relative]) + b"\n",
            "Noncanonical candidate artifact.",
        )
    plan = AnomalyPlan.from_payload(restored[PATHS[2]]["plan"])
    require(
        json_sha256(plan.model_dump()) == desc["plan_sha256"], "Injection plan identity differs."
    )
    generation = config_from_parameters(manifest["requested_generation"])
    require(
        resolve_generation_config(generation).parameters() == desc["generation"],
        "Requested/resolved candidate generation differs.",
    )
    provenance = manifest["provenance"]
    for kind in ("code", "dependency"):
        require(
            json_sha256(provenance[kind + "_files"])
            == provenance[kind + "_sha256"]
            == desc[kind + "_sha256"],
            "Candidate provenance differs.",
        )
    require(
        provenance["python_version"] == desc["python_version"],
        "Candidate Python provenance differs.",
    )
    if replay:
        current = fingerprint()
        require(
            all(
                current[k] == desc[k]
                for k in ("code_sha256", "dependency_sha256", "python_version")
            ),
            "Independent candidate replay requires the recorded generator environment.",
        )
        expected = documents(
            build_scenario(
                generation,
                plan.model_dump(),
                SourceInventoryConfig.from_payload(restored[PATHS[3]]["inventory_configuration"]),
            )
        )
        require(
            restored == expected, "Candidate facts/truth disagree with independent process replay."
        )
    return manifest


def write_candidate(candidate: dict, output_root: Path) -> Path:
    values = documents(candidate)
    encoded = {name: canonical_json(value) + b"\n" for name, value in values.items()}
    require(
        all(len(v) <= MAX_ARTIFACT_BYTES for v in encoded.values()),
        "Candidate exceeds artifact budget.",
    )
    require(not output_root.is_symlink(), "Candidate root cannot be a symlink.")
    output_root.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".anomaly-candidate-", dir=output_root) as tmp:
        staging = Path(tmp) / "candidate"
        for name, value in encoded.items():
            target = staging / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(value)
        artifacts = {name: artifact(staging / name, staging) for name in PATHS}
        provenance = code_provenance(fingerprint())
        desc = {
            "schema_version": VERSION,
            "generation": candidate["generation"],
            "plan_sha256": json_sha256(candidate["plan"]),
            "plan_schema_sha256": json_sha256(plan_schema()),
            **{k: provenance[k] for k in ("code_sha256", "dependency_sha256", "python_version")},
            "artifacts": artifacts,
        }
        payload = {
            "schema_version": VERSION,
            "candidate_id": "anomaly-candidate-sha256-" + json_sha256(desc),
            "descriptor": desc,
            "requested_generation": candidate["requested_generation"],
            "artifacts": artifacts,
            "provenance": provenance,
            **{
                k: candidate[k]
                for k in ("source_ready", "anomaly_ready", "model_ready", "publication_status")
            },
        }
        (staging / MANIFEST).write_bytes(canonical_json(payload) + b"\n")
        # A valid, replayed candidate is the only object allowed to be published.
        read_candidate(staging)
        destination = output_root / payload["candidate_id"]
        if destination.exists():
            require(
                read_candidate(destination)["descriptor"] == desc,
                "Conflicting immutable candidate.",
            )
        else:
            staging.rename(destination)
        return destination
