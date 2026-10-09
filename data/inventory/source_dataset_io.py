"""Atomic, immutable CSV source 2.7 with independently recomputed quality reports."""

from __future__ import annotations

import csv
import json
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING

from data.anomalies.source_contract import POLICY as ANOMALY_POLICY
from data.anomalies.source_contract import SCENARIO_PATH, AnomalySourceManifest
from data.export.schema import table_schema, typed_row
from data.generator.configuration import DatasetGenerationConfig, resolve_generation_config
from data.generator.identity import (
    canonical_json,
    code_fingerprint,
    code_provenance,
    content_sha256,
    file_sha256,
    json_sha256,
)
from data.generator.manifest_v2 import config_from_parameters, requested_parameters, unique_keys
from data.generator.progress import counted, stage
from data.generator.source_realism import realism_markdown
from data.inventory.contract import UTC_TIMESTAMP_PATTERN, require, utc_timestamp
from data.inventory.source_contract import SourceInventoryConfig
from data.inventory.source_dataset_contract import (
    FORECAST_GENERATOR_VERSION,
    GENERATOR_VERSION,
    MANIFEST_FILENAME,
    SOURCE_POLICY,
    SOURCE_TABLES,
    SOURCE_VERSION,
    SourceManifest,
    columns,
    csv_path,
    data_class,
    grain,
    table_schema_document,
)
from data.inventory.source_dataset_quality import (
    build_realism,
    build_source_report,
    report_markdown,
)
from data.inventory.source_tables import TableContext, normalize_tables
from data.inventory.source_tables_contract import TABLE_CONTRACT_VERSION, TABLES, field_rules
from data.inventory.source_tables_io import _csv_value, _parse_csv

if TYPE_CHECKING:
    from data.generator.configuration import ResolvedGenerationConfig

MAX_FILE_BYTES = 128 * 1024 * 1024
MAX_METADATA_BYTES = 2 * 1024 * 1024
CONFIG_PATH = "simulation_truth/inventory_configuration.json"
REPORT_NAMES = (
    "source_report.json",
    "source_report.md",
    "realism_report.json",
    "realism_report.md",
)


@stage("source_normalization")
def normalize_source(tables: dict) -> dict:
    require(set(tables) == set(SOURCE_TABLES), "Source 2.7 table allowlist differs.")
    native = normalize_tables({n: tables[n] for n in TABLES})
    result = {}
    for name in SOURCE_TABLES:
        if name in native:
            result[name] = native[name]
            continue
        schema = table_schema(name, "ai-smoke")
        rows = tables[name]
        for row in rows:
            require(
                all(isinstance(v, str) for v in row.values()), "Non-CSV scalar in commerce source."
            )
            typed_row(row, schema)
        keys = [tuple(r[f] for f in grain(name)) for r in rows]
        require(len(keys) == len(set(keys)), "Duplicate source table grain: " + name)
        result[name] = sorted(rows, key=lambda r: tuple(r[f] for f in grain(name)))
    return result


def table_identity(name: str, rows: list[dict]) -> dict:
    return {
        "row_count": len(rows),
        "columns": columns(name),
        "grain": grain(name),
        "data_class": data_class(name),
        "content_sha256": json_sha256(rows)
        if name in TABLES
        else content_sha256(rows, columns(name)),
    }


def verify_normalized_source(tables: dict) -> None:
    """Check the complete canonical tables without constructing a second dataset."""
    require(set(tables) == set(SOURCE_TABLES), "Source 2.7 table allowlist differs.")
    for name, rows in tables.items():
        definition = TABLES.get(name)
        schema = None if definition else table_schema(name, "ai-smoke")
        properties = field_rules(definition.model) if definition else {}
        keys = definition.grain if definition else grain(name)
        previous = None
        for row in rows:
            if definition:
                normalized = definition.model.model_validate(row).model_dump()
                for field, value in normalized.items():
                    if (
                        value is not None
                        and properties[field].get("pattern") == UTC_TIMESTAMP_PATTERN
                    ):
                        normalized[field] = utc_timestamp(value).isoformat()
                require(normalized == row, "Noncanonical source values/grain order.")
            else:
                require(
                    all(isinstance(v, str) for v in row.values()),
                    "Non-CSV scalar in commerce source.",
                )
                typed_row(row, schema)
            key = tuple(row[field] for field in keys)
            require(previous is None or previous < key, "Noncanonical source values/grain order.")
            previous = key


