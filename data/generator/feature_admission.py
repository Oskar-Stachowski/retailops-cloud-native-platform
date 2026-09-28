from __future__ import annotations

from typing import TYPE_CHECKING

from data.generator.configuration import resolve_generation_config
from data.generator.manifest_v2 import (
    SourceManifestV2,
    load_source_manifest_v2,
    read_verified_tables,
)
from data.generator.simulation_schema import uses_separation
from data.generator.source_quality import project_facts, validate_source_report
from ml.features.fact_input import require

if TYPE_CHECKING:
    from pathlib import Path

    from data.generator.configuration import DatasetGenerationConfig


def admit_feature_tables(tables: dict, config: DatasetGenerationConfig) -> dict:
    validate_source_report(tables, resolve_generation_config(config))
    return project_facts(tables)


def admit_feature_source(source_dir: Path, config: DatasetGenerationConfig) -> tuple[dict, dict]:
    manifest = load_source_manifest_v2(source_dir)
    require(
        manifest["schema_version"] == "2.6.0"
        and uses_separation(config.profile, manifest["schema_version"])
        and manifest["source_ready"]
        and manifest["descriptor"]["resolved_parameters"]
        == resolve_generation_config(config).parameters(),
        "Feature source requires an accepted 2.6 export with matching parameters.",
    )
    # The projected records themselves must match the verified identity, including
    # when a mutable export changes between admission and this second read.
    tables = read_verified_tables(
        SourceManifestV2.model_validate(manifest),
        source_dir,
        resolve_generation_config(config).end_date.isoformat(),
    )
    return project_facts(tables), manifest["descriptor"]
