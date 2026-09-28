from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from data.generator.configuration import SUPPORTED_PROFILES
from data.generator.demand_schema import uses_demand
from data.generator.feature_admission import admit_feature_source
from data.generator.identity import GENERATOR_VERSION
from data.generator.main import (
    DatasetGenerationConfig,
    build_dataset,
)
from ml.features.ai_demand import AI_HISTORY_COLUMNS
from ml.features.identity import (
    IDENTITY_FILENAME,
    feature_identity,
    feature_identity_from_source,
    load_feature_identity_manifest,
    write_feature_identity_manifest,
)
from ml.features.isolated_runtime import isolated_feature_rows
from ml.features.observation_history import (
    SCORABLE,
    aggregate_versions,
    history_json,
    observation_at_time,
)

SCHEMA_VERSION = "2.1"
DATASET_NAME = "retailops-demand-forecast-features"
FEATURE_SCHEMA = "demand_forecast_features.schema.json"
FEATURE_FILENAME = "features.csv"
MANIFEST_FILENAME = "feature_manifest.json"
GRAIN = ["date", "product_id", "store_id", "channel"]
TARGET = "units_sold"
SOURCE_ARTIFACTS = [
    "sales.csv",
    "orders.csv",
    "products.csv",
]
LEGACY_FEATURE_COLUMNS = [
    "schema_version",
    "dataset_id",
    "feature_row_id",
    "date",
    "product_id",
    "store_id",
    "channel",
    "units_sold",
    "observation_status",
    "observation_available_at",
    "category",
    "brand",
    "day_of_week",
    "is_weekend",
    "week_of_year",
    "month",
    "generated_at",
]
FEATURE_COLUMNS = [*LEGACY_FEATURE_COLUMNS, "observation_history"]


def feature_columns(profile: str) -> list[str]:
    return AI_HISTORY_COLUMNS if uses_demand(profile) else FEATURE_COLUMNS


@dataclass(frozen=True)
class DemandFeatureGenerationConfig:
    dataset: DatasetGenerationConfig = field(
        default_factory=lambda: DatasetGenerationConfig(profile="demo"),
    )
    output_dir: Path | None = None
    source_dir: Path | None = None


def _text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, tuple):
        return _text(value[0] if value else "")
    return str(value)


def _date(value: object) -> date:
    return date.fromisoformat(_text(value)[:10])


def _utc_timestamp(value: object) -> datetime:
    timestamp = datetime.fromisoformat(_text(value))
    if timestamp.tzinfo is None:
        msg = "Source availability timestamp must include a timezone."
        raise ValueError(msg)
    return timestamp.astimezone(UTC)


def forecast_origin_utc(first_target_date: date) -> datetime:
    return datetime.combine(first_target_date, datetime.min.time(), tzinfo=UTC) - timedelta(
        seconds=1,
    )


def observation_known_at_origin(row: dict[str, object], forecast_date: date) -> bool:
    return observation_at_origin(row, forecast_date) is not None


def observation_at_origin(row: dict[str, object], forecast_date: date) -> dict | None:
    origin = forecast_origin_utc(forecast_date)
    if _date(row["date"]) >= forecast_date:
        return None
    if (
        row.get("observation_status")
        in {"missing_data", "unknown_eligibility", "inactive_assortment", "location_closed"}
        or row.get("source_data_complete") is False
    ):
        return None
    evidence = row.get("source_evidence_available_at")
    if evidence and _utc_timestamp(evidence) > origin:
        return None
    known = observation_at_time(row, origin)
    return (
        known
        if known is not None and known.get("observation_status", "observed_positive") in SCORABLE
        else None
    )


def _feature_generated_at(tables: dict[str, list[dict[str, object]]]) -> str:
    candidates = [
        _text(sale.get("ingested_at")) or _text(sale.get("sold_at")) for sale in tables["sales"]
    ]
    return max(candidates) if candidates else datetime.now(UTC).isoformat()