def fingerprint() -> dict:
    root = Path(__file__).resolve().parents[2]
    extra = tuple(
        str(p.relative_to(root))
        for directory, pattern in (
            (root / "data/inventory", "*.py"),
            (root / "data/contracts", "*.schema.json"),
            (root / "data/anomalies", "*.py"),
        )
        for p in sorted(directory.glob(pattern))
    )
    return code_fingerprint(
        (*extra, "data/export/schema.py", "data/contracts/source_inventory_config.v1.schema.json")
    )


def descriptor(
    generation: DatasetGenerationConfig,
    config: SourceInventoryConfig,
    tables: dict,
    context: TableContext,
    provenance: dict,
) -> dict:
    effective = resolve_generation_config(generation)
    result = {
        "identity_version": "inventory-source-identity-1.0.0",
        "role": "source",
        "owner": "retailops-cloud-native-platform",
        "schema_version": SOURCE_VERSION,
        "generator_version": FORECAST_GENERATOR_VERSION
        if effective.forecast_plan_days
        else GENERATOR_VERSION,
        "table_contract_version": TABLE_CONTRACT_VERSION,
        "source_policy_version": SOURCE_POLICY,
        "canonicalization_version": "inventory-source-typed-csv-1.0.0",
        "table_schema_sha256": json_sha256(table_schema_document()),
        "resolved_parameters": resolve_generation_config(generation).parameters(),
        "inventory_configuration_sha256": json_sha256(config.model_dump()),
        "context": context.model_dump(),
        **{k: provenance[k] for k in ("code_sha256", "dependency_sha256", "python_version")},
        "tables": {n: table_identity(n, tables[n]) for n in SOURCE_TABLES},
    }
    if effective.forecast_plan_days:
        result["forecast_watermarks"] = forecast_watermarks(tables, context, effective)
    return result


def forecast_watermarks(
    tables: dict, context: TableContext, generation: ResolvedGenerationConfig
) -> dict:
    """Declare observed completeness at the real source cutoff; plans never extend it."""
    rows = tables["daily_demand_observations"]
    cutoff = datetime.fromisoformat(context.evaluated_at)
    complete = bool(rows) and all(
        r["source_data_complete"] == "true"
        and datetime.fromisoformat(r["available_at"]) <= cutoff
        and r["business_date"] <= generation.end_date.isoformat()
        for r in rows
    )
    return {
        "daily_demand_observations": {
            "as_of_time": context.evaluated_at,
            "complete_through": generation.end_date.isoformat() if complete else None,
            "completeness_status": "complete" if complete else "not_ready",
            "meaning": "synthetic_sales_day_close_without_return_guarantee",
            "policy_version": "daily-demand-1.0.0",
        }
    }


def artifact(path: Path, directory: Path) -> dict:
    return {
        "path": path.relative_to(directory).as_posix(),
        "sha256": file_sha256(path),
        "size_bytes": path.stat().st_size,
    }


def safe_file(directory: Path, relative: str, *, limit: int = MAX_FILE_BYTES) -> Path:
    path = directory / relative
    require(
        path.is_file()
        and not path.is_symlink()
        and path.resolve().is_relative_to(directory.resolve())
        and path.stat().st_size <= limit,
        "Source artifact escapes its directory, is missing, or exceeds its budget.",
    )
    return path


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_keys)


def verify_artifact(
    directory: Path, declared: dict, expected_path: str, *, limit: int = MAX_FILE_BYTES
) -> Path:
    require(declared["path"] == expected_path, "Source artifact placement differs from allowlist.")
    path = safe_file(directory, expected_path, limit=limit)
    require(artifact(path, directory) == declared, "Source artifact bytes/checksum differ.")
    return path


