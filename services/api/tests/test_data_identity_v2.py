from __future__ import annotations

import copy
import json
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from data.generator.configuration import DatasetGenerationConfig, resolve_generation_config
from data.generator.identity import canonical_cell, content_sha256, source_identity
from data.generator.main import build_dataset, generate_demo_dataset
from data.generator.manifest_v2 import (
    MANIFEST_V2_FILENAME,
    SourceManifestV2,
    load_source_manifest_v2,
    validate_source_manifest_v2,
)
from ml.features.demand_forecast import (
    FEATURE_COLUMNS,
    DemandFeatureGenerationConfig,
    build_demand_feature_rows,
    generate_demand_feature_dataset,
)
from ml.features.identity import (
    FeatureIdentityManifest,
    feature_identity,
    load_feature_identity_manifest,
    validate_feature_identity_manifest,
)

ROOT = Path(__file__).resolve().parents[3]
BOUNDED = DatasetGenerationConfig(profile="small", days=6, products=8, stores=3, warehouses=2)


@pytest.mark.parametrize(
    "profile,expected",
    [
        ("small", (90, 100, 5, 3)),
        ("medium", (180, 500, 20, 6)),
        ("large", (365, 1000, 50, 10)),
        ("ai-smoke", (30, 20, 3, 2)),
        ("ai-temporal-smoke", (102, 8, 3, 2)),
        ("ai-dev", (365, 100, 5, 3)),
        ("ai-training", (730, 200, 10, 4)),
    ],
)
def test_profile_resolution_has_no_unknown_defaults(profile, expected):
    result = resolve_generation_config(DatasetGenerationConfig(profile=profile))
    assert (result.days, result.products, result.stores, result.warehouses) == expected
    assert all(value is not None for value in result.parameters().values())
    assert (result.end_date - result.start_date).days + 1 == result.days
    assert result.end_date == (
        date(2026, 7, 31) if profile.startswith("ai-") else date(2026, 4, 30)
    )
    if profile == "ai-temporal-smoke":
        assert (result.warmup_days, result.origin_days, result.label_tail_days) == (28, 60, 14)


@pytest.mark.parametrize(
    "config",
    [
        DatasetGenerationConfig(profile="ai-load"),
        replace(BOUNDED, max_daily_rows=1),
        replace(BOUNDED, days=True),
        replace(BOUNDED, seed=None),
        replace(BOUNDED, start_date="2026-01-01"),
        replace(BOUNDED, start_date=date(2026, 5, 1), end_date=date(2026, 4, 30)),
        replace(BOUNDED, start_date=date(2026, 4, 1), end_date=date(2026, 4, 30)),
        DatasetGenerationConfig(profile="ai-temporal-smoke", days=42),
        DatasetGenerationConfig(end_date=date(2026, 7, 31)),
    ],
)
def test_invalid_configuration_is_rejected(config):
    with pytest.raises(ValueError):
        resolve_generation_config(config)


def test_explicit_date_rules_and_ai_load():
    end = date(2026, 6, 30)
    result = resolve_generation_config(replace(BOUNDED, end_date=end))
    assert (result.start_date, result.end_date) == (date(2026, 6, 25), end)
    result = resolve_generation_config(replace(BOUNDED, start_date=date(2026, 6, 1)))
    assert result.end_date == date(2026, 6, 6)
    result = resolve_generation_config(
        replace(BOUNDED, days=None, start_date=date(2026, 6, 1), end_date=end)
    )
    assert result.days == 30
    assert (
        resolve_generation_config(replace(BOUNDED, profile="ai-load", max_daily_rows=144)).products
        == 8
    )
    tables = build_dataset(replace(BOUNDED, end_date=end))
    assert min(row["sold_at"][:10] for row in tables["sales"]) == "2026-06-25"
    assert max(row["sold_at"][:10] for row in tables["sales"]) == "2026-06-30"


def test_demo_ignored_options_do_not_change_source_identity():
    default = DatasetGenerationConfig()
    override = DatasetGenerationConfig(days=30, products=20, seed=99)
    assert (
        source_identity(default, build_dataset(default))[0]
        == source_identity(override, build_dataset(override))[0]
    )
    assert resolve_generation_config(override).seed == 42


