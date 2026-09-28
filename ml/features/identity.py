from __future__ import annotations

import argparse
import csv
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import Field

from data.generator.configuration import (
    DatasetGenerationConfig,
    requested_parameters,
    resolve_generation_config,
)
from data.generator.demand_schema import uses_demand
from data.generator.identity import (
    code_fingerprint,
    code_provenance,
    content_sha256,
    file_sha256,
    json_sha256,
    source_identity,
)
from data.generator.manifest_v2 import (
    SHA256,
    Contract,
    Count,
    Provenance,
    RequestedParameters,
    SourceDescriptor,
    config_from_parameters,
    unique_keys,
)
from ml.features.ai_demand import AI_FEATURE_COLUMNS, AI_FEATURE_SCHEMA_PATH, validate_ai_records

IDENTITY_FILENAME = "feature_identity_manifest.json"
SCHEMA_PATH = "ml/contracts/demand_forecast_features.schema.json"
IDENTITY_SCHEMA_PATH = "ml/contracts/feature_identity_manifest.schema.json"
FEATURE_CODE = (
    "ml/features/demand_forecast.py",
    "ml/features/identity.py",
    SCHEMA_PATH,
    IDENTITY_SCHEMA_PATH,
    "ml/features/ai_demand.py",
    "ml/features/fact_input.py",
    "ml/features/worker.py",
    "ml/features/isolated_runtime.py",
    "ml/features/runtime_probe.py",
    AI_FEATURE_SCHEMA_PATH,
)
ROOT = Path(__file__).resolve().parents[2]


class FeatureDescriptor(Contract):
    identity_version: Literal["1.0.0"]
    role: Literal["features"]
    owner: Literal["retailops-cloud-native-platform"]
    parent_ids: list[Annotated[str, Field(pattern=r"^source-sha256-[0-9a-f]{64}$")]]
    schema_version: Literal["2.0", "3.0"]
    feature_schema_sha256: SHA256
    transformation_version: Literal[
        "observed-demand-identity-1.0.0",
        "daily-demand-panel-features-1.0.0",
        "daily-demand-facts-worker-1.0.0",
    ]
    code_sha256: SHA256
    dependency_sha256: SHA256
    python_version: str
    columns: list[str]
    identity_columns: list[str]
    row_count: Count
    content_sha256: SHA256


class FeatureArtifact(Contract):
    path: Literal["features.csv"]
    sha256: SHA256
    size_bytes: Count


class FeatureIdentityManifest(Contract):
    schema_version: Literal["1.0.0"]
    dataset_id: Annotated[str, Field(pattern=r"^features-sha256-[0-9a-f]{64}$")]
    descriptor: FeatureDescriptor
    source_descriptor: SourceDescriptor
    requested_parameters: RequestedParameters
    provenance: Provenance
    artifact: FeatureArtifact
    generated_at: str
    complete_daily_panel: bool
    inventory_ready: Literal[False]
    readiness: Literal["not_ready"]


