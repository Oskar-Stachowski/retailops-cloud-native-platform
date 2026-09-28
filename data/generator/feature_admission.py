from __future__ import annotations

import csv
from typing import TYPE_CHECKING

from data.generator.configuration import resolve_generation_config
from data.generator.manifest_v2 import load_source_manifest_v2
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
        uses_separation(config.profile, manifest["schema_version"])
        and manifest["source_ready"]
        and manifest["descriptor"]["resolved_parameters"]
        == resolve_generation_config(config).parameters(),
        "Feature source requires an accepted 2.5 export with matching parameters.",
    )
    tables = {}
    for artifact in manifest["artifacts"]:
        with (source_dir / artifact["path"]).open(newline="", encoding="utf-8") as stream:
            tables[artifact["table"]] = list(csv.DictReader(stream))
    return project_facts(tables), manifest["descriptor"]
