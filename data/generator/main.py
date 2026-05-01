from __future__ import annotations

import argparse
from pathlib import Path

from data.generator.csv_writer import CSV_WRITE_ORDER, write_tables
from data.generator.forecasts import generate_forecasts
from data.generator.incidents import generate_incident_dataset
from data.generator.inventory import generate_inventory_snapshots
from data.generator.products import generate_products
from data.generator.sales import generate_sales
from data.generator.users import generate_users


def build_demo_dataset() -> dict[str, list[dict[str, str]]]:
    products = generate_products()
    users = generate_users()
    sales = generate_sales(products)
    inventory_snapshots = generate_inventory_snapshots(products)
    forecasts = generate_forecasts(products)
    incidents = generate_incident_dataset(products, forecasts, users)

    return {
        "products": products,
        "users": users,
        "sales": sales,
        "inventory_snapshots": inventory_snapshots,
        "forecasts": forecasts,
        **incidents,
    }


def default_output_dir() -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "data" / "demo"


def generate_demo_dataset(output_dir: Path | None = None) -> dict[str, int]:
    output_dir = output_dir or default_output_dir()
    tables = build_demo_dataset()
    return write_tables(output_dir, tables)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate RetailOps demo CSV dataset."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=default_output_dir(),
        help="Directory where CSV files should be written.",
    )
    args = parser.parse_args()

    counts = generate_demo_dataset(args.output_dir)

    print("Demo CSV dataset generated:")
    for table_name in CSV_WRITE_ORDER:
        print(f"- {table_name}: {counts[table_name]}")
    print(f"\nOutput directory: {args.output_dir}")


if __name__ == "__main__":
    main()
