from __future__ import annotations

import copy
import csv
import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from data.generator.configuration import DatasetGenerationConfig, resolve_generation_config
from data.generator.feature_admission import admit_feature_source, admit_feature_tables
from data.generator.main import build_dataset, generate_demo_dataset
from data.generator.manifest_v2 import load_source_manifest_v2, report_metadata, validate_source_manifest_v2
from data.generator.simulation_schema import PRODUCT_PARAMETERS, SALE_TRUTH_FIELDS, STORE_PARAMETERS
from data.generator.source_quality import build_source_report, project_facts
from data.generator.source_realism import build_source_realism
from ml.features.demand_forecast import DemandFeatureGenerationConfig, build_demand_feature_rows, generate_demand_feature_dataset
from ml.features.fact_input import FACT_COLUMNS, validate_fact_input
from ml.features.identity import load_feature_identity_manifest
from ml.features.isolated_runtime import _run, isolated_feature_rows, verify_runtime_isolation
from ml.features.worker import transform

ROOT = Path(__file__).resolve().parents[3]
CONFIG = DatasetGenerationConfig(profile="ai-smoke", days=5, products=8, stores=3, warehouses=2)


@pytest.fixture(scope="module")
def tables():
    return build_dataset(CONFIG)


def test_simulation_is_physically_separate_from_ai_facts(tables):
    for name, forbidden in (("products", PRODUCT_PARAMETERS), ("stores", STORE_PARAMETERS), ("sales", SALE_TRUTH_FIELDS)):
        assert all(not set(forbidden) & row.keys() for row in tables[name])
    assert len(tables["product_simulation_parameters"]) == CONFIG.products
    assert len(tables["store_simulation_parameters"]) == CONFIG.stores
    facts = admit_feature_tables(tables, CONFIG)
    assert set(facts["tables"]) == set(FACT_COLUMNS)
    assert all(set(row) == set(FACT_COLUMNS[name]) for name, rows in facts["tables"].items() for row in rows)
    assert len(transform(facts)) == len(tables["daily_demand_observations"])
    with pytest.raises(ValueError, match="full source tables are forbidden"):
        build_demand_feature_rows(tables, CONFIG)


@pytest.mark.parametrize("name", ["daily_demand_truth", "promotion_effect_truth", "product_simulation_parameters", "inventory_snapshots", "forecasts"])
def test_features_and_runtime_reject_extra_source_tables(tables, name):
    payload = project_facts(tables)
    payload["tables"][name] = copy.deepcopy(tables[name])
    for operation in (validate_fact_input, transform, isolated_feature_rows):
        with pytest.raises(ValueError, match="allowlist"):
            operation(payload)


@pytest.mark.parametrize("table,field", [("daily_demand_observations", "latent_units"), ("daily_demand_observations", "gross_revenue"), ("daily_demand_observations", "realized_unit_price"), ("daily_demand_observations", "stock_quantity"), ("product_catalog", "demand_weight"), ("product_catalog", "unit_cost"), ("catalog_categories", "noise")])
def test_runtime_rejects_extra_fields_in_every_allowed_table(tables, table, field):
    payload = project_facts(tables)
    payload["tables"][table][0][field] = "1"
    with pytest.raises(ValueError, match="allowlist"):
        transform(payload)


@pytest.mark.parametrize("mutation", ["drop_parameters", "duplicate_parameters", "invalid_parameter", "mixed_fact", "bad_legacy_fk", "missing_panel"])
def test_final_hard_gate_rejects_broken_sources(tables, mutation):
    broken = copy.deepcopy(tables)
    if mutation == "drop_parameters": broken["product_simulation_parameters"].pop()
    elif mutation == "duplicate_parameters": broken["store_simulation_parameters"].append(dict(broken["store_simulation_parameters"][0]))
    elif mutation == "invalid_parameter": broken["product_simulation_parameters"][0]["return_rate"] = "1.01"
    elif mutation == "mixed_fact": broken["products"][0]["demand_weight"] = "1"
    elif mutation == "bad_legacy_fk": broken["inventory_snapshots"][0]["product_id"] = "unknown"
    elif mutation == "missing_panel": broken["daily_demand_observations"].pop()
    report = build_source_report(broken, resolve_generation_config(CONFIG))
    assert report["status"] == "failed" and not report["source_ready"]
    with pytest.raises(ValueError, match="hard gate"):
        admit_feature_tables(broken, CONFIG)


def test_final_report_preserves_legacy_gates_and_honest_use_case_readiness(tables):
    report = build_source_report(tables, resolve_generation_config(CONFIG))
    assert len([c for c in report["checks"] if c["check_id"].startswith("legacy:")]) == 15
    assert report["source_ready"] and report["readiness"]["forecast_source"]["status"] == "ready"
    assert not report["inventory_ready"]
    assert all(report["readiness"][name]["status"] == "not_ready" for name in ("forecasting", "anomaly", "stockout", "replay"))
    assert all({"policy_version", "sample_size", "value", "threshold", "status", "evidence"} <= c.keys() for c in report["checks"])


def test_ai_source_reports_cannot_be_forged_by_updating_checksums(tmp_path):
    generate_demo_dataset(tmp_path, CONFIG)
    manifest = load_source_manifest_v2(tmp_path)
    report_path = tmp_path / "source_report.json"
    report = json.loads(report_path.read_text())
    report["readiness"]["stockout"]["status"] = "ready"
    report_path.write_text(json.dumps(report))
    manifest["reports"] = report_metadata(tmp_path, CONFIG.profile)
    with pytest.raises(ValueError, match="Final source report"):
        validate_source_manifest_v2(manifest, tmp_path)


