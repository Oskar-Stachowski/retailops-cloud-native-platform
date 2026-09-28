from __future__ import annotations

import hashlib
import json
import platform
import re
import shutil
import subprocess
import unicodedata
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from data.generator.configuration import (
    CALENDAR_VERSION,
    CONFIG_VERSION,
    DatasetGenerationConfig,
    resolve_generation_config,
)
from data.generator.csv_writer import CSV_WRITE_ORDER, source_columns, source_table_order
from data.generator.demand_schema import DEMAND_CLASSES, DEMAND_VERSION, uses_demand
from data.generator.dimension_schema import (
    AI_CALENDAR_VERSION,
    DIMENSION_CLASSES,
    DIMENSIONS_VERSION,
    uses_dimensions,
)
from data.generator.pricing_schema import PRICING_CLASSES, PRICING_VERSION, uses_pricing

ROOT = Path(__file__).resolve().parents[2]
GENERATOR_VERSION = "0.5.0"
CANONICALIZATION_VERSION = "typed-csv-nfc-utc-multiset-1.3.0"
SOURCE_SCHEMA_VERSION = "2.3.0"
INTEGER_FIELDS = {
    "observed_units",
    "observed_orders",
    "return_units",
    "latent_units",
    "quantity",
    "stock_quantity",
    "latent_demand",
    "observed_sales",
    "predicted_quantity",
    "units_sold",
    "day_of_week",
    "week_of_year",
    "month",
    "quarter",
    "version",
    "pack_quantity",
    "minimum_quantity",
    "priority",
}
DECIMAL_FIELDS = {
    "net_revenue",
    "base_rate",
    "product_factor",
    "location_factor",
    "weekly_factor",
    "seasonal_factor",
    "lifecycle_factor",
    "price_factor",
    "promotion_factor",
    "anomaly_factor",
    "noise",
    "expected_rate",
    "rounding_draw",
    "price",
    "unit_price",
    "total_amount",
    "order_total",
    "refund_amount",
    "discount_percent",
    "demand_weight",
    "price_elasticity",
    "return_rate",
    "traffic_multiplier",
    "promo_sensitivity",
    "promotion_uplift",
    "price_elasticity_effect",
    "demand_noise",
    "confidence_level",
    "actual_value",
    "expected_value",
    "deviation_percent",
    "impact_value",
    "unit_cost",
    "gross_revenue",
    "realized_unit_price",
    "demand_multiplier",
}
BOOLEAN_FIELDS = {"stockout_flag", "promotion_applied", "is_weekend"}
BOOLEAN_FIELDS.update({"source_data_complete", "is_active_assortment", "return_data_complete"})
BOOLEAN_FIELDS.update(
    {
        "is_public_holiday",
        "is_easter",
        "is_christmas",
        "is_black_friday",
        "is_cyber_monday",
        "location_open",
        "is_category_season",
    }
)
TIME_FIELDS = {
    "sold_at",
    "ordered_at",
    "returned_at",
    "recorded_at",
    "occurred_at",
    "generated_at",
    "created_at",
    "updated_at",
    "ingested_at",
    "starts_at",
    "ends_at",
    "valid_from",
    "valid_to",
    "period_start",
    "period_end",
    "detected_at",
    "performed_at",
    "expires_at",
    "forecast_period_start",
    "forecast_period_end",
    "date",
    "observation_available_at",
    "available_at",
    "effective_from",
    "effective_to",
    "business_date",
    "launch_date",
    "discontinue_date",
    "business_day_start_at",
    "business_day_end_at",
    "local_day_start_at",
    "local_day_end_at",
    "known_at",
    "as_of_time",
}
DATA_CLASSES = dict.fromkeys(CSV_WRITE_ORDER, "source_observation")
DATA_CLASSES.update(
    dict.fromkeys(("products", "stores", "sales"), "mixed_fact_and_simulation_truth")
)
DATA_CLASSES.update(
    dict.fromkeys(
        ("forecasts", "anomalies", "alerts", "recommendations", "workflow_actions"),
        "source_operational_output",
    )
)
DATA_CLASSES.update(dict.fromkeys(("price_history", "promotions"), "source_plan"))
DATA_CLASSES.update(DIMENSION_CLASSES)
DATA_CLASSES.update(PRICING_CLASSES)
DATA_CLASSES.update(DEMAND_CLASSES)
DEPENDENCY_FILES = (
    "services/api/requirements.txt",
    "services/api/requirements-dev.txt",
)


def canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def json_sha256(value: object) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def csv_text(value: object) -> str:
    # Match csv.DictWriter: None -> empty, other values use their string representation.
    return "" if value is None else str(value)


