from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from data.generator.main import (
    DatasetGenerationConfig,
    build_dataset,
)
from data.generator.manifest import GENERATOR_VERSION

SCHEMA_VERSION = "1.0"
DATASET_NAME = "retailops-demand-forecast-features"
FEATURE_SCHEMA = "demand_forecast_features.schema.json"
FEATURE_FILENAME = "features.csv"
MANIFEST_FILENAME = "feature_manifest.json"
GRAIN = ["date", "product_id", "store_id", "channel"]
TARGET = "units_sold"
SOURCE_ARTIFACTS = [
    "sales.csv",
    "products.csv",
    "stores.csv",
    "price_history.csv",
    "promotions.csv",
    "inventory_snapshots.csv",
]
FEATURE_COLUMNS = [
    "schema_version",
    "dataset_id",
    "feature_row_id",
    "date",
    "product_id",
    "store_id",
    "channel",
    "units_sold",
    "latent_units_demand",
    "sales_revenue",
    "unit_price",
    "discount_percent",
    "promotion_active",
    "promotion_type",
    "stockout_flag",
    "inventory_on_hand",
    "inventory_reserved",
    "category",
    "brand",
    "product_status",
    "day_of_week",
    "is_weekend",
    "week_of_year",
    "month",
    "data_quality_status",
    "generated_at",
]


@dataclass(frozen=True)
class DemandFeatureGenerationConfig:
    dataset: DatasetGenerationConfig = field(
        default_factory=lambda: DatasetGenerationConfig(profile="demo"),
    )
    output_dir: Path | None = None


def _text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, tuple):
        return _text(value[0] if value else "")
    return str(value)


def _date(value: object) -> date:
    return date.fromisoformat(_text(value)[:10])


def _decimal(value: object, default: str = "0") -> Decimal:
    raw_value = _text(value)
    return Decimal(raw_value if raw_value else default)


def _money(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _ratio(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))


def _bool(value: object) -> bool:
    return _text(value).lower() in {"1", "true", "yes"}


def _feature_generated_at(tables: dict[str, list[dict[str, object]]]) -> str:
    candidates: list[str] = []
    for sale in tables["sales"]:
        candidates.append(_text(sale.get("ingested_at")) or _text(sale.get("sold_at")))
    for snapshot in tables["inventory_snapshots"]:
        candidates.append(_text(snapshot.get("ingested_at")) or _text(snapshot.get("recorded_at")))

    return max(value for value in candidates if value)


def _dataset_id(
    profile: str,
    seed: int,
    rows: list[dict[str, object]],
) -> str:
    dates = [row["date"] for row in rows]
    date_start = min(dates) if dates else "empty"
    date_end = max(dates) if dates else "empty"
    return f"{DATASET_NAME}-{profile}-{date_start}-{date_end}-seed{seed}"


def _active_promotion(
    product_id: str,
    channel: str,
    business_date: date,
    promotions: list[dict[str, object]],
) -> dict[str, object] | None:
    for promotion in promotions:
        promotion_channel = _text(promotion.get("channel"))
        if _text(promotion.get("product_id")) != product_id:
            continue
        if promotion_channel not in {"all", channel}:
            continue
        if _text(promotion.get("status")) != "active":
            continue
        if _date(promotion["starts_at"]) <= business_date <= _date(promotion["ends_at"]):
            return promotion
    return None


def _price_for_date(
    product_id: str,
    business_date: date,
    fallback: Decimal,
    price_history: list[dict[str, object]],
) -> Decimal:
    candidates = [
        price_point
        for price_point in price_history
        if _text(price_point.get("product_id")) == product_id
        and _date(price_point["valid_from"]) <= business_date
        and (
            not _text(price_point.get("valid_to"))
            or business_date <= _date(price_point["valid_to"])
        )
    ]
    if not candidates:
        return fallback

    current_prices = [
        price_point
        for price_point in candidates
        if _text(price_point.get("price_type")) == "regular"
    ]
    selected = current_prices[0] if current_prices else candidates[0]
    return _decimal(selected["price"], default=str(fallback))


