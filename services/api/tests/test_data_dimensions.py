from __future__ import annotations

import copy
import json
from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path
from zipfile import ZipFile

import pytest

from data.generator.business_calendar import calendar_attributes, day_bounds, holiday_dates
from data.generator.configuration import DatasetGenerationConfig, resolve_generation_config
from data.generator.csv_writer import CSV_WRITE_ORDER, write_tables
from data.generator.return_schema import RETURN_COLUMNS
from data.generator.demand_schema import DEMAND_COLUMNS
from data.generator.dimension_contract import dimension_contract_schema
from data.generator.dimension_quality import build_dimensions_report, validate_dimensions
from data.generator.dimension_schema import DIMENSION_COLUMNS
from data.generator.dimensions import DimensionIndex, in_period, resolve_version
from data.generator.main import build_dataset, generate_demo_dataset
from data.generator.manifest_v2 import build_source_manifest_v2, load_source_manifest_v2
from data.generator.pricing_schema import PRICING_COLUMNS
from ml.features.demand_forecast import FEATURE_COLUMNS, build_demand_feature_rows
from ml.features.identity import load_feature_identity_manifest

ROOT = Path(__file__).resolve().parents[3]
CONFIG = DatasetGenerationConfig(profile="ai-smoke")


@pytest.fixture(scope="module")
def dimensions():
    return build_dataset(CONFIG)


def test_catalog_separates_brands_categories_locations_and_channels(dimensions):
    assert set(dimensions) == set(CSV_WRITE_ORDER) | set(DIMENSION_COLUMNS) | set(PRICING_COLUMNS) | set(DEMAND_COLUMNS) | set(RETURN_COLUMNS)
    report = validate_dimensions(dimensions, resolve_generation_config(CONFIG))
    assert len(report["checks"]) == 8
    assert all(c["severity"] == "hard" and c["status"] == "passed" for c in report["checks"])
    assert report["active_daily_combinations"] < report["nominal_daily_grid"] == 1800
    assert report["observation_panel_status"] == "not_ready"
    assert report["inventory_ready"] is False
    categories = {r["id"]: r for r in dimensions["catalog_categories"]}
    brands = {}
    for product in dimensions["product_catalog"]:
        brands.setdefault(product["category_id"], set()).add(product["brand"])
        assert product["brand"] != categories[product["category_id"]]["name"]
        if categories[product["category_id"]]["name"] == "Pet Care":
            assert product["sku"].startswith("PETC-")
            assert " " not in product["sku"]
    assert any(len(values) > 1 for values in brands.values())
    pairs = {(r["selling_location_id"], r["channel"]) for r in dimensions["channel_assignments"]}
    assert len(pairs) == 3
    assert len(dimensions["selling_locations"]) == 2
    assert {r["country_code"] for r in dimensions["selling_locations"]} == {"PL", "DE"}
    assert not {r["id"] for r in dimensions["selling_locations"]} & {
        r["id"] for r in dimensions["stock_locations"]
    }
    assert {r["id"] for r in dimensions["products"]} == {
        r["id"] for r in dimensions["product_catalog"]
    }


def test_temporal_versions_have_exclusive_ends_known_at_cutoff_and_no_fallback(dimensions):
    rows = dimensions["fulfillment_routes"][:2]
    first, second = rows
    assert first["effective_to"] == second["effective_from"]
    assert resolve_version(rows, first["effective_from"]) == first
    assert resolve_version(rows, first["effective_to"]) == second
    assert resolve_version(rows, second["effective_to"]) is None
    future = dict(second, available_at="2026-08-01T00:00:00+00:00")
    assert not in_period(future, second["effective_from"], "2026-07-31T23:59:59+00:00")
    assert in_period(future, second["effective_from"], "2026-08-01T02:00:00+02:00")
    with pytest.raises(ValueError, match="timezone"):
        in_period(first, first["effective_from"], "2026-07-31T00:00:00")
    with pytest.raises(ValueError, match="Ambiguous"):
        resolve_version([first, first], first["effective_from"])
    index = DimensionIndex(dimensions)
    assert index.route("unknown", "store", first["effective_from"]) is None
    assert (
        index.route(first["selling_location_id"], first["channel"], second["effective_to"]) is None
    )


