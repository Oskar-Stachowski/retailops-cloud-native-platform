from __future__ import annotations

import argparse
import csv
import json
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from data.generator.configuration import (
    SUPPORTED_PROFILES,
    DatasetGenerationConfig,
    requested_parameters,
    resolve_generation_config,
)
from data.generator.csv_writer import source_columns, source_table_order
from data.generator.demand_quality import demand_report_markdown, validate_demand
from data.generator.demand_schema import DEMAND_GRAINS, DEMAND_VERSION, uses_demand
from data.generator.dimension_quality import validate_dimensions
from data.generator.dimension_schema import (
    AI_CALENDAR_VERSION,
    DIMENSION_GRAINS,
    DIMENSIONS_VERSION,
    uses_dimensions,
)
from data.generator.identity import (
    DATA_CLASSES,
    TIME_FIELDS,
    canonical_cell,
    code_fingerprint,
    code_provenance,
    content_sha256,
    csv_text,
    file_sha256,
    json_sha256,
    source_identity,
)
from data.generator.pricing_quality import pricing_report_markdown, validate_pricing
from data.generator.pricing_schema import PRICING_GRAINS, PRICING_VERSION, uses_pricing

MANIFEST_V2_FILENAME = "dataset_manifest.v2.json"
SHA256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
ISODate = Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2}$")]
Positive = Annotated[int, Field(gt=0)]
Count = Annotated[int, Field(ge=0)]
DataClass = Literal[
    "source_observation",
    "mixed_fact_and_simulation_truth",
    "source_operational_output",
    "source_plan",
    "simulation_truth",
]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class RequestedParameters(Contract):
    profile: str
    days: Positive | None
    products: Positive | None
    stores: Positive | None
    warehouses: Positive | None
    seed: Positive
    start_date: ISODate | None
    end_date: ISODate | None
    max_daily_rows: Positive | None


class ResolvedParameters(Contract):
    profile: str
    days: Positive
    products: Positive
    stores: Positive
    warehouses: Positive
    seed: Positive
    start_date: ISODate
    end_date: ISODate
    max_daily_rows: Positive
    business_timezone: Literal["UTC"]
    output_format: Literal["csv"]
    warmup_days: Count
    origin_days: Count
    label_tail_days: Count


class Versions(Contract):
    generator: Literal["0.2.0", "0.3.0", "0.4.0", "0.5.0"]
    config: Literal["1.0.0"]
    calendar: Literal["legacy-weekday-seasonality-1.0.0", "pl-de-berlin-calendar-1.0.0"]
    dimensions: Literal["retail-dimensions-1.0.0", "not_applicable"] | None = None
    pricing: Literal["retail-pricing-1.0.0", "not_applicable"] | None = None
    demand: Literal["daily-demand-1.0.0", "not_applicable"] | None = None
    canonicalization: Literal[
        "typed-csv-nfc-utc-multiset-1.0.0",
        "typed-csv-nfc-utc-multiset-1.1.0",
        "typed-csv-nfc-utc-multiset-1.2.0",
        "typed-csv-nfc-utc-multiset-1.3.0",
    ]
    csv_schema: Literal["1.0"]


class TableIdentity(Contract):
    row_count: Count
    columns: list[str]
    content_sha256: SHA256
    data_class: DataClass