@pytest.mark.parametrize(
    "override",
    [
        {"products": 20},
        {"seed": 43},
        {"days": 7},
        {"stores": 4},
        {"warehouses": 3},
        {"end_date": date(2026, 7, 31)},
    ],
)
def test_configuration_changes_source_and_feature_identity(override):
    other = replace(BOUNDED, **override)
    tables = build_dataset(BOUNDED)
    other_tables = build_dataset(other)
    assert source_identity(BOUNDED, tables)[0] != source_identity(other, other_tables)[0]
    assert (
        build_demand_feature_rows(tables, BOUNDED)[0]["dataset_id"]
        != build_demand_feature_rows(other_tables, other)[0]["dataset_id"]
    )


def test_content_and_row_order_have_distinct_identity_effects():
    tables = build_dataset(BOUNDED)
    original_source, _ = source_identity(BOUNDED, tables)
    original_features = build_demand_feature_rows(tables, BOUNDED)
    reordered = {key: list(reversed(rows)) for key, rows in tables.items()}
    assert source_identity(BOUNDED, reordered)[0] == original_source
    assert build_demand_feature_rows(reordered, BOUNDED) == original_features
    changed = copy.deepcopy(tables)
    changed["products"][0]["name"] += " changed"
    assert source_identity(BOUNDED, changed)[0] != original_source
    assert (
        build_demand_feature_rows(changed, BOUNDED)[0]["dataset_id"]
        != original_features[0]["dataset_id"]
    )
    descriptor_id, _, _ = feature_identity(BOUNDED, tables, original_features, FEATURE_COLUMNS)
    modified = copy.deepcopy(original_features)
    modified[0]["units_sold"] += 1
    assert feature_identity(BOUNDED, tables, modified, FEATURE_COLUMNS)[0] != descriptor_id
    metadata_only = copy.deepcopy(original_features)
    for row in metadata_only:
        row["dataset_id"] = "irrelevant-self-id"
        row["generated_at"] = "2030-01-01T00:00:00+00:00"
    assert feature_identity(BOUNDED, tables, metadata_only, FEATURE_COLUMNS)[0] == descriptor_id


def test_canonicalization_preserves_types_and_duplicate_rows():
    assert canonical_cell("price", "10.00") == canonical_cell("price", "1E1")
    assert canonical_cell("price", "-0.00") == "0"
    assert canonical_cell("name", "e\u0301") == "é"
    assert canonical_cell("sold_at", "2026-07-31T12:00:00+02:00") == "2026-07-31T10:00:00+00:00"
    assert (
        canonical_cell("recorded_at", "('2026-07-31T10:00:00+00:00',)")
        == "2026-07-31T10:00:00+00:00"
    )
    assert canonical_cell("valid_to", "") is None
    rows = [{"quantity": "1"}]
    assert content_sha256(rows, ["quantity"]) != content_sha256(rows * 2, ["quantity"])
    for field, value in [
        ("quantity", "1.5"),
        ("price", "NaN"),
        ("price", "invalid"),
        ("sold_at", "2026-01-01T00:00:00"),
        ("stockout_flag", "1"),
    ]:
        with pytest.raises(ValueError):
            canonical_cell(field, value)


@pytest.fixture
def exported(tmp_path):
    generate_demo_dataset(tmp_path, BOUNDED)
    return tmp_path, load_source_manifest_v2(tmp_path)


@pytest.mark.parametrize(
    "kind",
    [
        "null",
        "missing",
        "checksum",
        "content",
        "id",
        "path",
        "watermark",
        "provenance",
        "range",
        "unexpected",
    ],
)
def test_manifest_rejects_incomplete_or_inconsistent_metadata(exported, kind):
    directory, original = exported
    payload = copy.deepcopy(original)
    if kind == "null":
        payload["descriptor"]["resolved_parameters"]["products"] = None
    if kind == "missing":
        del payload["descriptor"]["resolved_parameters"]["seed"]
    if kind == "checksum":
        payload["artifacts"][0]["sha256"] = "0" * 64
    if kind == "content":
        payload["artifacts"][0]["content_sha256"] = "0" * 64
    if kind == "id":
        payload["dataset_id"] = "source-sha256-" + "0" * 64
    if kind == "path":
        payload["artifacts"][0]["path"] = "../products.csv"
    if kind == "watermark":
        payload["watermarks"]["sales"]["as_of_time"] = "2030-01-01T23:59:59+00:00"
    if kind == "provenance":
        payload["provenance"]["code_files"] = {}
    if kind == "range":
        payload["artifacts"][4]["date_range"]["date_end"] = "2030-01-01"
    if kind == "unexpected":
        payload["extra"] = True
    with pytest.raises(ValueError):
        validate_source_manifest_v2(payload, directory)


