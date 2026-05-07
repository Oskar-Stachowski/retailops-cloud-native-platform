from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from data.generator.csv_writer import CSV_WRITE_ORDER, write_tables
from data.generator.forecasts import generate_forecasts
from data.generator.incidents import generate_incident_dataset
from data.generator.inventory import generate_inventory_snapshots
from data.generator.locations import generate_stores, generate_warehouses
from data.generator.orders import generate_order_items, generate_orders
from data.generator.pricing import generate_price_history, generate_promotions
from data.generator.products import generate_products
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


def validate_generation_config(config: DatasetGenerationConfig) -> None:
    if config.profile not in SUPPORTED_PROFILES:
        supported = ", ".join(SUPPORTED_PROFILES)
        raise ValueError(
            f"Unsupported dataset profile '{config.profile}'. "
            f"Supported profiles: {supported}."
        )

    numeric_options = {
        "days": config.days,
        "products": config.products,
        "stores": config.stores,
        "warehouses": config.warehouses,
        "seed": config.seed,
    }
    invalid_options = [
        name
        for name, value in numeric_options.items()
        if value is not None and value <= 0
    ]

    if invalid_options:
        raise ValueError(
            "Dataset generation options must be positive integers: "
            + ", ".join(invalid_options)
        )

    if config.profile != "demo":
        raise NotImplementedError(
            "Only the 'demo' dataset profile is implemented in this sprint. "
            "The small, medium and large profiles are documented targets for "
            "future synthetic data generator commits."
        )


def build_dataset(
    config: DatasetGenerationConfig | None = None,
) -> dict[str, list[dict[str, str]]]:
    config = config or DatasetGenerationConfig()
    validate_generation_config(config)
    return build_demo_dataset()


def generate_demo_dataset(
    output_dir: Path | None = None,
    config: DatasetGenerationConfig | None = None,
) -> dict[str, int]:
    output_dir = output_dir or default_output_dir()
    tables = build_dataset(config)
    return write_tables(output_dir, tables)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate RetailOps synthetic CSV dataset."
    )
    parser.add_argument(
        "--profile",
        choices=SUPPORTED_PROFILES,
        default="demo",
        help=(
            "Dataset profile to generate. Only 'demo' is implemented for now; "
            "the remaining profiles are reserved for future commits."
        ),
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
        default=default_output_dir(),
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

    counts = generate_demo_dataset(args.output_dir, config)

    print(f"RetailOps CSV dataset generated for profile '{config.profile}':")
    for table_name in CSV_WRITE_ORDER:
        print(f"- {table_name}: {counts[table_name]}")
    print(f"\nOutput directory: {args.output_dir}")


if __name__ == "__main__":
    main()