class SourceDescriptor(Contract):
    identity_version: Literal["1.0.0"]
    role: Literal["source"]
    owner: Literal["retailops-cloud-native-platform"]
    parent_ids: list[str]
    schema_version: Literal["2.0.0", "2.1.0", "2.2.0", "2.3.0"]
    versions: Versions
    resolved_parameters: ResolvedParameters
    code_sha256: SHA256
    dependency_sha256: SHA256
    python_version: str
    tables: dict[str, TableIdentity]

    @model_validator(mode="after")
    def complete_source_schema(self) -> SourceDescriptor:
        revision = {"2.0.0": 0, "2.1.0": 1, "2.2.0": 2, "2.3.0": 3}[self.schema_version]
        expected_generator = f"0.{revision + 2}.0"
        expected_canonicalization = f"typed-csv-nfc-utc-multiset-1.{revision}.0"
        if (
            self.versions.generator != expected_generator
            or self.versions.canonicalization != expected_canonicalization
        ):
            msg = "Source schema and producer versions disagree."
            raise ValueError(msg)
        expected_pricing = (
            PRICING_VERSION
            if uses_pricing(self.resolved_parameters.profile, self.schema_version)
            else "not_applicable"
            if self.schema_version in {"2.2.0", "2.3.0"}
            else None
        )
        if self.versions.pricing != expected_pricing:
            msg = "Source pricing policy disagrees with schema/profile."
            raise ValueError(msg)
        expected_demand = (
            DEMAND_VERSION
            if uses_demand(self.resolved_parameters.profile, self.schema_version)
            else "not_applicable"
            if self.schema_version == "2.3.0"
            else None
        )
        if self.versions.demand != expected_demand:
            msg = "Source demand policy disagrees with schema/profile."
            raise ValueError(msg)
        names = source_table_order(self.resolved_parameters.profile, self.schema_version)
        if self.parent_ids or set(self.tables) != set(names):
            msg = "Source descriptor requires all tables and no parents."
            raise ValueError(msg)
        for name, table in self.tables.items():
            if table.columns != source_columns(name) or table.data_class != DATA_CLASSES[name]:
                msg = "Source descriptor table schema or classification disagrees."
                raise ValueError(msg)
        if uses_dimensions(self.resolved_parameters.profile, self.schema_version) and (
            self.versions.calendar != AI_CALENDAR_VERSION
            or self.versions.dimensions != DIMENSIONS_VERSION
        ):
            msg = "AI dimensions require their explicit calendar and dimension versions."
            raise ValueError(msg)
        if not uses_dimensions(self.resolved_parameters.profile, self.schema_version) and (
            self.versions.calendar != "legacy-weekday-seasonality-1.0.0"
            or self.versions.dimensions
            != (None if self.schema_version == "2.0.0" else "not_applicable")
        ):
            msg = "Legacy source must retain its calendar and dimension policy."
            raise ValueError(msg)
        return self


class Provenance(Contract):
    code_sha256: SHA256
    dependency_sha256: SHA256
    code_files: dict[str, SHA256]
    dependency_files: dict[str, SHA256]
    python_version: str
    git_commit: Annotated[str, Field(pattern=r"^(?:[0-9a-f]{40}|unavailable)$")]
    code_state: Literal["clean", "modified", "unavailable"]


class DateRange(Contract):
    date_start: ISODate | None
    date_end: ISODate | None
    value_count: Count

    @model_validator(mode="after")
    def consistent_bounds(self) -> DateRange:
        if self.value_count == 0:
            valid = self.date_start is None and self.date_end is None
        else:
            valid = (
                self.date_start is not None
                and self.date_end is not None
                and self.date_start <= self.date_end
            )
        if not valid:
            msg = "Date range does not match its value count."
            raise ValueError(msg)
        return self


class Artifact(Contract):
    table: str
    path: str
    sha256: SHA256
    size_bytes: Count
    row_count: Count
    content_sha256: SHA256
    schema_version: Literal["1.0"]
    columns: list[str]
    grain: list[str]
    data_class: DataClass
    temporal_role: Literal[
        "dimension",
        "observations",
        "plans",
        "return_tail",
        "operational_output",
        "simulation_truth",
    ]
    date_range: DateRange
    field_ranges: dict[str, DateRange]
    history_range: DateRange
    future_range: DateRange
    open_interval_rows: Count


class Report(Contract):
    path: str
    sha256: SHA256
    size_bytes: Count
    policy_version: str
    status: str


class Watermark(Contract):
    as_of_time: str
    complete_through: ISODate | None
    completeness_status: Literal["not_ready", "complete"]
    policy_version: Literal["legacy-source-boundary-1.0.0", "daily-demand-1.0.0"]
    meaning: Literal[
        "knowledge_boundary_without_completeness_guarantee",
        "synthetic_sales_day_close_without_return_guarantee",
    ]


class Readiness(Contract):
    forecasting: Literal["not_ready"]
    anomaly: Literal["not_ready"]
    stockout: Literal["not_ready"]
    replay: Literal["not_ready"]
    rag: Literal["not_applicable"]


