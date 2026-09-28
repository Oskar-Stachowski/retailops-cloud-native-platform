from __future__ import annotations

import copy
import json
from datetime import UTC, date, datetime, timedelta
from zipfile import ZipFile
from pathlib import Path

import pytest

from data.generator.configuration import DatasetGenerationConfig, resolve_generation_config
from data.generator.demand_panel import build_daily_panel
from data.generator.main import build_dataset
from data.generator.manifest_v2 import load_source_manifest_v2
from data.generator.observation_history import append_daily_revision, build_daily_versions, validate_daily_versions
from data.generator.source_quality import project_facts
from ml.features.ai_demand import calendar_lag
from ml.features.demand_forecast import build_demand_feature_rows, observation_at_origin
from ml.features.identity import load_feature_identity_manifest
from ml.features.observation_history import aggregate_versions, append_version, history_json, history_status, observation_at_time
from ml.features.worker import transform
from ml.models.random_forest_forecast import build_training_features
from ml.evaluation.fixed_origin import FixedOriginConfig, build_daily_panel as evaluation_panel, evaluate_fixed_origin


def test_late_sale_and_quantity_correction_preserve_earlier_features():
    config = DatasetGenerationConfig(profile="demo")
    tables = build_dataset(config)
    sale = {**tables["sales"][0], "quantity": "3"}
    day = date.fromisoformat(sale["sold_at"][:10])
    tables["sales"] = [sale]
    initial = build_demand_feature_rows(tables, config)[0]
    target_day = day + timedelta(days=1)
    target = {**initial, "date": target_day.isoformat()}
    expected = build_training_features(target, [initial], window_days=7)
    late_time = datetime.combine(day + timedelta(days=3), datetime.min.time(), tzinfo=UTC)
    late = {**sale, "id": "late-sale", "quantity": "5", "ingested_at": late_time.isoformat()}
    tables["sales"].append(late)
    with_late = build_demand_feature_rows(tables, config)[0]
    assert build_training_features(target, [with_late], window_days=7) == expected
    assert observation_at_origin(with_late, target_day)["units_sold"] == 3
    assert observation_at_time(with_late, late_time)["units_sold"] == 8
    correction = {**sale, "quantity": "1", "ingested_at": (late_time + timedelta(days=1)).isoformat()}
    tables["sales"].append(correction)
    corrected = build_demand_feature_rows(tables, config)[0]
    assert build_training_features(target, [corrected], window_days=7) == expected
    assert observation_at_time(corrected, late_time)["units_sold"] == 8
    assert corrected["units_sold"] == 6  # replacement of 3 by 1, not an additional sale
    assert initial["dataset_id"] != with_late["dataset_id"] != corrected["dataset_id"]


def test_daily_history_preserves_known_state_and_worker_calendar_lag():
    config = DatasetGenerationConfig(profile="ai-smoke", days=5, products=8, stores=3, warehouses=2)
    resolved = resolve_generation_config(config)
    tables = build_dataset(config)
    initial = copy.deepcopy(tables["daily_demand_versions"])
    original_rows = transform(project_facts(tables))
    sale = tables["sales"][0]
    reference = next(row for row in tables["sale_price_references"] if row["sale_id"] == sale["id"])
    day = date.fromisoformat(reference["business_date"])
    late_at = datetime.combine(resolved.end_date + timedelta(days=2), datetime.min.time(), tzinfo=UTC)
    late = {**sale, "id": "late-sale", "quantity": "5", "total_amount": str(5 * float(sale["unit_price"])), "ingested_at": late_at.isoformat()}
    tables["sales"].append(late)
    tables["sale_price_references"].append({**reference, "id": "late-reference", "sale_id": "late-sale"})
    tables["daily_demand_versions"] = build_daily_versions(tables, resolved)
    tables["daily_demand_observations"] = build_daily_panel(tables, resolved)
    assert all(row in tables["daily_demand_versions"] for row in initial)
    validate_daily_versions(tables)
    revised = transform(project_facts(tables))
    series = tuple(reference[field] for field in ("product_id", "selling_location_id", "channel"))
    first_target = day + timedelta(days=3)
    assert calendar_lag(original_rows, series, first_target, 1) == calendar_lag(revised, series, first_target, 1)
    observation = next(row for row in tables["daily_demand_observations"] if row["product_id"] == sale["product_id"] and row["business_date"] == day.isoformat() and row["channel"] == sale["channel"] and row["selling_location_id"] == series[1])
    old = copy.deepcopy(tables["daily_demand_versions"])
    tables["daily_demand_versions"] = append_daily_revision(old, observation["id"], int(observation["observed_units"]) + 2, (late_at + timedelta(days=1)).isoformat())
    assert tables["daily_demand_versions"][:-1] == old
    observation["observed_units"] = str(int(observation["observed_units"]) + 2)
    observation["available_at"] = (late_at + timedelta(days=1)).isoformat()
    validate_daily_versions(tables)
    corrected = transform(project_facts(tables))
    assert calendar_lag(corrected, series, first_target, 1) == calendar_lag(original_rows, series, first_target, 1)


