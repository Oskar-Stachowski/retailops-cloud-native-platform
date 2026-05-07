from __future__ import annotations

from decimal import Decimal

import pytest

from data.generator.main import (
    DatasetGenerationConfig,
    build_dataset,
    config_from_args,
    validate_generation_config,
)
from data.generator.manifest import build_dataset_manifest
from data.generator.quality import build_quality_report
from data.generator.realism_report import build_realism_report


class Args:
    profile = "demo"
    days = 14
    products = 20
    stores = 4
    warehouses = 4
    seed = 42


def test_config_from_args_maps_cli_options() -> None:
    config = config_from_args(Args)

    assert config == DatasetGenerationConfig(
        profile="demo",
        days=14,
        products=20,
        stores=4,
        warehouses=4,
        seed=42,
    )


def test_demo_profile_accepts_positive_scaling_options() -> None:
    config = DatasetGenerationConfig(
        profile="demo",
        days=14,
        products=20,
        stores=4,
        warehouses=4,
        seed=42,
    )

    validate_generation_config(config)


def test_demo_profile_keeps_current_dataset_shape() -> None:
    tables = build_dataset(DatasetGenerationConfig(profile="demo"))

    assert len(tables["products"]) == 8
    assert len(tables["users"]) == 4
    assert len(tables["stores"]) == 4
    assert len(tables["warehouses"]) == 4
    assert len(tables["orders"]) == 16
    assert len(tables["order_items"]) == 16
    assert len(tables["price_history"]) == 24
    assert len(tables["promotions"]) == 8
    assert len(tables["stock_movements"]) == 24
    assert len(tables["returns"]) == 4
    assert len(tables["sales"]) == 16
    assert len(tables["inventory_snapshots"]) == 8
    assert len(tables["forecasts"]) == 6
    assert len(tables["anomalies"]) == 4
    assert len(tables["alerts"]) == 4
    assert len(tables["recommendations"]) == 4
    assert len(tables["workflow_actions"]) == 4


def test_demo_profile_generates_store_and_warehouse_dimensions() -> None:
    tables = build_dataset(DatasetGenerationConfig(profile="demo"))

    store_codes = {store["store_code"] for store in tables["stores"]}
    warehouse_codes = {
        warehouse["warehouse_code"] for warehouse in tables["warehouses"]
    }

    assert store_codes == {
        "WAW-STORE-01",
        "GDN-STORE-01",
        "KRK-STORE-01",
        "BER-MKT-01",
    }
    assert warehouse_codes == {"WAW-01", "GDN-01", "KRK-01", "POZ-01"}
    assert {store["status"] for store in tables["stores"]} == {"active"}
    assert {warehouse["status"] for warehouse in tables["warehouses"]} == {
        "active"
    }


def test_demo_profile_generates_orders_and_order_items_from_sales() -> None:
    tables = build_dataset(DatasetGenerationConfig(profile="demo"))

    sales_by_reference = {
        sale["order_reference"]: sale for sale in tables["sales"]
    }
    orders_by_reference = {
        order["order_reference"]: order for order in tables["orders"]
    }
    order_items_by_order_id = {
        order_item["order_id"]: order_item
        for order_item in tables["order_items"]
    }
    store_ids = {store["id"] for store in tables["stores"]}

    assert set(orders_by_reference) == set(sales_by_reference)

    for order_reference, order in orders_by_reference.items():
        sale = sales_by_reference[order_reference]
        order_item = order_items_by_order_id[order["id"]]

        assert order["store_id"] in store_ids
        assert order["status"] == "completed"
        assert order["order_total"] == sale["total_amount"]
        assert order["currency"] == sale["currency"]
        assert order["ordered_at"] == sale["sold_at"]
        assert order_item["product_id"] == sale["product_id"]
        assert order_item["quantity"] == sale["quantity"]
        assert order_item["total_amount"] == sale["total_amount"]