class SourceManifestV2(Contract):
    schema_version: Literal["2.0.0", "2.1.0", "2.2.0", "2.3.0"]
    dataset_name: Literal["retailops-synthetic"]
    dataset_id: Annotated[str, Field(pattern=r"^source-sha256-[0-9a-f]{64}$")]
    descriptor: SourceDescriptor
    requested_parameters: RequestedParameters
    provenance: Provenance
    generated_at: str
    artifacts: list[Artifact]
    reports: list[Report]
    watermarks: dict[str, Watermark]
    readiness: Readiness
    inventory_ready: Literal[False]


def date_range(values: list[str]) -> dict[str, Any]:
    return {
        "date_start": min(values) if values else None,
        "date_end": max(values) if values else None,
        "value_count": len(values),
    }


def artifact_metadata(
    name: str,
    rows: list[dict[str, Any]],
    output_dir: Path,
    end_date: str,
) -> dict[str, Any]:
    columns = source_columns(name)
    field_values = {
        key: [str(canonical_cell(key, row[key]))[:10] for row in rows if csv_text(row.get(key))]
        for key in columns
        if key in TIME_FIELDS
    }
    all_dates = [value for values in field_values.values() for value in values]
    role = "observations" if field_values else "dimension"
    if DATA_CLASSES[name] == "source_plan":
        role = "plans"
    elif name == "returns":
        role = "return_tail"
    elif DATA_CLASSES[name] == "source_operational_output":
        role = "operational_output"
    elif DATA_CLASSES[name] == "simulation_truth":
        role = "simulation_truth"
    path = output_dir / (name + ".csv")
    return {
        "table": name,
        "path": path.name,
        "sha256": file_sha256(path),
        "size_bytes": path.stat().st_size,
        "row_count": len(rows),
        "content_sha256": content_sha256(rows, columns),
        "schema_version": "1.0",
        "columns": columns,
        "grain": {**DIMENSION_GRAINS, **PRICING_GRAINS, **DEMAND_GRAINS}.get(name, ["id"]),
        "data_class": DATA_CLASSES[name],
        "temporal_role": role,
        "date_range": date_range(all_dates),
        "field_ranges": {key: date_range(values) for key, values in field_values.items()},
        "history_range": date_range([value for value in all_dates if value <= end_date]),
        "future_range": date_range([value for value in all_dates if value > end_date]),
        "open_interval_rows": sum(
            not csv_text(row.get(key))
            for row in rows
            for key in ("valid_to", "ends_at", "discontinue_date")
            if key in columns
        ),
    }


def report_metadata(
    output_dir: Path, profile: str, schema_version: str = "2.3.0"
) -> list[dict[str, Any]]:
    names = ["dataset_manifest.json", "quality_report.json"]
    if profile != "demo":
        names.append("realism_report.json")
    if uses_dimensions(profile, schema_version):
        names.append("dimensions_report.json")
    if uses_pricing(profile, schema_version):
        names.extend(["pricing_report.json", "pricing_report.md"])
    if uses_demand(profile, schema_version):
        names.extend(["demand_report.json", "demand_report.md"])
    reports = []
    for name in names:
        path = output_dir / name
        payload = json.loads(
            (
                output_dir / (name.removesuffix(".md") + ".json" if name.endswith(".md") else name)
            ).read_text(encoding="utf-8")
        )
        reports.append(
            {
                "path": name,
                "sha256": file_sha256(path),
                "size_bytes": path.stat().st_size,
                "policy_version": DIMENSIONS_VERSION
                if name == "dimensions_report.json"
                else PRICING_VERSION
                if name in {"pricing_report.json", "pricing_report.md"}
                else DEMAND_VERSION
                if name in {"demand_report.json", "demand_report.md"}
                else "legacy-" + name.removesuffix(".json") + "-1.0",
                "status": str(payload.get("status", "not_applicable")),
            }
        )
    return reports