def canonical_cell(field: str, value: object) -> object:
    text = unicodedata.normalize("NFC", csv_text(value))
    if text == "":
        return None
    if field in BOOLEAN_FIELDS:
        if text.lower() not in {"true", "false"}:
            msg = f"Invalid boolean in field {field}."
            raise ValueError(msg)
        return text.lower() == "true"
    if field in INTEGER_FIELDS | DECIMAL_FIELDS:
        try:
            number = Decimal(text)
        except InvalidOperation as error:
            msg = f"Invalid numeric field {field}."
            raise ValueError(msg) from error
        if not number.is_finite():
            msg = f"Nonfinite numeric field {field}."
            raise ValueError(msg)
        if field in INTEGER_FIELDS:
            if number != number.to_integral_value():
                msg = f"Nonintegral field {field}."
                raise ValueError(msg)
            return int(number)
        return "0" if number == 0 else format(number.normalize(), "f")
    if field in TIME_FIELDS:
        # Legacy demo writes single-element timestamp tuples in two inventory tables.
        # Decode only that exact timestamp form; byte checksums retain the original CSV.
        legacy = re.fullmatch(r"\('([0-9TZ:.+\-]+)',\)", text)
        if legacy:
            text = legacy[1]
        if len(text) == 10:
            return date.fromisoformat(text).isoformat()
        timestamp = datetime.fromisoformat(text)
        if timestamp.tzinfo is None:
            msg = f"Timestamp requires timezone in field {field}."
            raise ValueError(msg)
        return timestamp.astimezone(UTC).isoformat()
    return text


def content_sha256(rows: list[dict[str, Any]], columns: list[str]) -> str:
    # A sorted multiset preserves duplicates and ignores physical row ordering.
    records = sorted(
        canonical_json({k: canonical_cell(k, row.get(k)) for k in columns}) for row in rows
    )
    digest = hashlib.sha256()
    digest.update(canonical_json(columns) + b"\n")
    for record in records:
        digest.update(record + b"\n")
    return digest.hexdigest()


def code_fingerprint(extra_files: tuple[str, ...] = ()) -> dict[str, Any]:
    code_files = [
        str(path.relative_to(ROOT)) for path in sorted((ROOT / "data/generator").glob("*.py"))
    ]
    code_files.extend(
        [
            "data/contracts/retailops_seed_dataset.contract.json",
            "data/contracts/source_dataset_manifest.v2.schema.json",
            "data/contracts/retail_dimensions.v1.schema.json",
            "data/contracts/retail_pricing.v1.schema.json",
            "data/contracts/retail_demand.v1.schema.json",
            *extra_files,
        ]
    )
    code_hashes = {
        name: file_sha256(ROOT / name)
        for name in sorted(set(code_files))
        if (ROOT / name).is_file()
    }
    dependency_hashes = {name: file_sha256(ROOT / name) for name in DEPENDENCY_FILES}
    return {
        "code_sha256": json_sha256(code_hashes),
        "dependency_sha256": json_sha256(dependency_hashes),
        "code_files": code_hashes,
        "dependency_files": dependency_hashes,
        "python_version": platform.python_version(),
    }


def code_provenance(fingerprint: dict[str, Any]) -> dict[str, Any]:
    git_executable = shutil.which("git")
    if git_executable is None:
        return {**fingerprint, "git_commit": "unavailable", "code_state": "unavailable"}
    commit = subprocess.run(  # noqa: S603 - trusted executable, fixed arguments, no shell
        [git_executable, "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    status = subprocess.run(  # noqa: S603 - explicitly scoped source paths
        [
            git_executable,
            "status",
            "--porcelain",
            "--",
            *fingerprint["code_files"],
            *fingerprint["dependency_files"],
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        **fingerprint,
        "git_commit": commit.stdout.strip() if commit.returncode == 0 else "unavailable",
        "code_state": (
            "unavailable" if status.returncode else "modified" if status.stdout.strip() else "clean"
        ),
    }


def source_identity(
    config: DatasetGenerationConfig,
    tables: dict[str, list[dict[str, Any]]],
) -> tuple[str, dict[str, Any]]:
    fingerprint = code_fingerprint()
    descriptor = {
        "identity_version": "1.0.0",
        "role": "source",
        "owner": "retailops-cloud-native-platform",
        "parent_ids": [],
        "schema_version": SOURCE_SCHEMA_VERSION,
        "versions": {
            "generator": GENERATOR_VERSION,
            "config": CONFIG_VERSION,
            "calendar": AI_CALENDAR_VERSION
            if uses_dimensions(config.profile)
            else CALENDAR_VERSION,
            "dimensions": DIMENSIONS_VERSION
            if uses_dimensions(config.profile)
            else "not_applicable",
            "pricing": PRICING_VERSION if uses_pricing(config.profile) else "not_applicable",
            "demand": DEMAND_VERSION if uses_demand(config.profile) else "not_applicable",
            "canonicalization": CANONICALIZATION_VERSION,
            "csv_schema": "1.0",
        },
        "resolved_parameters": resolve_generation_config(config).parameters(),
        "code_sha256": fingerprint["code_sha256"],
        "dependency_sha256": fingerprint["dependency_sha256"],
        "python_version": fingerprint["python_version"],
        "tables": {
            name: {
                "row_count": len(tables[name]),
                "columns": source_columns(name),
                "content_sha256": content_sha256(tables[name], source_columns(name)),
                "data_class": DATA_CLASSES[name],
            }
            for name in source_table_order(config.profile)
        },
    }
    return "source-sha256-" + json_sha256(descriptor), descriptor