def test_demo_profile_generates_price_history_and_promotions() -> None:
    tables = build_dataset(DatasetGenerationConfig(profile="demo"))

    product_ids = {product["id"] for product in tables["products"]}
    price_history_by_product: dict[str, list[dict[str, str]]] = {
        product_id: [] for product_id in product_ids
    }

    for price_point in tables["price_history"]:
        assert price_point["product_id"] in product_ids
        assert float(price_point["price"]) > 0
        assert price_point["currency"] == "PLN"
        assert price_point["price_type"] in {"regular", "planned"}
        if price_point["valid_to"]:
            assert price_point["valid_from"] <= price_point["valid_to"]
        price_history_by_product[price_point["product_id"]].append(
            price_point
        )

    assert {
        len(product_price_history)
        for product_price_history in price_history_by_product.values()
    } == {3}

    promotion_codes = set()
    for promotion in tables["promotions"]:
        assert promotion["product_id"] in product_ids
        assert promotion["promotion_code"] not in promotion_codes
        assert promotion["promotion_type"] == "discount"
        assert float(promotion["discount_percent"]) > 0
        assert promotion["starts_at"] <= promotion["ends_at"]
        assert promotion["status"] == "active"
        promotion_codes.add(promotion["promotion_code"])


def test_demo_profile_generates_stock_movements() -> None:
    tables = build_dataset(DatasetGenerationConfig(profile="demo"))

    product_ids = {product["id"] for product in tables["products"]}
    warehouse_ids = {warehouse["id"] for warehouse in tables["warehouses"]}
    movement_types = {
        movement["movement_type"] for movement in tables["stock_movements"]
    }

    assert movement_types == {"initial_stock", "sale"}

    for movement in tables["stock_movements"]:
        assert movement["product_id"] in product_ids
        assert movement["warehouse_id"] in warehouse_ids
        assert movement["warehouse_code"]
        assert movement["source_reference"]
        assert movement["occurred_at"]
        if movement["movement_type"] == "initial_stock":
            assert int(movement["quantity"]) >= 0
        if movement["movement_type"] == "sale":
            assert int(movement["quantity"]) < 0


def test_demo_profile_generates_returns_from_order_items() -> None:
    tables = build_dataset(DatasetGenerationConfig(profile="demo"))

    order_ids = {order["id"] for order in tables["orders"]}
    order_item_by_id = {
        order_item["id"]: order_item for order_item in tables["order_items"]
    }
    product_ids = {product["id"] for product in tables["products"]}

    for returned_item in tables["returns"]:
        order_item = order_item_by_id[returned_item["order_item_id"]]

        assert returned_item["order_id"] in order_ids
        assert returned_item["product_id"] in product_ids
        assert returned_item["product_id"] == order_item["product_id"]
        assert int(returned_item["quantity"]) > 0
        assert int(returned_item["quantity"]) <= int(order_item["quantity"])
        assert float(returned_item["refund_amount"]) > 0
        assert returned_item["currency"] == order_item["currency"]
        assert returned_item["reason"] == "customer_return"
        assert returned_item["status"] == "received"


@pytest.mark.parametrize(
    "config",
    [
        DatasetGenerationConfig(days=0),
        DatasetGenerationConfig(products=-1),
        DatasetGenerationConfig(stores=0),
        DatasetGenerationConfig(warehouses=-2),
        DatasetGenerationConfig(seed=0),
    ],
)
def test_generation_config_rejects_non_positive_numeric_options(
    config: DatasetGenerationConfig,
) -> None:
    with pytest.raises(ValueError, match="positive integers"):
        validate_generation_config(config)


@pytest.mark.parametrize("profile", ["small", "medium", "large"])
def test_non_demo_profiles_can_generate_scaled_datasets_with_overrides(
    profile: str,
) -> None:
    tables = build_dataset(
        DatasetGenerationConfig(
            profile=profile,
            days=3,
            products=5,
            stores=2,
            warehouses=2,
        )
    )

    assert len(tables["products"]) == 5
    assert len(tables["stores"]) == 2
    assert len(tables["warehouses"]) == 2
    assert len(tables["orders"]) == 15
    assert len(tables["sales"]) >= 15
    assert len(tables["order_items"]) == len(tables["sales"])
    assert len(tables["price_history"]) == 15
    assert len(tables["promotions"]) == 5
    assert len(tables["inventory_snapshots"]) == 5
    assert len(tables["stock_movements"]) >= 5 + len(tables["sales"])
    assert len(tables["returns"]) >= 0
    assert len(tables["anomalies"]) == 5
    assert len(tables["alerts"]) == 5
    assert len(tables["recommendations"]) == 5
    assert len(tables["workflow_actions"]) == 5

    assert {
        product["demand_class"] for product in tables["products"]
    }
    assert any(sale["latent_demand"] for sale in tables["sales"])
    assert any(sale["observed_sales"] for sale in tables["sales"])
    assert any(
        sale["promotion_applied"] == "true" for sale in tables["sales"]
    ) or len(tables["sales"]) >= 15


