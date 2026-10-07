from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

from data.generator.common import GenerationClock
from data.generator.configuration import (
    SUPPORTED_PROFILES,
    DatasetGenerationConfig,
    resolve_generation_config,
)
from data.generator.configuration import (
    validate_generation_config as validate_generation_config,  # noqa: PLC0414 - public legacy API
)
from data.generator.csv_writer import write_tables
from data.generator.demand_quality import validate_demand, write_demand_report
from data.generator.demand_schema import uses_demand
from data.generator.dimension_quality import validate_dimensions, write_dimensions_report
from data.generator.dimension_schema import uses_dimensions
from data.generator.forecasts import generate_forecasts
from data.generator.identity import source_identity
from data.generator.incidents import generate_incident_dataset
from data.generator.inventory import generate_inventory_snapshots
from data.generator.locations import generate_stores, generate_warehouses
from data.generator.manifest import write_dataset_manifest
from data.generator.manifest_v2 import (
    MANIFEST_V2_FILENAME,
    load_source_manifest_v2,
    write_source_manifest_v2,
)
from data.generator.orders import generate_order_items, generate_orders
from data.generator.pricing import generate_price_history, generate_promotions
from data.generator.pricing_quality import validate_pricing, write_pricing_report
from data.generator.pricing_schema import uses_pricing
from data.generator.products import generate_products
from data.generator.profile_engine import build_profile_dataset
from data.generator.quality import write_quality_report
from data.generator.realism_report import write_realism_report
from data.generator.return_quality import validate_returns, write_returns_report
from data.generator.return_schema import uses_returns
from data.generator.sales import generate_sales
from data.generator.simulation_schema import uses_separation
from data.generator.source_quality import validate_source_report, write_source_report
from data.generator.source_realism import build_source_realism, write_source_realism
from data.generator.stock import generate_returns, generate_stock_movements
from data.generator.users import generate_users

if TYPE_CHECKING:
    from data.anomalies.contract import AnomalyPlan


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
            "max-daily-rows": config.max_daily_rows,
        }.items()
        if value is not None
    ]
    if config.seed != 42:
        ignored_options.append("seed")

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
    *,
    anomaly_plan: AnomalyPlan | None = None,
) -> dict[str, list[dict[str, str]]]:
    config = config or DatasetGenerationConfig()
    effective = resolve_generation_config(config)
    if anomaly_plan is not None and not config.profile.startswith("ai-"):
        msg = "Anomaly scenarios require an AI profile."
        raise ValueError(msg)
    if config.profile == "demo":
        return build_demo_dataset()

    return build_profile_dataset(
        profile=effective.profile,
        days=effective.days,
        product_count=effective.products,
        store_count=effective.stores,
        warehouse_count=effective.warehouses,
        seed=effective.seed,
        clock=GenerationClock(effective.end_date),
        anomaly_plan=anomaly_plan,
        forecast_plan_days=effective.forecast_plan_days,
    )


def generate_demo_dataset(
    output_dir: Path | None = None,
    config: DatasetGenerationConfig | None = None,
) -> dict[str, int]:
    config = config or DatasetGenerationConfig()
    output_dir = output_dir or default_output_dir_for_profile(config.profile)
    tables = build_dataset(config)
    dimensions_report = (
        validate_dimensions(tables, resolve_generation_config(config))
        if uses_dimensions(config.profile)
        else None
    )
    pricing_report = (
        validate_pricing(tables, resolve_generation_config(config))
        if uses_pricing(config.profile)
        else None
    )
    demand_report = (
        validate_demand(tables, resolve_generation_config(config))
        if uses_demand(config.profile)
        else None
    )
    returns_report = (
        validate_returns(tables, resolve_generation_config(config))
        if uses_returns(config.profile)
        else None
    )
    source_report = (
        validate_source_report(tables, resolve_generation_config(config))
        if uses_separation(config.profile)
        else None
    )
    if (output_dir / MANIFEST_V2_FILENAME).exists():
        previous = load_source_manifest_v2(output_dir)
        if previous["dataset_id"] != source_identity(config, tables)[0]:
            msg = "Output already contains a different dataset; choose a new output directory."
            raise ValueError(msg)
    counts = write_tables(output_dir, tables)
    if dimensions_report is not None:
        write_dimensions_report(output_dir, dimensions_report)
    if pricing_report is not None:
        write_pricing_report(output_dir, pricing_report)
    if demand_report is not None:
        write_demand_report(output_dir, demand_report)
    if returns_report is not None:
        write_returns_report(output_dir, returns_report)
    write_quality_report(output_dir, config.profile, tables)
    write_dataset_manifest(output_dir, config, tables)
    if source_report is not None:
        write_source_report(output_dir, source_report)
        write_source_realism(output_dir, build_source_realism(config.profile, config.seed, tables))
    elif config.profile != "demo":
        write_realism_report(output_dir, config.profile, config.seed, tables)
    write_source_manifest_v2(config, tables, output_dir)
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
        "--start-date", type=date.fromisoformat, help="First sale date (inclusive)."
    )
    parser.add_argument("--end-date", type=date.fromisoformat, help="Last sale date (inclusive).")
    parser.add_argument(
        "--max-daily-rows",
        type=int,
        help="Preflight cap on days x products x stores; required for ai-load.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory where CSV files should be written.",
    )

    parser.add_argument(
        "--source-version",
        choices=("2.6", "2.7"),
        default=None,
        help="AI profiles default to inventory source 2.7; 2.6 is frozen compatibility.",
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
        start_date=getattr(args, "start_date", None),
        end_date=getattr(args, "end_date", None),
        max_daily_rows=getattr(args, "max_daily_rows", None),
    )


def main() -> None:
    args = parse_args()
    config = config_from_args(args)
    warn_if_demo_ignores_sizing_options(config)

    if config.profile.startswith("ai-") and args.source_version != "2.6":
        from data.inventory.run_source_dataset import (  # noqa: PLC0415 - versioned dispatch avoids dependency cycle
            run,
        )

        result = run(
            config,
            args.output_dir or Path(__file__).resolve().parents[2] / "data/generated/sources",
        )
        print(json.dumps(result, indent=2))  # noqa: T201 - CLI receipt
        if result["status"] != "passed":
            raise SystemExit(1)
        return
    if args.source_version == "2.7":
        message = "Source 2.7 requires an AI profile."
        raise ValueError(message)
    counts = generate_demo_dataset(args.output_dir, config)
    output_dir = args.output_dir or default_output_dir_for_profile(
        config.profile,
    )

    print(f"RetailOps CSV dataset generated for profile '{config.profile}':")  # noqa: T201 - CLI output
    for table_name in counts:
        print(f"- {table_name}: {counts[table_name]}")  # noqa: T201 - CLI output
    print(f"\nOutput directory: {output_dir}")  # noqa: T201 - CLI output


if __name__ == "__main__":
    main()
