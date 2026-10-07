"""Cached execution preserves complete planned-forecast sources on portfolio seeds."""

import json

import pytest

from data.generator.configuration import DatasetGenerationConfig
from data.generator.identity import canonical_json
from data.inventory.run_source_dataset import (
    build_source_dataset,
    default_inventory_config,
)
from data.inventory.source_cohort_batch_v2 import build_source_dataset_fast
from data.inventory.source_dataset_contract import SOURCE_TABLES, csv_path
from data.inventory.source_dataset_io import (
    normalize_source,
    read_source_dataset,
    write_source_dataset,
)


@pytest.mark.parametrize("seed", [42, 137, 2026])
def test_all_planned_source_tables_bytes_and_qualification_match(seed, tmp_path):
    generation = DatasetGenerationConfig(
        profile="ai-load",
        days=45,
        products=2,
        stores=1,
        warehouses=1,
        seed=seed,
        forecast_plan_days=14,
        max_daily_rows=90,
    )
    config = default_inventory_config(generation)
    ordinary, ordinary_context = build_source_dataset(generation, config)
    cached, cached_context = build_source_dataset_fast(generation, config)
    assert ordinary_context == cached_context
    assert normalize_source(ordinary) == normalize_source(cached)
    assert set(ordinary) == set(SOURCE_TABLES) and len(ordinary) == 58
    for name in SOURCE_TABLES:
        assert canonical_json(normalize_source(ordinary)[name]) == canonical_json(
            normalize_source(cached)[name]
        )
    ordinary_path = write_source_dataset(
        ordinary, ordinary_context, generation, config, tmp_path / "ordinary"
    )
    cached_path = write_source_dataset(
        cached, cached_context, generation, config, tmp_path / "cached"
    )
    assert ordinary_path.name == cached_path.name
    for name in SOURCE_TABLES:
        assert (ordinary_path / csv_path(name)).read_bytes() == (
            cached_path / csv_path(name)
        ).read_bytes()
    restored, manifest = read_source_dataset(cached_path)
    assert restored == normalize_source(ordinary)
    assert manifest["facts_ready"] is True
    report = json.loads((cached_path / "source_report.json").read_bytes())
    assert all(check["status"] == "passed" for check in report["checks"])
    assert (ordinary_path / "source_report.json").read_bytes() == (
        cached_path / "source_report.json"
    ).read_bytes()
