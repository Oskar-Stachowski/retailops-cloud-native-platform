from __future__ import annotations

import json
from typing import TYPE_CHECKING

from data.generator.csv_writer import source_columns, source_table_order
from data.generator.demand_quality import build_demand_report
from data.generator.dimension_quality import build_dimensions_report, require
from data.generator.observation_history import HISTORY_TABLE, validate_daily_versions
from data.generator.pricing_quality import build_pricing_report
from data.generator.quality import build_quality_report
from data.generator.return_quality import build_return_report
from data.generator.simulation import validate_simulation
from ml.features.fact_input import (
    FACT_COLUMNS,
    FACT_INPUT_VERSION,
    HISTORY_FACT_COLUMNS,
    HISTORY_INPUT_VERSION,
    validate_fact_input,
)
from ml.features.worker import transform

if TYPE_CHECKING:
    from pathlib import Path

    from data.generator.configuration import ResolvedGenerationConfig

SOURCE_POLICY = "forecast-source-acceptance-1.0.0"


def project_facts(tables: dict) -> dict:
    columns_by_table = HISTORY_FACT_COLUMNS if HISTORY_TABLE in tables else FACT_COLUMNS
    payload = {
        "policy_version": HISTORY_INPUT_VERSION if HISTORY_TABLE in tables else FACT_INPUT_VERSION,
        "tables": {
            name: [{field: row[field] for field in columns} for row in tables[name]]
            for name, columns in columns_by_table.items()
        },
    }
    validate_fact_input(payload)
    return payload


def _fact_schema(tables: dict, config: ResolvedGenerationConfig) -> int:
    schema_version = "2.6.0" if HISTORY_TABLE in tables else "2.5.0"
    require(
        set(tables) == set(source_table_order(config.profile, schema_version)),
        "Source table set disagrees.",
    )
    for name, rows in tables.items():
        require(
            all(
                set(row) == set(source_columns(name, config.profile, schema_version))
                for row in rows
            ),
            "Source fact columns reject mixed simulation fields: " + name,
        )
    return sum(map(len, tables.values()))


def build_source_report(tables: dict, config: ResolvedGenerationConfig) -> dict:
    policy = "forecast-source-acceptance-1.1.0" if HISTORY_TABLE in tables else SOURCE_POLICY
    legacy = build_quality_report(config.profile, tables)
    count = sum(map(len, tables.values()))
    checks = [
        {
            "check_id": "legacy:" + check["name"],
            "policy_version": "legacy-structural-1.0.0",
            "use_case": "forecast_source",
            "severity": "hard",
            "sample_size": count,
            "value": 0 if check["status"] == "passed" else 1,
            "threshold": 0,
            "status": check["status"],
            "evidence": "quality_report.json",
            "description": check["details"],
        }
        for check in legacy["checks"]
    ]
    for builder in (
        build_dimensions_report,
        build_pricing_report,
        build_demand_report,
        build_return_report,
    ):
        report = builder(tables, config)
        checks.extend(report["checks"])
    operations = {
        "fact_schema_without_simulation": lambda: _fact_schema(tables, config),
        "simulation_parameters_schema_coverage": lambda: validate_simulation(tables),
        "feature_fact_projection": lambda: len(transform(project_facts(tables))),
    }
    if HISTORY_TABLE in tables:
        operations["append_only_observation_history"] = lambda: validate_daily_versions(tables)
    for name, operation in operations.items():
        try:
            sample, status, detail = (
                operation(),
                "passed",
                "All required records satisfy the policy.",
            )
        except (ValueError, KeyError, TypeError, ArithmeticError) as error:
            sample, status, detail = count, "failed", str(error)
        checks.append(
            {
                "check_id": name,
                "policy_version": policy,
                "use_case": "forecast_source",
                "severity": "hard",
                "sample_size": sample,
                "value": 0 if status == "passed" else 1,
                "threshold": 0,
                "status": status,
                "evidence": "source_report.json",
                "description": detail,
            }
        )
    passed = all(check["status"] == "passed" for check in checks)
    readiness = {
        "forecast_source": (
            "ready" if passed else "not_ready",
            "AI-03 snapshot/curated input; observed_sales_units only",
        ),
        "forecasting": (
            "not_ready",
            "AI-03/04 snapshot, training and fixed-origin assessment required",
        ),
        "anomaly": ("not_ready", "AI-05 labels and evaluation required"),
        "stockout": ("not_ready", "AI-06 inventory ledger and reliable availability required"),
        "replay": ("not_ready", "AI-03/04 historical correction snapshots required"),
        "rag": ("not_applicable", "Source sales qualification does not qualify RAG"),
    }
    return {
        "policy_version": policy,
        "status": "passed" if passed else "failed",
        "checks": checks,
        "source_ready": passed,
        "inventory_ready": False,
        "target_type": "observed_sales_units",
        "readiness": {
            name: {
                "policy_version": policy,
                "sample_size": count,
                "value": passed if name == "forecast_source" else None,
                "threshold": True,
                "status": status,
                "evidence": "source_report.json",
                "reason": reason,
            }
            for name, (status, reason) in readiness.items()
        },
    }


def validate_source_report(tables: dict, config: ResolvedGenerationConfig) -> dict:
    report = build_source_report(tables, config)
    require(
        report["status"] == "passed",
        "Source hard gate failed: "
        + "; ".join(str(c["check_id"]) for c in report["checks"] if c["status"] == "failed"),
    )
    return report


def source_report_markdown(report: dict) -> str:
    lines = [
        "# Source acceptance",
        "",
        f"Policy: {report['policy_version']}. Status: {report['status']}.",
        "",
        "| Check | Status | Sample | Value | Threshold | Evidence |",
        "|---|---|---:|---|---|---|",
    ]
    lines.extend(
        f"| {c['check_id']} | {c['status']} | {c['sample_size']} | {c['value']} | {c['threshold']} | {c['evidence']} |"
        for c in report["checks"]
    )
    lines.extend(["", "| Use case | Status | Reason |", "|---|---|---|"])
    lines.extend(
        f"| {name} | {r['status']} | {r['reason']} |" for name, r in report["readiness"].items()
    )
    return "\n".join([*lines, ""])


def write_source_report(output: Path, report: dict) -> None:
    (output / "source_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output / "source_report.md").write_text(source_report_markdown(report), encoding="utf-8")