def test_sales_use_only_open_assortment_and_lifecycle(dimensions):
    index = DimensionIndex(dimensions)
    orders = {r["order_reference"]: r for r in dimensions["orders"]}
    products = {r["id"]: r for r in dimensions["product_catalog"]}
    for sale in dimensions["sales"]:
        day = sale["sold_at"][:10]
        product = products[sale["product_id"]]
        assert day >= product["launch_date"]
        assert not product["discontinue_date"] or day < product["discontinue_date"]
        assert index.eligible(sale["product_id"], orders[sale["order_reference"]]["store_id"], day)


@pytest.mark.parametrize("timezone", ["Europe/Warsaw", "Europe/Berlin"])
@pytest.mark.parametrize("day,hours", [(date(2026, 3, 29), 23), (date(2026, 10, 25), 25)])
def test_local_dst_bounds_and_utc_business_day(timezone, day, hours):
    start, end = map(datetime.fromisoformat, day_bounds(day, timezone))
    assert end - start == timedelta(hours=hours)
    utc_start, utc_end = map(datetime.fromisoformat, day_bounds(day))
    assert utc_end - utc_start == timedelta(hours=24)


@pytest.mark.parametrize(
    "day,jurisdiction,holiday",
    [
        (date(2024, 12, 24), "PL", ""),
        (date(2025, 12, 24), "PL", "christmas_eve"),
        (date(2026, 4, 5), "PL", "easter_sunday"),
        (date(2026, 4, 6), "PL", "easter_monday"),
        (date(2026, 6, 4), "PL", "corpus_christi"),
        (date(2026, 4, 3), "DE-BE", "good_friday"),
        (date(2026, 5, 14), "DE-BE", "ascension"),
        (date(2026, 5, 25), "DE-BE", "whit_monday"),
        (date(2026, 3, 8), "DE-BE", "international_womens_day"),
        (date(2025, 5, 8), "DE-BE", "liberation_day_80"),
        (date(2026, 5, 8), "DE-BE", ""),
    ],
)
def test_frozen_country_and_one_off_holidays(day, jurisdiction, holiday):
    attributes = calendar_attributes(day, jurisdiction, "store", "2024-01-01T00:00:00+00:00")
    assert attributes["holiday_names"] == holiday
    assert attributes["is_public_holiday"] == str(bool(holiday)).lower()
    if holiday:
        assert attributes["location_open"] == "false"
    digital = calendar_attributes(day, jurisdiction, "online", "2024-01-01T00:00:00+00:00")
    assert digital["location_open"] == "true"
    if holiday == "christmas_eve":
        assert attributes["available_at"] == "2024-12-31T00:00:00+00:00"
    if holiday == "liberation_day_80":
        assert attributes["available_at"] == "2024-07-21T00:00:00+00:00"


def test_calendar_retail_events_and_fail_closed_policy():
    for day, field in [
        (date(2026, 11, 27), "is_black_friday"),
        (date(2026, 11, 30), "is_cyber_monday"),
    ]:
        assert (
            calendar_attributes(day, "PL", "online", "2026-01-01T00:00:00+00:00")[field] == "true"
        )
    for year, jurisdiction in [(2023, "PL"), (2028, "DE-BE"), (2026, "DE-BY")]:
        with pytest.raises(ValueError, match="2024-2027"):
            holiday_dates(year, jurisdiction)
    with pytest.raises(ValueError, match="Unsupported"):
        calendar_attributes(date(2026, 1, 1), "PL", "unknown", "2025-12-01T00:00:00+00:00")