def _inventory_for_date(
    product_id: str,
    business_date: date,
    inventory_snapshots: list[dict[str, object]],
) -> dict[str, object] | None:
    candidates = [
        snapshot
        for snapshot in inventory_snapshots
        if _text(snapshot.get("product_id")) == product_id
        and _date(snapshot["recorded_at"]) <= business_date
    ]
    if not candidates:
        candidates = [
            snapshot
            for snapshot in inventory_snapshots
            if _text(snapshot.get("product_id")) == product_id
        ]
    if not candidates:
        return None

    return max(candidates, key=lambda snapshot: _text(snapshot["recorded_at"]))


def _quality_status(statuses: list[str]) -> str:
    normalized = {status for status in statuses if status}
    if not normalized or normalized == {"ok"}:
        return "passed"
    if "failed" in normalized:
        return "failed"
    return "warning"


def _promotion_type(value: str) -> str:
    return {
        "discount": "percentage_discount",
        "percentage_discount": "percentage_discount",
        "bundle": "bundle",
        "clearance": "clearance",
        "seasonal": "seasonal",
    }.get(value, "none")


def _build_aggregates(
    tables: dict[str, list[dict[str, object]]],
) -> dict[tuple[str, str, str, str], dict[str, object]]:
    orders_by_reference = {_text(order["order_reference"]): order for order in tables["orders"]}
    aggregates: dict[tuple[str, str, str, str], dict[str, object]] = {}

    for sale in tables["sales"]:
        business_date = _text(sale["sold_at"])[:10]
        product_id = _text(sale["product_id"])
        order = orders_by_reference[_text(sale["order_reference"])]
        store_id = _text(order["store_id"])
        channel = _text(sale["channel"])
        key = (business_date, product_id, store_id, channel)
        quantity = int(_decimal(sale["quantity"]))
        latent_demand = int(_decimal(sale.get("latent_demand"), default=str(quantity)))
        revenue = _decimal(sale["total_amount"])

        if key not in aggregates:
            aggregates[key] = {
                "date": business_date,
                "product_id": product_id,
                "store_id": store_id,
                "channel": channel,
                "units_sold": 0,
                "latent_units_demand": 0,
                "sales_revenue": Decimal("0"),
                "stockout_flag": False,
                "quality_statuses": [],
            }

        aggregate = aggregates[key]
        aggregate["units_sold"] += quantity
        aggregate["latent_units_demand"] += latent_demand
        aggregate["sales_revenue"] += revenue
        aggregate["stockout_flag"] = aggregate["stockout_flag"] or _bool(
            sale.get("stockout_flag"),
        )
        aggregate["quality_statuses"].append(_text(sale.get("data_quality_status")) or "ok")

    return aggregates


def build_demand_feature_rows(
    tables: dict[str, list[dict[str, object]]],
    config: DatasetGenerationConfig,
) -> list[dict[str, object]]:
    products_by_id = {_text(product["id"]): product for product in tables["products"]}
    generated_at = _feature_generated_at(tables)
    aggregates = _build_aggregates(tables)
    rows: list[dict[str, object]] = []

    for key in sorted(aggregates):
        aggregate = aggregates[key]
        business_date = _date(aggregate["date"])
        product_id = aggregate["product_id"]
        product = products_by_id[product_id]
        revenue = aggregate["sales_revenue"]
        units_sold = aggregate["units_sold"]
        weighted_unit_price = revenue / Decimal(units_sold) if units_sold else Decimal("0")
        list_price = _price_for_date(
            product_id,
            business_date,
            weighted_unit_price,
            tables["price_history"],
        )
        discount_percent = Decimal("0")
        if list_price > 0 and weighted_unit_price < list_price:
            discount_percent = (list_price - weighted_unit_price) / list_price * Decimal("100")
        promotion = _active_promotion(
            product_id,
            aggregate["channel"],
            business_date,
            tables["promotions"],
        )
        if promotion:
            discount_percent = max(discount_percent, _decimal(promotion["discount_percent"]))
        inventory = _inventory_for_date(
            product_id,
            business_date,
            tables["inventory_snapshots"],
        )
        inventory_on_hand = int(_decimal(inventory["stock_quantity"])) if inventory else 0
        iso_calendar = business_date.isocalendar()

        rows.append(
            {
                "schema_version": SCHEMA_VERSION,
                "dataset_id": "",
                "feature_row_id": ":".join(str(part) for part in key),
                "date": aggregate["date"],
                "product_id": product_id,
                "store_id": aggregate["store_id"],
                "channel": aggregate["channel"],
                "units_sold": units_sold,
                "latent_units_demand": aggregate["latent_units_demand"],
                "sales_revenue": _money(revenue),
                "unit_price": _money(weighted_unit_price),
                "discount_percent": _ratio(discount_percent),
                "promotion_active": promotion is not None,
                "promotion_type": _promotion_type(
                    _text(promotion.get("promotion_type")) if promotion else ""
                ),
                "stockout_flag": bool(aggregate["stockout_flag"]) or inventory_on_hand <= 0,
                "inventory_on_hand": inventory_on_hand,
                "inventory_reserved": 0,
                "category": _text(product["category"]),
                "brand": _text(product["brand"]),
                "product_status": _text(product["status"]),
                "day_of_week": business_date.isoweekday(),
                "is_weekend": business_date.isoweekday() in {6, 7},
                "week_of_year": iso_calendar.week,
                "month": business_date.month,
                "data_quality_status": _quality_status(aggregate["quality_statuses"]),
                "generated_at": generated_at,
            },
        )

    dataset_id = _dataset_id(config.profile, config.seed, rows)
    for row in rows:
        row["dataset_id"] = dataset_id

    return rows