@stage("source_read")
def read_source_dataset(directory: Path, payload: dict | None = None) -> tuple[dict, dict]:  # noqa: PLR0912, PLR0915 - ordered source integrity and replay gates
    require(
        not directory.is_symlink() and not any(p.is_symlink() for p in directory.rglob("*")),
        "Symlink in source dataset.",
    )
    if payload is None:
        payload = load_json(safe_file(directory, MANIFEST_FILENAME, limit=MAX_METADATA_BYTES))
    is_anomaly = payload.get("schema_version") == "2.8.0"
    manifest = (AnomalySourceManifest if is_anomaly else SourceManifest).model_validate(payload)
    normalized = manifest.model_dump()
    require(normalized == payload, "Noncanonical source manifest fields/types.")
    desc = normalized["descriptor"]
    require(manifest.dataset_id == "source-sha256-" + json_sha256(desc), "Source identity differs.")
    require(
        datetime.fromisoformat(manifest.generated_at).utcoffset() == timedelta(0),
        "Source generated_at requires UTC.",
    )
    generation = config_from_parameters(normalized["requested_parameters"])
    effective = resolve_generation_config(generation)
    require(
        generation.profile.startswith("ai-")
        and effective.parameters() == desc["resolved_parameters"],
        "Source requested/resolved generation differs.",
    )
    require(
        desc["generator_version"]
        == (
            "1.0.0"
            if is_anomaly
            else FORECAST_GENERATOR_VERSION
            if effective.forecast_plan_days
            else GENERATOR_VERSION
        ),
        "Source generator version disagrees with declared forecast planning mode.",
    )
    context = manifest.descriptor.context
    require(
        context.opening_at
        == context.projection.start_at
        == datetime.combine(effective.start_date, time.min, tzinfo=UTC).isoformat()
        and context.projection.end_at
        == datetime.combine(
            effective.end_date + timedelta(days=1), time.min, tzinfo=UTC
        ).isoformat(),
        "Inventory projection window differs from source generation.",
    )
    if is_anomaly:
        from data.anomalies.source_process import table_contract  # noqa: PLC0415 - generator cycle

        schema = table_contract()
    else:
        schema = table_schema_document()
    require(
        desc["table_schema_sha256"] == json_sha256(schema)
        and set(desc["tables"]) == set(SOURCE_TABLES)
        and set(normalized["artifacts"]) == set(SOURCE_TABLES),
        "Source table/schema allowlist differs.",
    )
    provenance = normalized["provenance"]
    if is_anomaly:
        current = fingerprint()
        require(
            all(
                current[k] == desc[k]
                for k in ("code_sha256", "dependency_sha256", "python_version")
            ),
            "Anomaly source replay requires the recorded generator environment.",
        )
    for kind in ("code", "dependency"):
        require(
            json_sha256(provenance[kind + "_files"])
            == provenance[kind + "_sha256"]
            == desc[kind + "_sha256"],
            "Source provenance checksum differs.",
        )
    require(
        provenance["python_version"] == desc["python_version"], "Source Python provenance differs."
    )
    config = SourceInventoryConfig.from_payload(
        load_json(
            verify_artifact(
                directory,
                normalized["inventory_configuration"],
                CONFIG_PATH,
                limit=MAX_METADATA_BYTES,
            )
        )
    )
    require(
        json_sha256(config.model_dump()) == desc["inventory_configuration_sha256"],
        "Private source configuration differs from identity.",
    )
    require(config.fulfillment.seed == effective.seed, "Inventory and generation seeds differ.")
    scenario = None
    if is_anomaly:
        from data.anomalies.candidate_io import (  # noqa: PLC0415
            candidate_plan_schema,
            parse_candidate_plan,
        )

        scenario = load_json(
            verify_artifact(
                directory, normalized["scenario"], SCENARIO_PATH, limit=MAX_METADATA_BYTES
            )
        )
        plan = parse_candidate_plan(scenario["plan"])
        require(
            json_sha256(plan.model_dump()) == desc["scenario_plan_sha256"]
            and json_sha256(candidate_plan_schema(plan.model_dump()))
            == desc["scenario_schema_sha256"],
            "Anomaly source plan binding differs.",
        )
    tables = {}
    for name in SOURCE_TABLES:
        path = verify_artifact(directory, normalized["artifacts"][name], csv_path(name))
        with path.open(encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            require(reader.fieldnames == columns(name), "Source CSV header differs: " + name)
            rows = []
            rules = field_rules(TABLES[name].model) if name in TABLES else {}
            for csv_row in counted(
                "source_read/" + name, reader, total=desc["tables"][name]["row_count"]
            ):
                require(
                    None not in csv_row and all(isinstance(v, str) for v in csv_row.values()),
                    "Malformed source CSV row width.",
                )
                if name in TABLES:
                    row = (
                        TABLES[name]
                        .model.model_validate(
                            {k: _parse_csv(v, rules[k]) for k, v in csv_row.items()}
                        )
                        .model_dump()
                    )
                else:
                    row = csv_row
                rows.append(row)
        require(
            table_identity(name, rows) == desc["tables"][name],
            "Source table content/metadata differs: " + name,
        )
        tables[name] = rows
    verify_normalized_source(tables)
    if scenario is not None:
        from data.anomalies.source_process import scenario_document  # noqa: PLC0415

        require(
            scenario == scenario_document(tables, context, generation, config, scenario["plan"]),
            "Anomaly effects/truth disagree with independent process replay.",
        )
    reports = build_reports(
        tables, context, effective, config, scenario_plan=scenario["plan"] if scenario else None
    )
    require(
        desc.get("forecast_watermarks")
        == (
            forecast_watermarks(tables, context, effective)
            if effective.forecast_plan_days
            else None
        ),
        "Forecast watermark differs from independently recomputed observed source completeness.",
    )
    require(set(normalized["reports"]) == set(REPORT_NAMES), "Source report allowlist differs.")
    for name, expected in reports.items():
        path = verify_artifact(
            directory, normalized["reports"][name], name, limit=MAX_METADATA_BYTES
        )
        require(
            path.read_bytes() == expected, "Source report differs from recomputed facts: " + name
        )
    require(
        manifest.facts_ready == load_report(reports)["facts_ready"],
        "Source facts readiness differs.",
    )
    allowed = {MANIFEST_FILENAME, CONFIG_PATH, *REPORT_NAMES, *(csv_path(n) for n in SOURCE_TABLES)}
    if is_anomaly:
        allowed.add(SCENARIO_PATH)
    require(
        {p.relative_to(directory).as_posix() for p in directory.rglob("*") if p.is_file()}
        == allowed,
        "Unallowlisted file in source dataset.",
    )
    return tables, normalized


def load_report(reports: dict[str, bytes]) -> dict:
    return json.loads(reports["source_report.json"])


@stage("source_validation")
def build_reports(
    tables: dict,
    context: TableContext,
    generation: ResolvedGenerationConfig,
    config: SourceInventoryConfig,
    *,
    scenario_plan: dict | None = None,
) -> dict[str, bytes]:
    demand_plan = None
    if scenario_plan is not None:
        from data.anomalies.candidate_io import parse_candidate_plan  # noqa: PLC0415
        from data.anomalies.contract import AnomalyPlan  # noqa: PLC0415

        parsed = parse_candidate_plan(scenario_plan)
        demand_plan = parsed if isinstance(parsed, AnomalyPlan) else None
    quality = build_source_report(tables, context, generation, config, anomaly_plan=demand_plan)
    if scenario_plan is not None:
        quality["policy_version"] = ANOMALY_POLICY
        for name in ("anomaly_process_replay", "anomaly_effect_reconciliation"):
            quality["checks"].append(
                {
                    "check_id": name,
                    "policy_version": ANOMALY_POLICY,
                    "severity": "hard",
                    "status": "passed",
                    "sample_size": len(parsed.injections),
                    "description": "Checked by independent complete process replay before publication/read.",
                    "evidence": "source_report.json",
                }
            )
    require(
        quality["status"] != "failed",
        "Inventory source hard gate failed: "
        + "; ".join(
            r["check_id"] + ": " + r["description"]
            for r in quality["checks"]
            if r["status"] == "failed"
        ),
    )
    realism = build_realism(tables, generation)
    return {
        "source_report.json": canonical_json(quality) + b"\n",
        "source_report.md": report_markdown(quality).encode(),
        "realism_report.json": canonical_json(realism) + b"\n",
        "realism_report.md": (
            realism_markdown(realism)
            + "\nInventory diagnostics: "
            + json.dumps(realism["inventory_diagnostics"], sort_keys=True)
            + "\n"
        ).encode(),
    }


@stage("source_write")
def write_source_dataset(
    tables: dict,
    context: TableContext,
    generation: DatasetGenerationConfig,
    config: SourceInventoryConfig,
    output_root: Path,
    *,
    scenario_plan: dict | None = None,
    consume_input: bool = False,
) -> Path:
    incoming = tables
    tables = normalize_source(incoming)
    if consume_input:
        incoming.clear()
    del incoming
    effective = resolve_generation_config(generation)
    provenance = code_provenance(fingerprint())
    desc = descriptor(generation, config, tables, context, provenance)
    scenario = None
    if scenario_plan is not None:
        from data.anomalies.source_process import (  # noqa: PLC0415
            extend_descriptor,
            scenario_document,
        )

        scenario = scenario_document(tables, context, generation, config, scenario_plan)
        desc = extend_descriptor(desc, scenario["plan"])
    identifier = "source-sha256-" + json_sha256(desc)
    reports = build_reports(
        tables, context, effective, config, scenario_plan=scenario["plan"] if scenario else None
    )
    output_root.mkdir(parents=True, exist_ok=True)
    final = output_root / identifier
    if final.exists():
        _, previous = read_source_dataset(final)
        require(previous["dataset_id"] == identifier, "Existing immutable source differs.")
        return final
    with TemporaryDirectory(prefix=".inventory-source-", dir=output_root) as temporary:
        staging = Path(temporary) / "source"
        staging.mkdir()
        for name in SOURCE_TABLES:
            path = staging / csv_path(name)
            path.parent.mkdir(exist_ok=True)
            with path.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=columns(name), lineterminator="\n")
                writer.writeheader()
                writer.writerows(
                    {k: _csv_value(v) for k, v in r.items()}
                    for r in counted("source_write/" + name, tables[name], total=len(tables[name]))
                )
        (staging / CONFIG_PATH).write_bytes(canonical_json(config.model_dump()) + b"\n")
        if scenario is not None:
            (staging / SCENARIO_PATH).write_bytes(canonical_json(scenario) + b"\n")
        for name, value in reports.items():
            (staging / name).write_bytes(value)
        payload = {
            "schema_version": "2.8.0" if scenario else SOURCE_VERSION,
            "dataset_name": "retailops-synthetic",
            "dataset_id": identifier,
            "descriptor": desc,
            "requested_parameters": requested_parameters(generation),
            "provenance": provenance,
            "generated_at": datetime.now(UTC).isoformat(),
            "artifacts": {n: artifact(staging / csv_path(n), staging) for n in SOURCE_TABLES},
            "inventory_configuration": artifact(staging / CONFIG_PATH, staging),
            "reports": {n: artifact(staging / n, staging) for n in REPORT_NAMES},
            "facts_ready": load_report(reports)["facts_ready"],
            "source_ready": False,
            "inventory_ready": False,
            "model_ready": False,
            "publication_status": "awaiting_ai03_handoff",
        }
        if scenario is not None:
            payload["scenario"] = artifact(staging / SCENARIO_PATH, staging)
        (staging / MANIFEST_FILENAME).write_bytes(canonical_json(payload) + b"\n")
        del tables
        read_source_dataset(staging)
        staging.rename(final)
    return final