def _build_aggregates(
    tables: dict[str, list[dict[str, object]]],
) -> dict[tuple[str, str, str, str], dict[str, object]]:
    orders_by_reference = {_text(order["order_reference"]): order for order in tables["orders"]}
    aggregates: dict[tuple[str, str, str, str], dict[str, object]] = {}
    events = {}

    for sale in tables["sales"]:
        business_date = _text(sale["sold_at"])[:10]
        product_id = _text(sale["product_id"])
        order = orders_by_reference[_text(sale["order_reference"])]
        store_id = _text(order["store_id"])
        channel = _text(sale["channel"])
        key = (business_date, product_id, store_id, channel)
        raw_quantity = _text(sale.get("quantity"))
        if not raw_quantity:
            msg = f"Missing sale quantity for {key}; unknown is not zero."
            raise ValueError(msg)
        quantity_value = Decimal(raw_quantity)
        quantity = int(quantity_value)
        if quantity_value != quantity or quantity < 0:
            msg = f"Sale quantity must be a nonnegative integer for {key}."
            raise ValueError(msg)
        available_at = max(
            _utc_timestamp(sale.get("ingested_at") or sale["sold_at"]),
            _utc_timestamp(order.get("created_at") or order["ordered_at"]),
        )

        if key not in aggregates:
            aggregates[key] = {
                "date": business_date,
                "product_id": product_id,
                "store_id": store_id,
                "channel": channel,
                "units_sold": 0,
                "observation_available_at": available_at,
            }
            events[key] = []

        aggregate = aggregates[key]
        aggregate["units_sold"] += quantity
        aggregate["observation_available_at"] = max(
            aggregate["observation_available_at"],
            available_at,
        )
        events[key].append((_text(sale["id"]), available_at, quantity))

    for key, aggregate in aggregates.items():
        history = aggregate_versions(events[key])
        aggregate["units_sold"] = history[-1]["units_sold"]
        aggregate["observation_history"] = history_json(history)

    return aggregates


def build_demand_feature_rows(
    tables: dict[str, list[dict[str, object]]],
    config: DatasetGenerationConfig,
) -> list[dict[str, object]]:
    if uses_demand(config.profile):
        msg = "AI features require an accepted source directory and isolated facts worker; full source tables are forbidden."
        raise ValueError(msg)
    products_by_id = {_text(product["id"]): product for product in tables["products"]}
    generated_at = _feature_generated_at(tables)
    aggregates = _build_aggregates(tables)
    rows: list[dict[str, object]] = []

    for key in sorted(aggregates):
        aggregate = aggregates[key]
        business_date = _date(aggregate["date"])
        product_id = aggregate["product_id"]
        product = products_by_id[product_id]
        units_sold = int(aggregate["units_sold"])
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
                "observation_status": "observed_zero" if units_sold == 0 else "observed_positive",
                "observation_available_at": aggregate["observation_available_at"].isoformat(),
                "category": _text(product["category"]),
                "brand": _text(product["brand"]),
                "day_of_week": business_date.isoweekday(),
                "is_weekend": business_date.isoweekday() in {6, 7},
                "week_of_year": iso_calendar.week,
                "month": business_date.month,
                "generated_at": generated_at,
                "observation_history": aggregate["observation_history"],
            },
        )

    dataset_id, _, _ = feature_identity(config, tables, rows, FEATURE_COLUMNS)
    for row in rows:
        row["dataset_id"] = dataset_id

    return rows