def build_feature_manifest(
    config: DatasetGenerationConfig,
    rows: list[dict[str, object]],
) -> dict[str, object]:
    dates = [row["date"] for row in rows]
    dataset_id = rows[0]["dataset_id"] if rows else _dataset_id(config.profile, config.seed, rows)

    return {
        "dataset_id": dataset_id,
        "dataset_name": DATASET_NAME,
        "schema_version": SCHEMA_VERSION,
        "feature_schema": FEATURE_SCHEMA,
        "profile": config.profile,
        "grain": GRAIN,
        "target": TARGET,
        "date_start": min(dates) if dates else "",
        "date_end": max(dates) if dates else "",
        "formats": ["csv"],
        "row_count": len(rows),
        "source_artifacts": SOURCE_ARTIFACTS,
        "quality_report": "quality_report.json",
        "generator_version": GENERATOR_VERSION,
        "seed": config.seed,
        "generated_at": datetime.now(UTC).isoformat(),
    }


def default_feature_output_dir(profile: str) -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "data" / "synthetic" / profile / "features" / "demand_forecast"


def write_feature_dataset(
    output_dir: Path,
    rows: list[dict[str, object]],
    manifest: dict[str, object],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / FEATURE_FILENAME).open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=FEATURE_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    (output_dir / MANIFEST_FILENAME).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def generate_demand_feature_dataset(
    config: DemandFeatureGenerationConfig,
) -> dict[str, object]:
    tables = build_dataset(config.dataset)
    rows = build_demand_feature_rows(tables, config.dataset)
    manifest = build_feature_manifest(config.dataset, rows)
    output_dir = config.output_dir or default_feature_output_dir(config.dataset.profile)
    write_feature_dataset(output_dir, rows, manifest)
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate RetailOps demand forecasting feature dataset.",
    )
    parser.add_argument("--profile", choices=("demo", "small", "medium", "large"), default="demo")
    parser.add_argument("--days", type=int)
    parser.add_argument("--products", type=int)
    parser.add_argument("--stores", type=int)
    parser.add_argument("--warehouses", type=int)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-dir", type=Path)
    return parser.parse_args()


def config_from_args(args: argparse.Namespace) -> DemandFeatureGenerationConfig:
    return DemandFeatureGenerationConfig(
        dataset=DatasetGenerationConfig(
            profile=args.profile,
            days=args.days,
            products=args.products,
            stores=args.stores,
            warehouses=args.warehouses,
            seed=args.seed,
        ),
        output_dir=args.output_dir,
    )


def main() -> None:
    config = config_from_args(parse_args())
    manifest = generate_demand_feature_dataset(config)
    output_dir = config.output_dir or default_feature_output_dir(config.dataset.profile)

    print(  # noqa: T201 - CLI output
        f"RetailOps demand forecast features generated: {manifest['row_count']} rows",
    )
    print(f"Output directory: {output_dir}")  # noqa: T201 - CLI output


if __name__ == "__main__":
    main()
