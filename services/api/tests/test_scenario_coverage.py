from __future__ import annotations

from data.generator.main import DatasetGenerationConfig, build_dataset


def values(rows: list[dict[str, str]], column: str) -> set[str]:
    return {row[column] for row in rows if row.get(column)}


def test_demo_incident_dataset_covers_required_operational_scenarios() -> None:
    tables = build_dataset(DatasetGenerationConfig(profile="demo"))

    anomaly_types = values(tables["anomalies"], "anomaly_type")
    alert_types = values(tables["alerts"], "alert_type")
    recommendation_types = values(tables["recommendations"], "recommendation_type")
    recommendation_rationales = values(tables["recommendations"], "rationale")

    assert {"sales_drop", "sales_spike", "stale_inventory"}.issubset(anomaly_types)
    assert {"sales_drop", "stockout_risk", "overstock_risk"}.issubset(alert_types)
    assert "replenish_stock" in recommendation_types
    assert "stockout_risk" in recommendation_rationales


def test_demo_dataset_includes_missing_forecast_context() -> None:
    tables = build_dataset(DatasetGenerationConfig(profile="demo"))

    product_ids = values(tables["products"], "id")
    forecast_product_ids = values(tables["forecasts"], "product_id")

    assert product_ids - forecast_product_ids
