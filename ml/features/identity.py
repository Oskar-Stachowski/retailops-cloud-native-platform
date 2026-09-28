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

IDENTITY_FILENAME = "feature_identity_manifest.json"
SCHEMA_PATH = "ml/contracts/demand_forecast_features.schema.json"
IDENTITY_SCHEMA_PATH = "ml/contracts/feature_identity_manifest.schema.json"
FEATURE_CODE = (
    "ml/features/demand_forecast.py",
    "ml/features/identity.py",
    SCHEMA_PATH,
    IDENTITY_SCHEMA_PATH,
)
ROOT = Path(__file__).resolve().parents[2]


class FeatureDescriptor(Contract):
    identity_version: Literal["1.0.0"]
    role: Literal["features"]
    owner: Literal["retailops-cloud-native-platform"]
    parent_ids: list[Annotated[str, Field(pattern=r"^source-sha256-[0-9a-f]{64}$")]]
    schema_version: Literal["2.0"]
    feature_schema_sha256: SHA256
    transformation_version: Literal["observed-demand-identity-1.0.0"]
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
    complete_daily_panel: Literal[False]
    inventory_ready: Literal[False]
    readiness: Literal["not_ready"]


def feature_identity(
    config: DatasetGenerationConfig,
    tables: dict[str, list[dict[str, Any]]],
    rows: list[dict[str, Any]],
    columns: list[str],
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    source_id, source_descriptor = source_identity(config, tables)
    fingerprint = code_fingerprint(FEATURE_CODE)
    identity_columns = [name for name in columns if name not in {"dataset_id", "generated_at"}]
    descriptor = {
        "identity_version": "1.0.0",
        "role": "features",
        "owner": "retailops-cloud-native-platform",
        "parent_ids": [source_id],
        "schema_version": "2.0",
        "feature_schema_sha256": file_sha256(ROOT / SCHEMA_PATH),
        "transformation_version": "observed-demand-identity-1.0.0",
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
    tables: dict[str, list[dict[str, Any]]],
    rows: list[dict[str, Any]],
    columns: list[str],
    output_dir: Path,
) -> None:
    dataset_id, descriptor, source_descriptor = feature_identity(config, tables, rows, columns)
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
        "complete_daily_panel": False,
        "inventory_ready": False,
        "readiness": "not_ready",
    }
    validate_feature_identity_manifest(payload, output_dir, columns)
    (output_dir / IDENTITY_FILENAME).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def validate_feature_identity_manifest(
    payload: dict[str, Any],
    output_dir: Path,
    columns: list[str],
) -> str:
    manifest = FeatureIdentityManifest.model_validate(payload)
    descriptor = manifest.descriptor.model_dump()
    source_descriptor = manifest.source_descriptor.model_dump()
    source_id = "source-sha256-" + json_sha256(source_descriptor)
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
        descriptor["feature_schema_sha256"] != provenance["code_files"].get(SCHEMA_PATH)
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
    return manifest.dataset_id


def load_feature_identity_manifest(output_dir: Path, columns: list[str]) -> dict[str, Any]:
    path = output_dir / IDENTITY_FILENAME
    if path.is_symlink() or path.stat().st_size > 1024 * 1024:
        msg = "Feature manifest must be a bounded regular file."
        raise ValueError(msg)
    payload = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_keys)
    validate_feature_identity_manifest(payload, output_dir, columns)
    return payload


def main() -> None:
    from ml.features.demand_forecast import (  # noqa: PLC0415 - avoid generation import cycle
        FEATURE_COLUMNS,
    )

    parser = argparse.ArgumentParser(description="Verify feature identity and source lineage.")
    parser.add_argument("--data-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        manifest = load_feature_identity_manifest(args.data_dir, FEATURE_COLUMNS)
    except (ValueError, OSError):
        parser.exit(1, "Feature identity verification failed.\n")
    print("Feature identity verified: " + manifest["dataset_id"])  # noqa: T201 - CLI result


if __name__ == "__main__":
    main()
