from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from pathlib import Path

from data.generator.csv_writer import CSV_WRITE_ORDER


class ManifestConfig(Protocol):
    profile: str
    days: int | None
    products: int | None
    stores: int | None
    warehouses: int | None
    seed: int


DATASET_NAME = "retailops-synthetic"
SCHEMA_VERSION = "1.0"
GENERATOR_VERSION = "0.1.0"


def _table_date_range(
    rows: list[dict[str, str]],
    candidate_fields: tuple[str, ...],
) -> tuple[str | None, str | None]:
    values: list[str] = []
    for row in rows:
        for field in candidate_fields:
            value = row.get(field)
            if value:
                if isinstance(value, tuple):
                    value = value[0]
                values.append(str(value)[:10])
                break

    if not values:
        return None, None

    return min(values), max(values)


def _dataset_date_range(
    tables: dict[str, list[dict[str, str]]],
) -> dict[str, str | None]:
    candidate_fields = (
        "sold_at",
        "ordered_at",
        "recorded_at",
        "occurred_at",
        "generated_at",
        "created_at",
        "starts_at",
        "valid_from",
    )
    start_dates: list[str] = []
    end_dates: list[str] = []

    for rows in tables.values():
        date_start, date_end = _table_date_range(rows, candidate_fields)
        if date_start:
            start_dates.append(date_start)
        if date_end:
            end_dates.append(date_end)

    return {
        "date_start": min(start_dates) if start_dates else None,
        "date_end": max(end_dates) if end_dates else None,
    }


def _artifacts_for_profile(profile: str) -> list[str]:
    artifacts = [f"{table_name}.csv" for table_name in CSV_WRITE_ORDER]
    artifacts.append("dataset_manifest.json")
    artifacts.append("quality_report.json")
    if profile != "demo":
        artifacts.append("realism_report.json")
    return artifacts


def build_dataset_manifest(
    config: ManifestConfig,
    tables: dict[str, list[dict[str, str]]],
) -> dict[str, object]:
    date_range = _dataset_date_range(tables)

    return {
        "dataset_name": DATASET_NAME,
        "profile": config.profile,
        "schema_version": SCHEMA_VERSION,
        "generator_version": GENERATOR_VERSION,
        "seed": config.seed,
        "generated_at": datetime.now(UTC).isoformat(),
        "date_start": date_range["date_start"],
        "date_end": date_range["date_end"],
        "parameters": {
            "days": config.days,
            "products": config.products,
            "stores": config.stores,
            "warehouses": config.warehouses,
        },
        "formats": ["csv"],
        "row_counts": {table_name: len(tables[table_name]) for table_name in CSV_WRITE_ORDER},
        "artifacts": _artifacts_for_profile(config.profile),
    }


def write_dataset_manifest(
    output_dir: Path,
    config: ManifestConfig,
    tables: dict[str, list[dict[str, str]]],
) -> Path:
    manifest_path = output_dir / "dataset_manifest.json"
    manifest = build_dataset_manifest(config, tables)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest_path
