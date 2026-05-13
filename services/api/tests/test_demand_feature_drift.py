from __future__ import annotations

import json
from decimal import Decimal

from data.generator.main import DatasetGenerationConfig, build_dataset
from ml.drift.demand_feature_drift import (
    DRIFT_REPORT_FILENAME,
    DRIFT_SUMMARY_FILENAME,
    DemandFeatureDriftConfig,
    build_drift_report,
    generate_demand_feature_drift_report,
)
from ml.features.demand_forecast import build_demand_feature_rows


def test_drift_report_passes_when_reference_and_current_features_match() -> None:
    dataset = DatasetGenerationConfig(
        profile="small",
        days=4,
        products=5,
        stores=2,
        warehouses=2,
        seed=42,
    )
    rows = build_demand_feature_rows(build_dataset(dataset), dataset)
    report = build_drift_report(
        DemandFeatureDriftConfig(
            dataset=dataset,
            reference_seed=42,
            current_seed=42,
        ),
        rows,
        rows,
    )

    assert report["status"] == "passed"
    assert report["failed_check_count"] == 0
    assert report["warning_check_count"] == 0
    assert report["reference_dataset_id"] == report["current_dataset_id"]


def test_drift_report_flags_numeric_and_categorical_changes() -> None:
    dataset = DatasetGenerationConfig(profile="small", seed=42)
    reference_rows = [
        {
            "dataset_id": "reference",
            "units_sold": 10,
            "latent_units_demand": 10,
            "sales_revenue": "100.00",
            "unit_price": "10.00",
            "discount_percent": "0.0000",
            "inventory_on_hand": 20,
            "inventory_reserved": 0,
            "channel": "online",
            "promotion_active": False,
            "promotion_type": "none",
            "stockout_flag": False,
            "category": "apparel",
            "brand": "brand-a",
            "product_status": "active",
            "day_of_week": 1,
            "is_weekend": False,
            "month": 5,
            "data_quality_status": "passed",
        }
        for _ in range(4)
    ]
    current_rows = [
        {
            **row,
            "dataset_id": "current",
            "units_sold": 20,
            "latent_units_demand": 22,
            "sales_revenue": "220.00",
            "channel": "store",
        }
        for row in reference_rows
    ]

    report = build_drift_report(
        DemandFeatureDriftConfig(
            dataset=dataset,
            warning_threshold=Decimal("0.1000"),
            failure_threshold=Decimal("0.2500"),
        ),
        reference_rows,
        current_rows,
    )

    failed_checks = {
        check["check_name"] for check in report["checks"] if check["status"] == "failed"
    }

    assert report["status"] == "failed"
    assert "units_sold_mean_relative_change" in failed_checks
    assert "channel_max_bucket_share_delta" in failed_checks


def test_drift_job_writes_report_and_summary(tmp_path) -> None:
    config = DemandFeatureDriftConfig(
        dataset=DatasetGenerationConfig(
            profile="small",
            days=4,
            products=5,
            stores=2,
            warehouses=2,
            seed=42,
        ),
        reference_seed=42,
        current_seed=43,
        output_dir=tmp_path,
    )

    report = generate_demand_feature_drift_report(config)
    written_report = json.loads((tmp_path / DRIFT_REPORT_FILENAME).read_text(encoding="utf-8"))
    summary = (tmp_path / DRIFT_SUMMARY_FILENAME).read_text(encoding="utf-8")

    assert written_report["report_name"] == "retailops-demand-feature-drift"
    assert written_report["status"] == report["status"]
    assert written_report["check_count"] > 0
    assert "# RetailOps Demand Feature Drift" in summary