def watermark_metadata(
    end_date: date, profile: str = "demo", schema_version: str = "2.3.0"
) -> dict[str, dict[str, Any]]:
    cutoff = datetime.combine(end_date, time(23, 59, 59), tzinfo=UTC).isoformat()
    result = {
        name: {
            "as_of_time": cutoff,
            "complete_through": None,
            "completeness_status": "not_ready",
            "policy_version": "legacy-source-boundary-1.0.0",
            "meaning": "knowledge_boundary_without_completeness_guarantee",
        }
        for name in ("sales", "orders", "returns", "inventory_snapshots", "stock_movements")
    }
    if uses_demand(profile, schema_version):
        from datetime import timedelta  # noqa: PLC0415 - date arithmetic for versioned stream

        result["daily_demand_observations"] = {
            "as_of_time": datetime.combine(
                end_date + timedelta(days=1), time.min, tzinfo=UTC
            ).isoformat(),
            "complete_through": end_date.isoformat(),
            "completeness_status": "complete",
            "policy_version": DEMAND_VERSION,
            "meaning": "synthetic_sales_day_close_without_return_guarantee",
        }
    return result


def build_source_manifest_v2(
    config: DatasetGenerationConfig,
    tables: dict[str, list[dict[str, Any]]],
    output_dir: Path,
) -> dict[str, Any]:
    dataset_id, descriptor = source_identity(config, tables)
    effective = resolve_generation_config(config)
    payload = {
        "schema_version": "2.3.0",
        "dataset_name": "retailops-synthetic",
        "dataset_id": dataset_id,
        "descriptor": descriptor,
        "requested_parameters": requested_parameters(config),
        "provenance": code_provenance(code_fingerprint()),
        "generated_at": datetime.now(UTC).isoformat(),
        "artifacts": [
            artifact_metadata(name, tables[name], output_dir, effective.end_date.isoformat())
            for name in source_table_order(config.profile)
        ],
        "reports": report_metadata(output_dir, config.profile),
        "watermarks": watermark_metadata(effective.end_date, config.profile),
        "readiness": {
            "forecasting": "not_ready",
            "anomaly": "not_ready",
            "stockout": "not_ready",
            "replay": "not_ready",
            "rag": "not_applicable",
        },
        "inventory_ready": False,
    }
    validate_source_manifest_v2(payload, output_dir)
    return payload


def config_from_parameters(parameters: dict[str, Any]) -> DatasetGenerationConfig:
    values = dict(parameters)
    for name in ("start_date", "end_date"):
        values[name] = date.fromisoformat(values[name]) if values[name] is not None else None
    return DatasetGenerationConfig(**values)


def validate_source_manifest_v2(payload: dict[str, Any], output_dir: Path) -> str:
    manifest = SourceManifestV2.model_validate(payload)
    descriptor = manifest.descriptor.model_dump(exclude_unset=True)
    if manifest.schema_version != descriptor["schema_version"]:
        msg = "Source manifest and descriptor versions disagree."
        raise ValueError(msg)
    config = config_from_parameters(manifest.requested_parameters.model_dump())
    effective = resolve_generation_config(config)
    if (
        config.profile not in SUPPORTED_PROFILES
        or descriptor["resolved_parameters"] != effective.parameters()
    ):
        msg = "Requested and resolved parameters disagree."
        raise ValueError(msg)
    if (
        manifest.dataset_id != "source-sha256-" + json_sha256(descriptor)
        or descriptor["parent_ids"]
    ):
        msg = "Invalid source identity descriptor."
        raise ValueError(msg)
    provenance = manifest.provenance.model_dump()
    if provenance["python_version"] != descriptor["python_version"]:
        msg = "Python provenance does not match identity."
        raise ValueError(msg)
    for kind in ("code", "dependency"):
        digest = provenance[kind + "_sha256"]
        if (
            digest != json_sha256(provenance[kind + "_files"])
            or digest != descriptor[kind + "_sha256"]
        ):
            msg = "Code or dependency provenance does not match identity."
            raise ValueError(msg)

    generated = datetime.fromisoformat(manifest.generated_at)
    if generated.tzinfo is None or generated.utcoffset().total_seconds() != 0:
        msg = "Manifest generation time requires UTC."
        raise ValueError(msg)
    if [a.table for a in manifest.artifacts] != source_table_order(
        config.profile, manifest.schema_version
    ):
        msg = "Source manifest requires every table exactly once."
        raise ValueError(msg)
    verify_source_artifacts(manifest, output_dir, effective.end_date.isoformat())
    if [report.model_dump() for report in manifest.reports] != report_metadata(
        output_dir, config.profile, manifest.schema_version
    ):
        msg = "Source metadata or report checksum does not match."
        raise ValueError(msg)
    if {
        key: value.model_dump() for key, value in manifest.watermarks.items()
    } != watermark_metadata(effective.end_date, config.profile, manifest.schema_version):
        msg = "Watermarks must preserve the explicit boundary and unknown completeness."
        raise ValueError(msg)
    return manifest.dataset_id