@pytest.mark.parametrize(
    "table,field,value,check",
    [
        ("product_catalog", "brand", "Electronics", "catalog_lifecycle_assortment"),
        ("product_catalog", "status", "inactive", "catalog_lifecycle_assortment"),
        ("product_catalog", "available_at", "2026-07-01T00:00:00", "dimension_schema_pk_sku"),
        ("product_catalog", "sku", "PET -000001", "dimension_schema_pk_sku"),
        ("product_catalog", "unit_cost", "-1.00", "catalog_lifecycle_assortment"),
        ("product_catalog", "category_id", "unknown", "catalog_lifecycle_assortment"),
        (
            "product_catalog",
            "available_at",
            "2026-08-01T00:00:00+00:00",
            "catalog_lifecycle_assortment",
        ),
        ("catalog_categories", "department", "invalid", "catalog_lifecycle_assortment"),
        ("selling_locations", "region_code", "DE-South", "selling_stock_channel_region"),
        ("selling_locations", "business_timezone", "Europe/Warsaw", "selling_stock_channel_region"),
        ("fulfillment_routes", "stock_location_id", "unknown", "assignment_routing_versions"),
        (
            "fulfillment_routes",
            "available_at",
            "2026-08-01T00:00:00+00:00",
            "assignment_routing_versions",
        ),
        ("fulfillment_routes", "route_key", "unknown", "assignment_routing_versions"),
        ("channel_assignments", "effective_from", "2026-07-03", "calendar_exact_coverage"),
        ("business_calendar", "location_open", "unknown", "dimension_schema_pk_sku"),
        ("business_calendar", "is_public_holiday", "true", "calendar_exact_coverage"),
        (
            "business_calendar",
            "local_day_end_at",
            "2026-07-02T00:00:00+00:00",
            "calendar_exact_coverage",
        ),
        ("category_calendar", "calendar_version", "unknown", "category_season_coverage"),
        ("category_calendar", "is_category_season", "true", "category_season_coverage"),
        ("stores", "channel", "wholesale", "legacy_adapter_consistency"),
    ],
)
def test_dimension_hard_gates_reject_invalid_semantics(dimensions, table, field, value, check):
    broken = copy.deepcopy(dimensions)
    broken[table][0][field] = value
    report = build_dimensions_report(broken, resolve_generation_config(CONFIG))
    assert report["status"] == "failed"
    assert next(c for c in report["checks"] if c["check_id"] == check)["status"] == "failed"
    with pytest.raises(ValueError, match="hard gate"):
        validate_dimensions(broken, resolve_generation_config(CONFIG))


def test_missing_calendar_is_unknown_and_cannot_be_used_for_features(dimensions):
    broken = copy.deepcopy(dimensions)
    missing = broken["business_calendar"].pop(0)
    assignment = next(
        r for r in broken["channel_assignments"] if r["id"] == missing["assignment_id"]
    )
    with pytest.raises(ValueError, match="unknown"):
        DimensionIndex(broken).eligible(
            broken["product_catalog"][0]["id"],
            assignment["legacy_store_id"],
            missing["business_date"],
        )
    with pytest.raises(ValueError, match="hard gate"):
        build_demand_feature_rows(broken, CONFIG)