def test_version_cutoffs_and_missing_history_are_explicit():
    history = append_version([], 3, "2026-07-01T12:00:00+00:00")
    history = append_version(history, 8, "2026-07-01T23:59:59.500000+00:00")
    row = {"observation_history": history_json(history)}
    assert history_status(row, datetime(2026, 7, 1, 11, tzinfo=UTC)) == "missing_history"
    assert observation_at_time(row, datetime(2026, 7, 1, 23, 59, 59, tzinfo=UTC))["units_sold"] == 3
    assert observation_at_time(row, datetime(2026, 7, 1, 23, 59, 59, 500000, tzinfo=UTC))["units_sold"] == 8
    assert observation_at_time({"observation_history": "[]"}, datetime.now(UTC)) is None
    missing = append_version([], None, "2026-07-01T12:00:00+00:00")
    assert history_status({"observation_history": history_json(missing)}, datetime(2026,7,2,tzinfo=UTC)) == "missing"


@pytest.mark.parametrize("kind", ["delete_prefix", "duplicate", "backdate", "latest_value", "grain", "extra_field"])
def test_history_gate_rejects_ambiguous_or_rewritten_states(kind):
    config = DatasetGenerationConfig(profile="ai-smoke", days=2, products=4, stores=2, warehouses=2)
    tables = build_dataset(config)
    row = tables["daily_demand_versions"][0]
    if kind == "delete_prefix": row["version"] = "2"
    elif kind == "duplicate": tables["daily_demand_versions"].append(dict(row))
    elif kind == "backdate": row["available_at"] = "2020-01-01T00:00:00+00:00"
    elif kind == "latest_value": row["observed_units"] = str(int(row["observed_units"]) + 1)
    elif kind == "grain": row["channel"] = "invalid"
    else: row["truth"] = "1"
    with pytest.raises(ValueError): validate_daily_versions(tables)


def test_correction_cannot_backdate_or_invent_an_earlier_state():
    history = append_version([], 3, "2026-07-01T12:00:00+00:00")
    for value in ("2026-07-01T11:00:00+00:00", "2026-07-01T12:00:00+00:00"):
        with pytest.raises(ValueError, match="increase strictly"): append_version(history, 8, value)
    with pytest.raises(ValueError, match="Missing observation history"): append_daily_revision([], "unknown", 8, "2026-07-02T00:00:00+00:00")
    with pytest.raises(ValueError, match="Ambiguous sale revision"):
        aggregate_versions([("sale", datetime(2026,7,1,tzinfo=UTC),3), ("sale",datetime(2026,7,1,tzinfo=UTC),8)])


def test_late_corrections_cannot_change_fixed_origin_training_or_predictions():
    config = FixedOriginConfig(dataset=DatasetGenerationConfig(profile="small", days=42, products=5, stores=2, warehouses=2), n_estimators=8)
    tables = build_dataset(config.dataset)
    features = build_demand_feature_rows(tables, config.dataset)
    start, end = date(2026,3,20), date(2026,4,30)
    panel = evaluation_panel(features, tables["products"], tables["stores"], date_start=start, date_end=end, max_panel_rows=config.max_panel_rows, assume_synthetic_complete=True)
    _, before, _ = evaluate_fixed_origin(panel, date_start=start, date_end=end, config=config)
    revised = copy.deepcopy(panel)
    for row in revised:
        if "observation_history" in row:
            history = json.loads(row["observation_history"])
            row["observation_history"] = history_json(append_version(history, int(row["units_sold"]) + 1000, "2099-01-01T00:00:00+00:00"))
            row["units_sold"] = int(row["units_sold"]) + 1000
            row["observation_available_at"] = "2099-01-01T00:00:00+00:00"
    _, after, _ = evaluate_fixed_origin(revised, date_start=start, date_end=end, config=config)
    assert [(r["predicted_units"], r["baseline_predicted_units"]) for r in before] == [(r["predicted_units"], r["baseline_predicted_units"]) for r in after]
    assert [r["actual_units"] for r in before] != [r["actual_units"] for r in after]


def test_historical_source25_and_features30_retain_identity(tmp_path):
    root = Path(__file__).resolve().parents[3]
    with ZipFile(root/"services/api/tests/fixtures/source_manifest_v2_5.zip") as archive:
        for name in archive.namelist(): (tmp_path/name).write_bytes(archive.read(name))
    source, features = load_source_manifest_v2(tmp_path), load_feature_identity_manifest(tmp_path)
    assert source["dataset_id"] == "source-sha256-608e4b784829f05628195c52ab403409ccbd61ada13ac1e1b34c5392a585e4d8"
    assert features["dataset_id"] == "features-sha256-662447c8a6002cde3084489bf7eb7157d1dcbf29ad56acc52e9481d5ae9f7f07"
