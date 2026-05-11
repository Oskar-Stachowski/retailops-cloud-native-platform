from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from data.generator.csv_writer import CSV_WRITE_ORDER, write_tables
from data.generator.forecasts import generate_forecasts
from data.generator.incidents import generate_incident_dataset
from data.generator.inventory import generate_inventory_snapshots
from data.generator.locations import generate_stores, generate_warehouses
from data.generator.manifest import write_dataset_manifest
from data.generator.orders import generate_order_items, generate_orders
from data.generator.pricing import generate_price_history, generate_promotions
from data.generator.products import generate_products
from data.generator.profile_engine import (
    build_profile_dataset,
    profile_defaults,
)
from data.generator.quality import write_quality_report
from data.generator.realism_report import write_realism_report
from data.generator.sales import generate_sales
from data.generator.stock import generate_returns, generate_stock_movements
from data.generator.users import generate_users

SUPPORTED_PROFILES = ("demo", "small", "medium", "large")


@dataclass(frozen=True)
class DatasetGenerationConfig:
    profile: str = "demo"
    days: int | None = None
    products: int | None = None
    stores: int | None = None
    warehouses: int | None = None
    seed: int = 42


def build_demo_dataset() -> dict[str, list[dict[str, str]]]:
    products = generate_products()
    users = generate_users()
    stores = generate_stores()
    warehouses = generate_warehouses()
    sales = generate_sales(products)
    orders = generate_orders(sales, stores)
    order_items = generate_order_items(sales, orders)
    price_history = generate_price_history(products)
    promotions = generate_promotions(products)
    inventory_snapshots = generate_inventory_snapshots(products)
    stock_movements = generate_stock_movements(
        inventory_snapshots,
        sales,
        warehouses,
    )
    returns = generate_returns(order_items, orders)
    forecasts = generate_forecasts(products)
    incidents = generate_incident_dataset(products, forecasts, users)

    return {
        "products": products,
        "users": users,
        "stores": stores,
        "warehouses": warehouses,
        "orders": orders,
        "order_items": order_items,
        "price_history": price_history,
        "promotions": promotions,
        "stock_movements": stock_movements,
        "returns": returns,
        "sales": sales,
        "inventory_snapshots": inventory_snapshots,
        "forecasts": forecasts,
        **incidents,
    }


def default_output_dir() -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "data" / "demo"


def default_output_dir_for_profile(profile: str) -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    if profile == "demo":
        return repo_root / "data" / "demo"

    return repo_root / "data" / "synthetic" / profile


def validate_generation_config(config: DatasetGenerationConfig) -> None:
    if config.profile not in SUPPORTED_PROFILES:
        supported = ", ".join(SUPPORTED_PROFILES)
        msg = f"Unsupported dataset profile '{config.profile}'. Supported profiles: {supported}."
        raise ValueError(
            msg,
        )

    numeric_options = {
        "days": config.days,
        "products": config.products,
        "stores": config.stores,
        "warehouses": config.warehouses,
        "seed": config.seed,
    }
    invalid_options = [
        name for name, value in numeric_options.items() if value is not None and value <= 0
    ]

    if invalid_options:
        raise ValueError(
            "Dataset generation options must be positive integers: " + ", ".join(invalid_options),
        )


def warn_if_demo_ignores_sizing_options(config: DatasetGenerationConfig) -> None:
    if config.profile != "demo":
        return

    ignored_options = [
        name
        for name, value in {
            "days": config.days,
            "products": config.products,
            "stores": config.stores,
            "warehouses": config.warehouses,
        }.items()
        if value is not None
    ]

    if not ignored_options:
        return

    ignored = ", ".join(f"--{name}" for name in ignored_options)
    print(  # noqa: T201 - CLI warning output
        "Warning: the demo profile is fixed-size. "
        f"Ignoring sizing option(s): {ignored}. "
        "Use --profile small, medium, or large for bounded sizing overrides.",
        file=sys.stderr,
    )


def build_dataset(
    config: DatasetGenerationConfig | None = None,
) -> dict[str, list[dict[str, str]]]:
    config = config or DatasetGenerationConfig()
    validate_generation_config(config)
    if config.profile == "demo":
        return build_demo_dataset()

    defaults = profile_defaults(config.profile)
    days = config.days or defaults.days
    product_count = config.products or defaults.products
    store_count = config.stores or defaults.stores
    warehouse_count = config.warehouses or defaults.warehouses

    return build_profile_dataset(
        profile=config.profile,
        days=days,
        product_count=product_count,
        store_count=store_count,
        warehouse_count=warehouse_count,
        seed=config.seed,
    )


def generate_demo_dataset(
    output_dir: Path | None = None,
    config: DatasetGenerationConfig | None = None,
) -> dict[str, int]:
    config = config or DatasetGenerationConfig()
    output_dir = output_dir or default_output_dir_for_profile(config.profile)
    tables = build_dataset(config)
    counts = write_tables(output_dir, tables)
    write_quality_report(output_dir, config.profile, tables)
    write_dataset_manifest(output_dir, config, tables)
    if config.profile != "demo":
        write_realism_report(output_dir, config.profile, config.seed, tables)
    return counts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate RetailOps synthetic CSV dataset.")
    parser.add_argument(
        "--profile",
        choices=SUPPORTED_PROFILES,
        default="demo",
        help="Dataset profile to generate.",
    )
    parser.add_argument(
        "--days",
        type=int,
        help="Number of historical business days to generate.",
    )
    parser.add_argument(
        "--products",
        type=int,
        help="Number of products to generate.",
    )
    parser.add_argument(
        "--stores",
        type=int,
        help="Number of stores or selling locations to generate.",
    )
    parser.add_argument(
        "--warehouses",
        type=int,
        help="Number of warehouses to generate.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Deterministic generation seed reserved for scalable profiles.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory where CSV files should be written.",
    )

    return parser.parse_args()


def config_from_args(args: argparse.Namespace) -> DatasetGenerationConfig:
    return DatasetGenerationConfig(
        profile=args.profile,
        days=args.days,
        products=args.products,
        stores=args.stores,
        warehouses=args.warehouses,
        seed=args.seed,
    )


def main() -> None:
    args = parse_args()
    config = config_from_args(args)
    warn_if_demo_ignores_sizing_options(config)

    counts = generate_demo_dataset(args.output_dir, config)
    output_dir = args.output_dir or default_output_dir_for_profile(
        config.profile,
    )

    print(f"RetailOps CSV dataset generated for profile '{config.profile}':")  # noqa: T201 - CLI output
    for table_name in CSV_WRITE_ORDER:
        print(f"- {table_name}: {counts[table_name]}")  # noqa: T201 - CLI output
    print(f"\nOutput directory: {output_dir}")  # noqa: T201 - CLI output


if __name__ == "__main__":
    main()