@pytest.mark.parametrize(
    "kind",
    [
        "sku",
        "primary_key",
        "route_gap",
        "overlap",
        "assortment_lifecycle",
        "closed_sale",
        "prelaunch_sale",
        "discontinued_sale",
    ],
)
def test_relational_and_sales_failures_are_blocked(dimensions, kind):
    broken = copy.deepcopy(dimensions)
    if kind == "sku":
        broken["product_catalog"][1]["sku"] = broken["product_catalog"][0]["sku"]
    elif kind == "primary_key":
        broken["stock_locations"][1]["id"] = broken["stock_locations"][0]["id"]
    elif kind == "route_gap":
        broken["fulfillment_routes"].pop(0)
    elif kind == "overlap":
        broken["fulfillment_routes"][1]["effective_from"] = broken["fulfillment_routes"][0][
            "effective_from"
        ]
    elif kind == "assortment_lifecycle":
        product = next(r for r in broken["product_catalog"] if r["launch_date"] > "2026-07-02")
        next(r for r in broken["assortment"] if r["product_id"] == product["id"])[
            "effective_from"
        ] = "2026-07-02"
    else:
        sale = broken["sales"][0]
        if kind == "closed_sale":
            sale["sold_at"] = "2026-07-05T12:00:00+00:00"
        else:
            product = next(
                r
                for r in broken["product_catalog"]
                if (
                    r["launch_date"] > "2026-07-02"
                    if kind == "prelaunch_sale"
                    else r["discontinue_date"]
                )
            )
            sale["product_id"] = product["id"]
            day = "2026-07-02" if kind == "prelaunch_sale" else product["discontinue_date"]
            sale["sold_at"] = day + "T12:00:00+00:00"
    assert build_dimensions_report(broken, resolve_generation_config(CONFIG))["status"] == "failed"


def test_recomputed_manifest_hashes_cannot_bypass_missing_calendar(tmp_path, dimensions):
    generate_demo_dataset(tmp_path, CONFIG)
    broken = copy.deepcopy(dimensions)
    broken["business_calendar"].pop()
    write_tables(tmp_path, broken)
    with pytest.raises(ValueError, match="hard gate"):
        build_source_manifest_v2(CONFIG, broken, tmp_path)


def test_new_source_includes_all_dimensions_and_mixed_versions_fail(tmp_path):
    generate_demo_dataset(tmp_path, CONFIG)
    manifest = load_source_manifest_v2(tmp_path)
    assert manifest["schema_version"] == "2.4.0"
    assert len(manifest["artifacts"]) == 37
    assert manifest["descriptor"]["versions"]["dimensions"] == "retail-dimensions-1.0.0"
    assert any(
        r["path"] == "dimensions_report.json" and r["status"] == "passed"
        for r in manifest["reports"]
    )
    manifest["descriptor"]["versions"]["generator"] = "0.2.0"
    from data.generator.manifest_v2 import SourceManifestV2

    with pytest.raises(ValueError, match="producer versions"):
        SourceManifestV2.model_validate(manifest)


def test_genuine_data01_export_remains_readable_without_identity_change(tmp_path):
    with ZipFile(Path(__file__).parent / "fixtures/source_manifest_v2_0.zip") as fixture:
        for name in fixture.namelist():
            assert Path(name).name == name
            (tmp_path / name).write_bytes(fixture.read(name))
    manifest = load_source_manifest_v2(tmp_path)
    assert manifest["schema_version"] == "2.0.0"
    assert (
        manifest["dataset_id"]
        == "source-sha256-b4d2a6cf560129ce23374841340e65897a7b09becbe4749e1352c3f150bc1309"
    )
    assert len(manifest["artifacts"]) == 17
    features = load_feature_identity_manifest(tmp_path, FEATURE_COLUMNS)
    assert (
        features["dataset_id"]
        == "features-sha256-bdb259d15fd67e0af15dbce1465ff480ae93421125bde83231b0bf5730a9db13"
    )
    assert features["descriptor"]["parent_ids"] == [manifest["dataset_id"]]


def test_committed_dimensions_schema_uses_runtime_field_rules():
    assert (
        json.loads((ROOT / "data/contracts/retail_dimensions.v1.schema.json").read_text())
        == dimension_contract_schema()
    )


def test_minimal_ai_profile_and_legacy_profiles_are_separate():
    config = replace(CONFIG, days=1, products=1, stores=1, warehouses=1)
    tables = build_dataset(config)
    assert validate_dimensions(tables, resolve_generation_config(config))["status"] == "passed"
    assert len(tables["business_calendar"]) == 1
    assert not set(DIMENSION_COLUMNS) & set(build_dataset(DatasetGenerationConfig()))
