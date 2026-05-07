from __future__ import annotations

import pytest

from data.generator.main import (
    DatasetGenerationConfig,
    build_dataset,
    config_from_args,
    validate_generation_config,
)


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
def test_non_demo_profiles_are_reserved_for_future_commits(
    profile: str,
) -> None:
    with pytest.raises(NotImplementedError, match="Only the 'demo'"):
        validate_generation_config(DatasetGenerationConfig(profile=profile))