def test_synthetic_profile_generation_is_deterministic_for_seed() -> None:
    config = DatasetGenerationConfig(
        profile="small",
        days=5,
        products=8,
        stores=3,
        warehouses=2,
        seed=123,
    )

    first = build_dataset(config)
    second = build_dataset(config)

    assert first["products"] == second["products"]
    assert first["sales"] == second["sales"]
    assert first["returns"] == second["returns"]


def test_realism_report_summarizes_synthetic_profile() -> None:
    config = DatasetGenerationConfig(
        profile="small",
        days=14,
        products=20,
        stores=4,
        warehouses=3,
        seed=42,
    )
    tables = build_dataset(config)
    report = build_realism_report(config.profile, config.seed, tables)
    metrics = report["realism_metrics"]

    assert report["profile"] == "small"
    assert report["seed"] == 42
    assert report["row_counts"]["products"] == 20
    assert Decimal(metrics["average_order_items"]) > Decimal("1.0")
    assert Decimal(metrics["top_20_percent_product_revenue_share"]) > 0
    assert "data_quality_status_counts" in metrics
    assert "demand_class_counts" in metrics


def test_dataset_manifest_summarizes_demo_dataset() -> None:
    config = DatasetGenerationConfig(profile="demo")
    tables = build_dataset(config)
    manifest = build_dataset_manifest(config, tables)

    assert manifest["dataset_name"] == "retailops-synthetic"
    assert manifest["profile"] == "demo"
    assert manifest["schema_version"] == "1.0"
    assert manifest["seed"] == 42
    assert manifest["formats"] == ["csv"]
    assert manifest["row_counts"]["products"] == 8
    assert manifest["row_counts"]["sales"] == 16
    assert "dataset_manifest.json" in manifest["artifacts"]
    assert "quality_report.json" in manifest["artifacts"]
    assert "realism_report.json" not in manifest["artifacts"]


def test_dataset_manifest_includes_realism_report_for_synthetic_profile() -> None:
    config = DatasetGenerationConfig(
        profile="small",
        days=3,
        products=5,
        stores=2,
        warehouses=2,
    )
    tables = build_dataset(config)
    manifest = build_dataset_manifest(config, tables)

    assert manifest["profile"] == "small"
    assert manifest["parameters"] == {
        "days": 3,
        "products": 5,
        "stores": 2,
        "warehouses": 2,
    }
    assert manifest["row_counts"]["products"] == 5
    assert manifest["row_counts"]["orders"] == 15
    assert "dataset_manifest.json" in manifest["artifacts"]
    assert "quality_report.json" in manifest["artifacts"]
    assert "realism_report.json" in manifest["artifacts"]
    assert manifest["date_start"] <= manifest["date_end"]


def test_quality_report_passes_for_demo_dataset() -> None:
    config = DatasetGenerationConfig(profile="demo")
    tables = build_dataset(config)
    report = build_quality_report(config.profile, tables)

    assert report["status"] == "passed"
    assert report["summary"]["failed"] == 0
    assert report["row_counts"]["products"] == 8


def test_quality_report_passes_for_synthetic_profile() -> None:
    config = DatasetGenerationConfig(
        profile="small",
        days=14,
        products=20,
        stores=4,
        warehouses=3,
    )
    tables = build_dataset(config)
    report = build_quality_report(config.profile, tables)

    assert report["status"] == "passed"
    assert report["summary"]["failed"] == 0
    assert report["row_counts"]["orders"] == 280
    assert report["row_counts"]["sales"] == report["row_counts"]["order_items"]