def verify_source_artifacts(manifest: SourceManifestV2, output_dir: Path, end_date: str) -> None:
    tables = {}
    for artifact in manifest.artifacts:
        name = artifact.table
        if artifact.path != name + ".csv" or (output_dir / artifact.path).is_symlink():
            msg = "Artifact path must be a direct regular CSV file."
            raise ValueError(msg)
        with (output_dir / artifact.path).open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames != source_columns(name):
                msg = "CSV columns do not match source schema."
                raise ValueError(msg)
            rows = list(reader)
        tables[name] = rows
        if any(None in row or any(value is None for value in row.values()) for row in rows):
            msg = "Malformed CSV record width."
            raise ValueError(msg)
        actual = artifact_metadata(name, rows, output_dir, end_date)
        identity = {
            key: actual[key] for key in ("row_count", "columns", "content_sha256", "data_class")
        }
        if (
            actual != artifact.model_dump()
            or identity != manifest.descriptor.tables[name].model_dump()
        ):
            msg = "Artifact checksum, content, dates or identity do not match."
            raise ValueError(msg)
    if uses_dimensions(manifest.descriptor.resolved_parameters.profile, manifest.schema_version):
        dimensions_report = validate_dimensions(
            tables,
            resolve_generation_config(
                config_from_parameters(manifest.requested_parameters.model_dump())
            ),
        )
        if (
            json.loads((output_dir / "dimensions_report.json").read_text(encoding="utf-8"))
            != dimensions_report
        ):
            msg = "Dimensions report does not match verified source records."
            raise ValueError(msg)
    if uses_pricing(manifest.descriptor.resolved_parameters.profile, manifest.schema_version):
        report = validate_pricing(
            tables,
            resolve_generation_config(
                config_from_parameters(manifest.requested_parameters.model_dump())
            ),
        )
        if json.loads(
            (output_dir / "pricing_report.json").read_text(encoding="utf-8")
        ) != report or (output_dir / "pricing_report.md").read_text(
            encoding="utf-8"
        ) != pricing_report_markdown(report):
            msg = "Pricing report does not match verified source records."
            raise ValueError(msg)
    if uses_demand(manifest.descriptor.resolved_parameters.profile, manifest.schema_version):
        report = validate_demand(
            tables,
            resolve_generation_config(
                config_from_parameters(manifest.requested_parameters.model_dump())
            ),
        )
        if json.loads(
            (output_dir / "demand_report.json").read_text(encoding="utf-8")
        ) != report or (output_dir / "demand_report.md").read_text(
            encoding="utf-8"
        ) != demand_report_markdown(report):
            msg = "Demand report does not match verified source records."
            raise ValueError(msg)


def unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            msg = "Duplicate JSON keys are not allowed."
            raise ValueError(msg)
        result[key] = value
    return result


def load_source_manifest_v2(output_dir: Path) -> dict[str, Any]:
    path = output_dir / MANIFEST_V2_FILENAME
    if path.is_symlink() or path.stat().st_size > 1024 * 1024:
        msg = "Manifest must be a bounded regular file."
        raise ValueError(msg)
    payload = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_keys)
    validate_source_manifest_v2(payload, output_dir)
    return payload


def write_source_manifest_v2(
    config: DatasetGenerationConfig,
    tables: dict[str, list[dict[str, Any]]],
    output_dir: Path,
) -> Path:
    payload = build_source_manifest_v2(config, tables, output_dir)
    path = output_dir / MANIFEST_V2_FILENAME
    temporary = output_dir / (MANIFEST_V2_FILENAME + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify RetailOps source manifest v2 and every artifact."
    )
    parser.add_argument("--data-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        manifest = load_source_manifest_v2(args.data_dir)
    except (ValueError, OSError):
        parser.exit(1, "Source manifest v2 verification failed.\n")
    print("Source manifest v2 verified: " + manifest["dataset_id"])  # noqa: T201 - bounded CLI result


if __name__ == "__main__":
    main()