def build_feature_manifest(
    config: DatasetGenerationConfig,
    rows: list[dict[str, object]],
    *,
    dataset_id: str | None = None,
) -> dict[str, object]:
    dates = [row["date"] for row in rows]
    dataset_id = str(rows[0]["dataset_id"]) if rows else dataset_id
    if dataset_id is None:
        msg = "Empty features require an explicit source-derived dataset ID."
        raise ValueError(msg)

    ai = uses_demand(config.profile)
    schema_version = str(rows[0]["schema_version"]) if rows else "3.1" if ai else SCHEMA_VERSION
    return {
        "dataset_id": dataset_id,
        "dataset_name": DATASET_NAME,
        "schema_version": schema_version,
        "feature_schema": (
            "demand_forecast_features.v3_1.schema.json"
            if schema_version == "3.1"
            else "demand_forecast_features.v3.schema.json"
        )
        if ai
        else FEATURE_SCHEMA,
        "profile": config.profile,
        "grain": ["date", "product_id", "selling_location_id", "channel"] if ai else GRAIN,
        "target": TARGET,
        "date_start": min(dates) if dates else "",
        "date_end": max(dates) if dates else "",
        "formats": ["csv"],
        "row_count": len(rows),
        "source_artifacts": [
            "daily_demand_observations.csv",
            "product_catalog.csv",
            "catalog_categories.csv",
            *(["daily_demand_versions.csv"] if schema_version == "3.1" else []),
        ]
        if ai
        else SOURCE_ARTIFACTS,
        **({"target_type": "observed_sales_units"} if ai else {}),
        "forecast_origin_rule": "previous_day_end_utc",
        "available_at_origin_fields": [
            "date",
            "product_id",
            "selling_location_id" if ai else "store_id",
            "channel",
            "category",
            "brand",
            "day_of_week",
            "is_weekend",
            "week_of_year",
            "month",
        ],
        "label_fields": ["units_sold", "observation_status"],
        "observation_availability_field": "observation_available_at",
        "inventory_ready": False,
        "complete_daily_panel": ai and all(row["source_data_complete"] for row in rows),
        "quality_report": "demand_report.json" if ai else "quality_report.json",
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
        writer = csv.DictWriter(
            file,
            fieldnames=AI_HISTORY_COLUMNS
            if manifest["schema_version"] == "3.1"
            else FEATURE_COLUMNS,
        )
        writer.writeheader()
        writer.writerows(rows)

    (output_dir / MANIFEST_FILENAME).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def generate_demand_feature_dataset(
    config: DemandFeatureGenerationConfig,
) -> dict[str, object]:
    columns = feature_columns(config.dataset.profile)
    source_descriptor = None
    tables = None
    if uses_demand(config.dataset.profile):
        if config.source_dir is None:
            msg = "AI features require --source-dir with an accepted source export."
            raise ValueError(msg)
        facts, source_descriptor = admit_feature_source(config.source_dir, config.dataset)
        rows = isolated_feature_rows(facts)
        dataset_id, _, _ = feature_identity_from_source(
            config.dataset, source_descriptor, rows, columns
        )
        for row in rows:
            row["dataset_id"] = dataset_id
    else:
        tables = build_dataset(config.dataset)
        rows = build_demand_feature_rows(tables, config.dataset)
        dataset_id, _, _ = feature_identity(config.dataset, tables, rows, columns)
    manifest = build_feature_manifest(config.dataset, rows, dataset_id=dataset_id)
    output_dir = config.output_dir or default_feature_output_dir(config.dataset.profile)
    if (output_dir / IDENTITY_FILENAME).exists():
        previous = load_feature_identity_manifest(output_dir, columns)
        if previous["dataset_id"] != dataset_id:
            msg = "Output already contains different features; choose a new output directory."
            raise ValueError(msg)
    write_feature_dataset(output_dir, rows, manifest)
    write_feature_identity_manifest(
        config.dataset, tables, rows, columns, output_dir, source_descriptor=source_descriptor
    )
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate RetailOps demand forecasting feature dataset.",
    )
    parser.add_argument("--profile", choices=SUPPORTED_PROFILES, default="demo")
    parser.add_argument("--days", type=int)
    parser.add_argument("--products", type=int)
    parser.add_argument("--stores", type=int)
    parser.add_argument("--warehouses", type=int)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--start-date", type=date.fromisoformat)
    parser.add_argument("--end-date", type=date.fromisoformat)
    parser.add_argument("--max-daily-rows", type=int)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--source-dir", type=Path)
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
            start_date=getattr(args, "start_date", None),
            end_date=getattr(args, "end_date", None),
            max_daily_rows=getattr(args, "max_daily_rows", None),
        ),
        output_dir=args.output_dir,
        source_dir=getattr(args, "source_dir", None),
    )


def main() -> None:
    config = config_from_args(parse_args())
    try:
        manifest = generate_demand_feature_dataset(config)
    except (ValueError, RuntimeError, OSError):
        sys.exit("Feature source admission or isolated runtime failed.")
    output_dir = config.output_dir or default_feature_output_dir(config.dataset.profile)

    print(  # noqa: T201 - CLI output
        f"RetailOps demand forecast features generated: {manifest['row_count']} rows",
    )
    print(f"Output directory: {output_dir}")  # noqa: T201 - CLI output


if __name__ == "__main__":
    main()
