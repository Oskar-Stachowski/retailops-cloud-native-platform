#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


REQUIRED_EVENT_CONTRACT_FIELDS = {
    "contract_name",
    "version",
    "envelope",
    "supported_event_types",
    "supported_topics",
    "persistence",
}


class ContractFailure(Exception):
    pass


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ContractFailure(f"Missing JSON file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ContractFailure(f"Invalid JSON file {path}: {exc}") from exc


def csv_header(path: Path) -> list[str]:
    try:
        with path.open(newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            return list(reader.fieldnames or [])
    except FileNotFoundError as exc:
        raise ContractFailure(f"Missing CSV file: {path}") from exc


def csv_row_count(path: Path) -> int:
    with path.open(newline="", encoding="utf-8") as file:
        return sum(1 for _ in csv.DictReader(file))


def validate_dataset_contract(contract_path: Path, data_dir: Path) -> tuple[list[dict[str, Any]], dict[str, int]]:
    contract = load_json(contract_path)
    checks: list[dict[str, Any]] = []
    row_counts: dict[str, int] = {}

    tables = contract.get("tables")
    if not isinstance(tables, list) or not tables:
        raise ContractFailure("Dataset contract must contain a non-empty 'tables' list.")

    seen_tables: set[str] = set()
    for table in tables:
        name = str(table.get("name", ""))
        filename = str(table.get("filename", ""))
        required_columns = table.get("required_columns")

        if not name or not filename:
            raise ContractFailure("Each table contract must define 'name' and 'filename'.")
        if name in seen_tables:
            raise ContractFailure(f"Duplicate table contract: {name}")
        if not isinstance(required_columns, list) or not required_columns:
            raise ContractFailure(f"Table contract {name} must define required_columns.")

        seen_tables.add(name)
        csv_path = data_dir / filename
        actual_header = csv_header(csv_path)
        missing_columns = sorted(set(required_columns) - set(actual_header))
        unexpected_status = "failed" if missing_columns else "passed"
        row_counts[name] = csv_row_count(csv_path)
        checks.append(
            {
                "name": f"{name}_csv_columns_match_contract",
                "status": unexpected_status,
                "details": {
                    "file": str(csv_path),
                    "required_columns": required_columns,
                    "actual_columns": actual_header,
                    "missing_columns": missing_columns,
                    "row_count": row_counts[name],
                },
            },
        )

    validation = contract.get("validation", {})
    quality_report_file = validation.get("quality_report_file")
    required_quality_status = validation.get("required_quality_status")
    if quality_report_file and required_quality_status:
        quality_report = load_json(data_dir / str(quality_report_file))
        actual_status = quality_report.get("status")
        checks.append(
            {
                "name": "quality_report_status_matches_contract",
                "status": "passed" if actual_status == required_quality_status else "failed",
                "details": {
                    "file": str(data_dir / str(quality_report_file)),
                    "required_status": required_quality_status,
                    "actual_status": actual_status,
                },
            },
        )

    seeded_tables = set(validation.get("seeded_db_tables", []))
    contract_tables = {table.get("name") for table in tables}
    missing_seeded_tables = sorted(seeded_tables - contract_tables)
    checks.append(
        {
            "name": "seeded_db_tables_have_contracts",
            "status": "passed" if not missing_seeded_tables else "failed",
            "details": {
                "seeded_db_tables": sorted(seeded_tables),
                "missing_seeded_tables": missing_seeded_tables,
            },
        },
    )

    return checks, row_counts


def validate_event_contract(event_contract_path: Path) -> list[dict[str, Any]]:
    event_contract = load_json(event_contract_path)
    checks: list[dict[str, Any]] = []

    missing_top_level = sorted(REQUIRED_EVENT_CONTRACT_FIELDS - set(event_contract))
    envelope = event_contract.get("envelope", {})
    required_envelope_fields = envelope.get("required_fields", [])
    missing_envelope_basics = sorted(
        set(
            [
                "event_id",
                "event_type",
                "topic",
                "schema_version",
                "source",
                "correlation_id",
                "occurred_at",
                "ingested_at",
                "payload",
            ],
        )
        - set(required_envelope_fields),
    )

    checks.append(
        {
            "name": "event_contract_shape_is_valid",
            "status": "passed" if not missing_top_level and not missing_envelope_basics else "failed",
            "details": {
                "file": str(event_contract_path),
                "missing_top_level_fields": missing_top_level,
                "missing_envelope_fields": missing_envelope_basics,
                "supported_event_type_count": len(event_contract.get("supported_event_types", [])),
                "supported_topic_count": len(event_contract.get("supported_topics", [])),
            },
        },
    )

    return checks


def write_report(report_path: Path, checks: list[dict[str, Any]], row_counts: dict[str, int]) -> dict[str, Any]:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    failed = [check for check in checks if check["status"] != "passed"]
    report = {
        "status": "passed" if not failed else "failed",
        "generated_at": datetime.now(UTC).isoformat(),
        "summary": {
            "checks": len(checks),
            "passed": len(checks) - len(failed),
            "failed": len(failed),
        },
        "row_counts": row_counts,
        "checks": checks,
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate RetailOps data and event contracts.")
    parser.add_argument(
        "--contract",
        type=Path,
        default=Path("data/contracts/retailops_seed_dataset.contract.json"),
    )
    parser.add_argument("--data-dir", type=Path, default=Path("data/demo"))
    parser.add_argument(
        "--event-contract",
        type=Path,
        default=Path("events/contracts/retailops-realtime-events.v1.contract.json"),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("ci-cd/reports/data/data-contract-report.json"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        dataset_checks, row_counts = validate_dataset_contract(args.contract, args.data_dir)
        event_checks = validate_event_contract(args.event_contract)
        report = write_report(args.report, dataset_checks + event_checks, row_counts)
    except ContractFailure as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"Data contract status: {report['status']}")
    print(f"Data contract report: {args.report}")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