def feature_identity(
    config: DatasetGenerationConfig,
    tables: dict[str, list[dict[str, Any]]],
    rows: list[dict[str, Any]],
    columns: list[str],
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    _, source_descriptor = source_identity(config, tables)
    return feature_identity_from_source(config, source_descriptor, rows, columns)


def feature_identity_from_source(
    config: DatasetGenerationConfig, source_descriptor: dict, rows: list[dict], columns: list[str]
) -> tuple[str, dict, dict]:
    SourceDescriptor.model_validate(source_descriptor)
    source_id = "source-sha256-" + json_sha256(source_descriptor)
    ai = uses_demand(config.profile)
    fingerprint = code_fingerprint(FEATURE_CODE)
    identity_columns = [name for name in columns if name not in {"dataset_id", "generated_at"}]
    descriptor = {
        "identity_version": "1.0.0",
        "role": "features",
        "owner": "retailops-cloud-native-platform",
        "parent_ids": [source_id],
        "schema_version": "3.0" if ai else "2.0",
        "feature_schema_sha256": file_sha256(
            ROOT / (AI_FEATURE_SCHEMA_PATH if ai else SCHEMA_PATH)
        ),
        "transformation_version": "daily-demand-facts-worker-1.0.0"
        if ai
        else "observed-demand-identity-1.0.0",
        "code_sha256": fingerprint["code_sha256"],
        "dependency_sha256": fingerprint["dependency_sha256"],
        "python_version": fingerprint["python_version"],
        "columns": columns,
        "identity_columns": identity_columns,
        "row_count": len(rows),
        "content_sha256": content_sha256(rows, identity_columns),
    }
    return "features-sha256-" + json_sha256(descriptor), descriptor, source_descriptor


def write_feature_identity_manifest(
    config: DatasetGenerationConfig,
    tables: dict[str, list[dict[str, Any]]] | None,
    rows: list[dict[str, Any]],
    columns: list[str],
    output_dir: Path,
    *,
    source_descriptor: dict | None = None,
) -> None:
    if source_descriptor is None:
        dataset_id, descriptor, source_descriptor = feature_identity(config, tables, rows, columns)
    else:
        dataset_id, descriptor, source_descriptor = feature_identity_from_source(
            config, source_descriptor, rows, columns
        )
    path = output_dir / "features.csv"
    payload = {
        "schema_version": "1.0.0",
        "dataset_id": dataset_id,
        "descriptor": descriptor,
        "source_descriptor": source_descriptor,
        "requested_parameters": requested_parameters(config),
        "provenance": code_provenance(code_fingerprint(FEATURE_CODE)),
        "artifact": {
            "path": path.name,
            "sha256": file_sha256(path),
            "size_bytes": path.stat().st_size,
        },
        "generated_at": datetime.now(UTC).isoformat(),
        "complete_daily_panel": uses_demand(config.profile),
        "inventory_ready": False,
        "readiness": "not_ready",
    }
    validate_feature_identity_manifest(payload, output_dir, columns)
    (output_dir / IDENTITY_FILENAME).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def identity_columns_for_schema(schema_version: str, columns: list[str] | None) -> list[str]:
    if columns is not None:
        return columns
    if schema_version == "3.0":
        return AI_FEATURE_COLUMNS
    import ml.features.demand_forecast as legacy_features  # noqa: PLC0415 - avoid import cycle

    return legacy_features.FEATURE_COLUMNS


def validate_feature_identity_manifest(
    payload: dict[str, Any],
    output_dir: Path,
    columns: list[str] | None,
) -> str:
    manifest = FeatureIdentityManifest.model_validate(payload)
    descriptor = manifest.descriptor.model_dump()
    source_descriptor = manifest.source_descriptor.model_dump(exclude_unset=True)
    source_id = "source-sha256-" + json_sha256(source_descriptor)
    columns = identity_columns_for_schema(descriptor["schema_version"], columns)
    ai = descriptor["schema_version"] == "3.0"
    expected_transform = (
        (
            "daily-demand-facts-worker-1.0.0"
            if source_descriptor["schema_version"] == "2.5.0"
            else "daily-demand-panel-features-1.0.0"
        )
        if ai
        else "observed-demand-identity-1.0.0"
    )
    if (
        ai
        != uses_demand(
            source_descriptor["resolved_parameters"]["profile"], source_descriptor["schema_version"]
        )
        or manifest.complete_daily_panel != ai
        or descriptor["transformation_version"] != expected_transform
    ):
        msg = "Feature schema, completeness or source version disagree."
        raise ValueError(msg)
    config = config_from_parameters(manifest.requested_parameters.model_dump())
    if source_descriptor["resolved_parameters"] != resolve_generation_config(config).parameters():
        msg = "Feature source parameters disagree."
        raise ValueError(msg)
    identity_columns = [name for name in columns if name not in {"dataset_id", "generated_at"}]
    if (
        manifest.dataset_id != "features-sha256-" + json_sha256(descriptor)
        or descriptor["parent_ids"] != [source_id]
        or source_descriptor["parent_ids"]
        or descriptor["columns"] != columns
        or descriptor["identity_columns"] != identity_columns
    ):
        msg = "Invalid feature identity or source lineage."
        raise ValueError(msg)
    provenance = manifest.provenance.model_dump()
    if (
        descriptor["feature_schema_sha256"]
        != provenance["code_files"].get(AI_FEATURE_SCHEMA_PATH if ai else SCHEMA_PATH)
        or source_descriptor["dependency_sha256"] != descriptor["dependency_sha256"]
        or source_descriptor["python_version"] != descriptor["python_version"]
    ):
        msg = "Feature schema or source environment disagrees."
        raise ValueError(msg)
    for kind in ("code", "dependency"):
        if descriptor[kind + "_sha256"] != provenance[kind + "_sha256"] or provenance[
            kind + "_sha256"
        ] != json_sha256(provenance[kind + "_files"]):
            msg = "Feature provenance does not match identity."
            raise ValueError(msg)
    if descriptor["python_version"] != provenance["python_version"]:
        msg = "Feature Python provenance disagrees."
        raise ValueError(msg)
    generated = datetime.fromisoformat(manifest.generated_at)
    if generated.tzinfo is None or generated.utcoffset().total_seconds() != 0:
        msg = "Feature manifest generation time requires UTC."
        raise ValueError(msg)
    path = output_dir / manifest.artifact.path
    if (
        path.is_symlink()
        or file_sha256(path) != manifest.artifact.sha256
        or path.stat().st_size != manifest.artifact.size_bytes
    ):
        msg = "Feature artifact byte checksum does not match."
        raise ValueError(msg)
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != columns:
            msg = "Feature CSV columns disagree."
            raise ValueError(msg)
        rows = list(reader)
    if (
        any(None in row or any(value is None for value in row.values()) for row in rows)
        or any(row["dataset_id"] != manifest.dataset_id for row in rows)
        or len(rows) != descriptor["row_count"]
        or content_sha256(rows, identity_columns) != descriptor["content_sha256"]
    ):
        msg = "Feature content or row identity disagrees."
        raise ValueError(msg)
    if ai:
        validate_ai_records(rows)
    return manifest.dataset_id


def load_feature_identity_manifest(
    output_dir: Path, columns: list[str] | None = None
) -> dict[str, Any]:
    path = output_dir / IDENTITY_FILENAME
    if path.is_symlink() or path.stat().st_size > 1024 * 1024:
        msg = "Feature manifest must be a bounded regular file."
        raise ValueError(msg)
    payload = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_keys)
    validate_feature_identity_manifest(payload, output_dir, columns)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify feature identity and source lineage.")
    parser.add_argument("--data-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        manifest = load_feature_identity_manifest(args.data_dir)
    except (ValueError, OSError):
        parser.exit(1, "Feature identity verification failed.\n")
    print("Feature identity verified: " + manifest["dataset_id"])  # noqa: T201 - CLI result


if __name__ == "__main__":
    main()
