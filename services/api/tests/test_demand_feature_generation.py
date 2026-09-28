from __future__ import annotations

import csv
import json

import pytest

from data.generator.main import DatasetGenerationConfig, build_dataset
from ml.features.demand_forecast import (
    FEATURE_FILENAME,
    GRAIN,
    MANIFEST_FILENAME,
    TARGET,
    DemandFeatureGenerationConfig,
    build_demand_feature_rows,
    build_feature_manifest,
    generate_demand_feature_dataset,
)


def test_demand_feature_rows_follow_contract_grain_and_target() -> None:
    config = DatasetGenerationConfig(profile="demo")
    tables = build_dataset(config)
    rows = build_demand_feature_rows(tables, config)

    assert rows
    assert len(rows) <= len(tables["sales"])

    first = rows[0]
    assert first["schema_version"] == "2.0"
    assert first["dataset_id"].startswith("features-sha256-")
    assert first["feature_row_id"] == ":".join(str(first[field]) for field in GRAIN)
    assert first[TARGET] >= 0
    assert first["observation_status"] == "observed_positive"
    assert (
        not {"latent_units_demand", "unit_price", "promotion_active", "inventory_on_hand"}
        & first.keys()
    )


def test_demand_feature_generation_aggregates_duplicate_grain_rows() -> None:
    config = DatasetGenerationConfig(profile="demo")
    tables = build_dataset(config)
    sale = tables["sales"][0]
    duplicate_sale = {
        **sale,
        "id": "duplicate-sale",
        "quantity": "2",
        "total_amount": "20.00",
        "unit_price": "10.00",
        "latent_demand": "3",
    }
    tables["sales"] = [sale, duplicate_sale, *tables["sales"][1:]]

    rows = build_demand_feature_rows(tables, config)
    order = next(
        order for order in tables["orders"] if order["order_reference"] == sale["order_reference"]
    )
    matching_row = next(
        row
        for row in rows
        if row["date"] == sale["sold_at"][:10]
        and row["product_id"] == sale["product_id"]
        and row["store_id"] == order["store_id"]
        and row["channel"] == sale["channel"]
    )

    assert matching_row["units_sold"] == int(sale["quantity"]) + 2
    assert matching_row["observation_status"] == "observed_positive"


def test_aggregate_availability_uses_latest_contributing_sale() -> None:
    config = DatasetGenerationConfig(profile="demo")
    tables = build_dataset(config)
    sale = tables["sales"][0]
    tables["sales"] = [
        sale,
        {**sale, "id": "late-sale", "ingested_at": "2099-01-01T12:00:00+00:00"},
    ]

    rows = build_demand_feature_rows(tables, config)

    assert len(rows) == 1
    assert rows[0]["observation_available_at"] == "2099-01-01T12:00:00+00:00"


def test_explicit_zero_sale_is_distinct_from_missing_sale() -> None:
    config = DatasetGenerationConfig(profile="demo")
    tables = build_dataset(config)
    sale = {**tables["sales"][0], "quantity": "0"}
    tables["sales"] = [sale]

    rows = build_demand_feature_rows(tables, config)
    assert len(rows) == 1
    assert rows[0]["units_sold"] == 0
    assert rows[0]["observation_status"] == "observed_zero"

    tables["sales"] = []
    assert build_demand_feature_rows(tables, config) == []

    tables["sales"] = [{**sale, "quantity": ""}]
    with pytest.raises(ValueError, match="unknown is not zero"):
        build_demand_feature_rows(tables, config)


def test_feature_rows_do_not_use_same_day_outcomes_or_unmapped_inventory() -> None:
    config = DatasetGenerationConfig(profile="small", days=5, products=6, stores=2, warehouses=2)
    tables = build_dataset(config)
    before = build_demand_feature_rows(tables, config)
    tables["price_history"] = []
    tables["promotions"] = []
    tables["inventory_snapshots"] = []
    tables["sales"][0] = {
        **tables["sales"][0],
        "total_amount": "999999.00",
        "latent_demand": "999999",
        "stockout_flag": "true",
        "promotion_applied": "true",
    }
    after = build_demand_feature_rows(tables, config)

    assert before[0]["dataset_id"] != after[0]["dataset_id"]
    assert [{k: v for k, v in row.items() if k != "dataset_id"} for row in before] == [
        {k: v for k, v in row.items() if k != "dataset_id"} for row in after
    ]

    tables["sales"][0]["quantity"] = str(int(tables["sales"][0]["quantity"]) + 100)
    changed_label = build_demand_feature_rows(tables, config)
    origin_fields = build_feature_manifest(config, before)["available_at_origin_fields"]
    assert [row["feature_row_id"] for row in before] == [
        row["feature_row_id"] for row in changed_label
    ]
    assert any(
        old["units_sold"] != new["units_sold"]
        for old, new in zip(before, changed_label, strict=True)
    )
    assert all(
        all(old[field] == new[field] for field in origin_fields)
        for old, new in zip(before, changed_label, strict=True)
    )


def test_demand_feature_manifest_describes_generated_rows() -> None:
    config = DatasetGenerationConfig(
        profile="small",
        days=3,
        products=5,
        stores=2,
        warehouses=2,
        seed=123,
    )
    tables = build_dataset(config)
    rows = build_demand_feature_rows(tables, config)
    manifest = build_feature_manifest(config, rows)

    assert manifest["dataset_name"] == "retailops-demand-forecast-features"
    assert manifest["profile"] == "small"
    assert manifest["grain"] == GRAIN
    assert manifest["target"] == TARGET
    assert manifest["row_count"] == len(rows)
    assert manifest["seed"] == 123
    assert manifest["date_start"] <= manifest["date_end"]
    assert "sales.csv" in manifest["source_artifacts"]
    assert manifest["forecast_origin_rule"] == "previous_day_end_utc"
    assert manifest["observation_availability_field"] == "observation_available_at"
    assert manifest["inventory_ready"] is False
    assert manifest["complete_daily_panel"] is False


def test_demand_feature_job_writes_csv_and_manifest(tmp_path) -> None:
    config = DemandFeatureGenerationConfig(
        dataset=DatasetGenerationConfig(
            profile="small",
            days=3,
            products=5,
            stores=2,
            warehouses=2,
            seed=42,
        ),
        output_dir=tmp_path,
    )

    manifest = generate_demand_feature_dataset(config)
    rows = list(csv.DictReader((tmp_path / FEATURE_FILENAME).open(encoding="utf-8")))
    written_manifest = json.loads((tmp_path / MANIFEST_FILENAME).read_text(encoding="utf-8"))

    assert rows
    assert len(rows) == manifest["row_count"]
    assert written_manifest["dataset_id"] == manifest["dataset_id"]
    assert rows[0]["dataset_id"] == manifest["dataset_id"]