def test_manifest_rejects_changed_bytes_missing_files_and_duplicate_json_keys(exported):
    directory, payload = exported
    path = directory / "sales.csv"
    original = path.read_bytes()
    path.write_bytes(original + b"\n")
    with pytest.raises(ValueError):
        validate_source_manifest_v2(payload, directory)
    path.write_bytes(original)
    (directory / "products.csv").unlink()
    with pytest.raises(OSError):
        validate_source_manifest_v2(payload, directory)
    (directory / MANIFEST_V2_FILENAME).write_text('{"dataset_id":"a","dataset_id":"b"}')
    with pytest.raises(ValueError, match="Duplicate"):
        load_source_manifest_v2(directory)


def test_future_ranges_and_watermarks_follow_actual_files(exported):
    _, payload = exported
    artifacts = {a["table"]: a for a in payload["artifacts"]}
    end = payload["descriptor"]["resolved_parameters"]["end_date"]
    assert artifacts["sales"]["field_ranges"]["sold_at"]["date_end"] == end
    for name in ("price_history", "promotions", "forecasts"):
        assert artifacts[name]["future_range"]["date_end"] > end
    assert artifacts["returns"]["temporal_role"] == "return_tail"
    assert artifacts["price_history"]["open_interval_rows"] > 0
    assert payload["watermarks"]["sales"]["as_of_time"] == end + "T23:59:59+00:00"
    assert payload["watermarks"]["sales"]["complete_through"] is None
    assert payload["inventory_ready"] is False
    assert payload["readiness"]["forecasting"] == "not_ready"


@pytest.mark.parametrize(
    "config",
    [
        BOUNDED,
        DatasetGenerationConfig(profile="ai-smoke"),
        DatasetGenerationConfig(profile="ai-temporal-smoke"),
    ],
)
def test_repeated_exports_keep_logical_identity_and_table_bytes(tmp_path, config):
    manifests = []
    feature_manifests = []
    for name in ("a", "b"):
        directory = tmp_path / name
        generate_demo_dataset(directory, config)
        manifests.append(load_source_manifest_v2(directory))
        generate_demand_feature_dataset(
            DemandFeatureGenerationConfig(dataset=config, output_dir=directory / "features", source_dir=directory)
        )
        feature_manifests.append(
            load_feature_identity_manifest(directory / "features")
        )
    assert manifests[0]["dataset_id"] == manifests[1]["dataset_id"]
    assert manifests[0]["artifacts"] == manifests[1]["artifacts"]
    assert feature_manifests[0]["dataset_id"] == feature_manifests[1]["dataset_id"]
    assert feature_manifests[0]["artifact"] == feature_manifests[1]["artifact"]
    assert feature_manifests[0]["descriptor"]["parent_ids"] == [manifests[0]["dataset_id"]]
    feature_path = tmp_path / "a" / "features"
    (feature_path / "features.csv").write_bytes(
        (feature_path / "features.csv").read_bytes() + b"\n"
    )
    with pytest.raises(ValueError):
        validate_feature_identity_manifest(feature_manifests[0], feature_path, FEATURE_COLUMNS)


def test_export_refuses_overwrite_of_different_source_and_features(tmp_path):
    source = tmp_path / "source"
    features = tmp_path / "features"
    generate_demo_dataset(source, BOUNDED)
    generate_demand_feature_dataset(
        DemandFeatureGenerationConfig(dataset=BOUNDED, output_dir=features)
    )
    snapshots = {
        path: path.read_bytes() for directory in (source, features) for path in directory.iterdir()
    }
    other = replace(BOUNDED, seed=43)
    with pytest.raises(ValueError, match="different dataset"):
        generate_demo_dataset(source, other)
    with pytest.raises(ValueError, match="different features"):
        generate_demand_feature_dataset(
            DemandFeatureGenerationConfig(dataset=other, output_dir=features)
        )
    assert all(path.read_bytes() == content for path, content in snapshots.items())
    generate_demo_dataset(source, BOUNDED)
    generate_demand_feature_dataset(
        DemandFeatureGenerationConfig(dataset=BOUNDED, output_dir=features)
    )


def test_committed_json_schemas_match_executable_models():
    for model, path in [
        (SourceManifestV2, "data/contracts/source_dataset_manifest.v2.schema.json"),
        (FeatureIdentityManifest, "ml/contracts/feature_identity_manifest.schema.json"),
    ]:
        assert json.loads((ROOT / path).read_text()) == model.model_json_schema()
