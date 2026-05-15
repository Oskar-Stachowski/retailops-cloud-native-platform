#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class ScenarioReportFailure(Exception):
    pass


def read_csv_rows(data_dir: Path, filename: str) -> list[dict[str, str]]:
    path = data_dir / filename
    try:
        with path.open(newline="", encoding="utf-8") as file:
            return list(csv.DictReader(file))
    except FileNotFoundError as exc:
        raise ScenarioReportFailure(f"Missing CSV file: {path}") from exc


def values(rows: list[dict[str, str]], column: str) -> set[str]:
    return {row[column] for row in rows if row.get(column)}


def count_values(rows: list[dict[str, str]], column: str) -> dict[str, int]:
    return dict(sorted(Counter(row[column] for row in rows if row.get(column)).items()))


def build_report(data_dir: Path) -> dict[str, Any]:
    products = read_csv_rows(data_dir, "products.csv")
    forecasts = read_csv_rows(data_dir, "forecasts.csv")
    anomalies = read_csv_rows(data_dir, "anomalies.csv")
    alerts = read_csv_rows(data_dir, "alerts.csv")
    recommendations = read_csv_rows(data_dir, "recommendations.csv")
    inventory_snapshots = read_csv_rows(data_dir, "inventory_snapshots.csv")

    anomaly_types = values(anomalies, "anomaly_type")
    alert_types = values(alerts, "alert_type")
    recommendation_types = values(recommendations, "recommendation_type")
    recommendation_rationales = values(recommendations, "rationale")
    product_ids = values(products, "id")
    forecast_product_ids = values(forecasts, "product_id")
    missing_forecast_products = sorted(product_ids - forecast_product_ids)

    checks = [
        {
            "name": "sales_drop_present",
            "status": "passed" if "sales_drop" in anomaly_types and "sales_drop" in alert_types else "failed",
            "evidence": "anomalies.anomaly_type and alerts.alert_type",
        },
        {
            "name": "sales_spike_present",
            "status": "passed" if "sales_spike" in anomaly_types else "failed",
            "evidence": "anomalies.anomaly_type",
        },
        {
            "name": "stale_inventory_present",
            "status": "passed" if "stale_inventory" in anomaly_types else "failed",
            "evidence": "anomalies.anomaly_type",
        },
        {
            "name": "stockout_risk_present",
            "status": "passed"
            if "stockout_risk" in alert_types or "stockout_risk" in recommendation_rationales
            else "failed",
            "evidence": "alerts.alert_type or recommendations.rationale",
        },
        {
            "name": "overstock_risk_present",
            "status": "passed" if "overstock_risk" in alert_types else "failed",
            "evidence": "alerts.alert_type",
        },
        {
            "name": "missing_forecast_context_present",
            "status": "passed" if missing_forecast_products else "failed",
            "evidence": "products without forecast rows",
        },
        {
            "name": "inventory_freshness_context_present",
            "status": "passed"
            if all(row.get("recorded_at") and row.get("ingested_at") for row in inventory_snapshots)
            else "failed",
            "evidence": "inventory_snapshots.recorded_at and ingested_at",
        },
    ]

    failed = [check for check in checks if check["status"] != "passed"]
    return {
        "status": "passed" if not failed else "failed",
        "generated_at": datetime.now(UTC).isoformat(),
        "data_dir": str(data_dir),
        "summary": {
            "checks": len(checks),
            "passed": len(checks) - len(failed),
            "failed": len(failed),
        },
        "row_counts": {
            "products": len(products),
            "forecasts": len(forecasts),
            "anomalies": len(anomalies),
            "alerts": len(alerts),
            "recommendations": len(recommendations),
            "inventory_snapshots": len(inventory_snapshots),
        },
        "coverage": {
            "anomaly_type_counts": count_values(anomalies, "anomaly_type"),
            "alert_type_counts": count_values(alerts, "alert_type"),
            "recommendation_type_counts": count_values(recommendations, "recommendation_type"),
            "recommendation_rationale_counts": count_values(recommendations, "rationale"),
            "products_without_forecasts": missing_forecast_products,
        },
        "checks": checks,
    }


def write_json(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    coverage = report["coverage"]
    lines = [
        "# RetailOps scenario coverage report",
        "",
        f"Generated at: `{report['generated_at']}`",
        f"Data directory: `{report['data_dir']}`",
        f"Status: **{report['status'].upper()}**",
        "",
        "## Checks",
        "",
        "| Check | Status | Evidence |",
        "| --- | --- | --- |",
    ]
    for check in report["checks"]:
        lines.append(f"| `{check['name']}` | `{check['status']}` | {check['evidence']} |")

    lines.extend(
        [
            "",
            "## Scenario counts",
            "",
            "### Anomaly types",
            "",
            "| Type | Count |",
            "| --- | ---: |",
        ],
    )
    for name, count in coverage["anomaly_type_counts"].items():
        lines.append(f"| `{name}` | {count} |")

    lines.extend(["", "### Alert types", "", "| Type | Count |", "| --- | ---: |"])
    for name, count in coverage["alert_type_counts"].items():
        lines.append(f"| `{name}` | {count} |")

    lines.extend(
        [
            "",
            "### Recommendation types",
            "",
            "| Type | Count |",
            "| --- | ---: |",
        ],
    )
    for name, count in coverage["recommendation_type_counts"].items():
        lines.append(f"| `{name}` | {count} |")

    lines.extend(
        [
            "",
            "## Missing forecast context",
            "",
            f"Products without forecast rows: `{len(coverage['products_without_forecasts'])}`",
            "",
            "This is intentional demo evidence for UI/API paths that must handle products without forecasts.",
            "",
            "## Claim boundary",
            "",
            "Safe claim: the demo dataset contains deterministic operational scenarios for sales drops, sales spikes, stale inventory, stockout risk, overstock risk and products without forecasts.",
            "",
            "Careful claim: this does not mean every production data-quality edge case is modeled; it is a portfolio readiness gate for representative retail operations scenarios.",
            "",
        ],
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate RetailOps scenario coverage evidence.")
    parser.add_argument("--data-dir", type=Path, default=Path("data/demo"))
    parser.add_argument(
        "--json-report",
        type=Path,
        default=Path("ci-cd/reports/data/scenario-coverage-report.json"),
    )
    parser.add_argument(
        "--markdown-report",
        type=Path,
        default=Path("docs/evidence/data/scenario-coverage-report.md"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = build_report(args.data_dir)
        write_json(args.json_report, report)
        write_markdown(args.markdown_report, report)
    except ScenarioReportFailure as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"Scenario coverage status: {report['status']}")
    print(f"Scenario coverage JSON: {args.json_report}")
    print(f"Scenario coverage Markdown: {args.markdown_report}")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
