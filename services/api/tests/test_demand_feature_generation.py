from __future__ import annotations

import csv
import json

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
    assert first["schema_version"] == "1.0"
    assert first["dataset_id"].startswith("retailops-demand-forecast-features-demo-")
    assert first["feature_row_id"] == ":".join(str(first[field]) for field in GRAIN)
    assert first[TARGET] >= 0
    assert first["sales_revenue"] != ""
    assert first["unit_price"] != ""
    assert first["promotion_type"] in {
        "none",
        "percentage_discount",
        "bundle",
        "clearance",
        "seasonal",
    }
    assert first["data_quality_status"] in {"passed", "warning", "failed"}


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
        order
        for order in tables["orders"]
        if order["order_reference"] == sale["order_reference"]
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
    assert matching_row["latent_units_demand"] >= matching_row["units_sold"]


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