def test_feature_entry_requires_an_explicit_accepted_source(tmp_path):
    with pytest.raises(ValueError, match="source-dir"):
        generate_demand_feature_dataset(DemandFeatureGenerationConfig(CONFIG, tmp_path))
    source = tmp_path / "source"
    generate_demo_dataset(source, CONFIG)
    from dataclasses import replace
    with pytest.raises(ValueError, match="matching parameters"):
        admit_feature_source(source, replace(CONFIG, seed=43))


def test_source_change_during_admission_cannot_get_the_old_parent_identity(tmp_path, monkeypatch):
    generate_demo_dataset(tmp_path, CONFIG)
    original_loader = load_source_manifest_v2

    def mutate_after_validation(source_dir):
        manifest = original_loader(source_dir)
        path = source_dir / "product_catalog.csv"
        with path.open(newline="") as stream:
            reader = csv.DictReader(stream)
            fields, rows = reader.fieldnames, list(reader)
        rows[0]["brand"] = "changed-after-validation"
        with path.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        return manifest

    monkeypatch.setattr("data.generator.feature_admission.load_source_manifest_v2", mutate_after_validation)
    with pytest.raises(ValueError, match="checksum"):
        admit_feature_source(tmp_path, CONFIG)


def test_worker_is_actually_isolated_and_returns_only_facts(tables, monkeypatch):
    monkeypatch.setenv("RETAILOPS_TRUTH_CANARY", "private-source-value")
    assert all(verify_runtime_isolation().values())
    payload = admit_feature_tables(tables, CONFIG)
    assert isolated_feature_rows(payload) == transform(payload)
    for name in ("daily_demand_truth", "inventory_snapshots"):
        bad = copy.deepcopy(payload)
        bad["tables"][name] = tables[name]
        # Bypass supervisor validation to prove the container's own runtime rejects it.
        with pytest.raises(RuntimeError, match="Feature input rejected"):
            _run(bad, "ml.features.worker")


def test_docker_unavailable_never_falls_back_to_host(tables, monkeypatch):
    monkeypatch.setattr("ml.features.isolated_runtime.shutil.which", lambda _: None)
    with pytest.raises(RuntimeError, match="requires Docker"):
        isolated_feature_rows(project_facts(tables))


def test_realism_uses_observed_denominators_without_fabricated_truth(tables):
    report = build_source_realism(CONFIG.profile, CONFIG.seed, tables)
    metrics = {r["metric_id"]: r for r in report["metrics"]}
    assert metrics["top_20_percent_catalog_revenue_share"]["sample_size"] == CONFIG.products
    assert metrics["top_20_percent_catalog_revenue_share"]["status"] == "not_evaluable"
    assert metrics["open_panel_zero_rate"]["sample_size"] == sum(r["location_open"] == "true" for r in tables["daily_demand_observations"])
    assert metrics["stockout_rate"]["value"] is None
    assert metrics["causal_promotion_uplift"]["value"] is None
    assert metrics["stockout_rate"]["status"] == "not_ready"


def test_segment_realism_reconciles_open_days_and_final_refunds(tables):
    metrics = build_source_realism(CONFIG.profile, CONFIG.seed, tables)["metrics"]
    zero = [r for r in metrics if r["metric_id"].startswith("open_panel_zero_rate:")]
    returns = [r for r in metrics if r["metric_id"].startswith("final_refunded_unit_rate:")]
    assert sum(r["sample_size"] for r in zero) == sum(r["location_open"] == "true" for r in tables["daily_demand_observations"])
    assert sum(r["sample_size"] for r in returns) == sum(int(r["quantity"]) for r in tables["sales"])
    expected_refunds = sum(int(r["quantity"]) for r in tables["return_events"] if r["status"] == "refunded")
    assert sum(r["value"] * r["sample_size"] for r in returns) == pytest.approx(expected_refunds)
    assert all(set(r["segment"]) == {"demand_bucket", "category", "channel"} for r in [*zero,*returns])


def test_closed_segment_is_unknown_and_small_samples_are_not_evaluable():
    from datetime import date
    config = DatasetGenerationConfig(profile="ai-smoke", days=1, products=1, stores=1, warehouses=1,end_date=date(2026,7,5))
    report = build_source_realism(config.profile, config.seed, build_dataset(config))
    zero = next(r for r in report["metrics"] if r["metric_id"].startswith("open_panel_zero_rate:"))
    assert zero["sample_size"] == 0 and zero["value"] is None and zero["status"] == "not_evaluable"
    basket = next(r for r in report["metrics"] if r["metric_id"] == "average_distinct_order_items")
    assert basket["value"] is None and basket["status"] == "not_evaluable"


def test_historical_source_2_4_and_feature_3_0_keep_exact_identity(tmp_path):
    with ZipFile(ROOT / "services/api/tests/fixtures/source_manifest_v2_4.zip") as archive:
        for name in archive.namelist():
            assert Path(name).name == name
            (tmp_path / name).write_bytes(archive.read(name))
    source = load_source_manifest_v2(tmp_path)
    features = load_feature_identity_manifest(tmp_path)
    assert source["dataset_id"] == "source-sha256-d6562b0397df3a18a45c9fe419910f11b086c99cfd498b5d55881f2d67e81e2c"
    assert features["dataset_id"] == "features-sha256-daf83f0b54c4ba8901bc6fd0050735c35614c1ba800cdfcbe418d0484e52f6db"
    assert features["descriptor"]["parent_ids"] == [source["dataset_id"]]
