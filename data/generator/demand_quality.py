from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from data.generator.business_calendar import utc_midnight
from data.generator.commerce_pricing import CommercePricing
from data.generator.demand_contract import validate_demand_row
from data.generator.demand_grid import demand_grid
from data.generator.demand_model import daily_demand
from data.generator.demand_panel import build_daily_panel
from data.generator.demand_schema import DEMAND_COLUMNS, DEMAND_GRAIN, DEMAND_VERSION
from data.generator.dimension_quality import require, timestamp
from data.generator.dimensions import DimensionIndex

if TYPE_CHECKING:
    from pathlib import Path

    from data.generator.configuration import ResolvedGenerationConfig


def _key(row: dict[str, str]) -> tuple[str, ...]:
    return tuple(row[field] for field in DEMAND_GRAIN)


def _schema(tables: dict, _config: ResolvedGenerationConfig) -> int:
    count = 0
    for name in DEMAND_COLUMNS:
        require(
            len({r["id"] for r in tables[name]}) == len(tables[name]),
            "Duplicate demand primary key.",
        )
        for row in tables[name]:
            validate_demand_row(name, row)
            if "available_at" in row:
                timestamp(row["available_at"])
            count += 1
    return count


def _coverage(tables: dict, config: ResolvedGenerationConfig) -> int:
    grid, excluded = demand_grid(tables, config)
    rows = tables["daily_demand_observations"]
    require(
        len({_key(r) for r in rows}) == len(rows) and {_key(r) for r in rows} == grid.keys(),
        "Demand panel missing/extra day or duplicate grain; missing is never zero.",
    )
    require(
        sorted(tables["daily_demand_exclusions"], key=_key) == sorted(excluded, key=_key),
        "Inactive combinations disagree with lifecycle/asortment.",
    )
    require(
        len(grid) + len(excluded) == config.days * config.products * config.stores,
        "Demand denominator disagrees with nominal grid.",
    )
    return len(rows)


def _aggregates(tables: dict, config: ResolvedGenerationConfig) -> int:
    missing = frozenset(
        _key(r) for r in tables["daily_demand_observations"] if r["observation_status"] == "missing"
    )
    expected = build_daily_panel(tables, config, missing_keys=missing)
    require(
        sorted(tables["daily_demand_observations"], key=_key) == expected,
        "Demand aggregates, statuses or availability disagree with source facts.",
    )
    return len(expected)


def _baskets(tables: dict, _config: ResolvedGenerationConfig) -> int:
    grouped = defaultdict(list)
    for item in tables["order_items"]:
        grouped[item["order_id"]].append(item)
    order_ids = {r["id"] for r in tables["orders"]}
    require(grouped.keys() <= order_ids, "Basket references unknown order.")
    for order in tables["orders"]:
        items = grouped[order["id"]]
        require(
            bool(items) and len({r["product_id"] for r in items}) == len(items),
            "Empty basket or repeated SKU in basket.",
        )
        require(
            all(
                int(r["quantity"]) > 0
                and Decimal(r["total_amount"]) == int(r["quantity"]) * Decimal(r["unit_price"])
                and r["currency"] == order["currency"]
                for r in items
            ),
            "Basket line quantities/revenue/currency disagree.",
        )
        require(
            sum((Decimal(r["total_amount"]) for r in items), Decimal(0))
            == Decimal(order["order_total"]),
            "Basket total does not reconcile.",
        )
    return len(order_ids)


def _demand(tables: dict, config: ResolvedGenerationConfig) -> int:
    grid, _ = demand_grid(tables, config)
    products, stores = (
        {r["id"]: r for r in tables["products"]},
        {r["id"]: r for r in tables["stores"]},
    )
    pricing = CommercePricing(tables, DimensionIndex(tables))
    expected = [
        daily_demand(products[key[1]], stores[flags["legacy_store_id"]], key, pricing, config)
        for key, flags in sorted(grid.items())
        if flags["location_open"] == "true"
    ]
    require(
        sorted(tables["daily_demand_truth"], key=_key) == expected,
        "Demand formula/weight/sampling does not match versioned policy.",
    )
    totals = Counter()
    refs = {r["sale_id"]: r for r in tables["sale_price_references"]}
    for row in tables["sales"]:
        totals[_key(refs[row["id"]])] += int(row["quantity"])
        require(
            all(
                row[field] == ""
                for field in (
                    "latent_demand",
                    "stockout_flag",
                    "promotion_uplift",
                    "price_elasticity_effect",
                    "demand_noise",
                )
            ),
            "Daily simulation truth cannot be repeated in transaction facts.",
        )
    require(
        all(totals[_key(row)] == int(row["latent_units"]) for row in expected),
        "Basket allocation changed daily sampled units.",
    )
    return len(expected)


def _complete(tables: dict, config: ResolvedGenerationConfig) -> int:
    rows = tables["daily_demand_observations"]
    require(
        all(
            r["source_data_complete"] == "true" and r["observation_status"] != "missing"
            for r in rows
        ),
        "Complete export requires explicit complete windows; missing remains unknown.",
    )
    require(
        all(
            r["net_revenue"] == r["return_units"] == "" and r["return_data_complete"] == "false"
            for r in rows
        ),
        "Unqualified legacy returns cannot become net revenue or zero returns.",
    )
    boundary = timestamp(utc_midnight(config.end_date + timedelta(days=1)))
    require(
        all(timestamp(r["available_at"]) <= boundary for r in rows),
        "Complete panel contains data after its declared snapshot boundary.",
    )
    return len(rows)


def build_demand_report(
    tables: dict[str, list[dict[str, Any]]], config: ResolvedGenerationConfig
) -> dict[str, Any]:
    checks = []
    for check_id, function in (
        ("demand_schema", _schema),
        ("daily_panel_coverage", _coverage),
        ("daily_transaction_aggregation", _aggregates),
        ("basket_sku_totals", _baskets),
        ("daily_demand_budget", _demand),
        ("daily_source_completeness", _complete),
    ):
        try:
            sample = function(tables, config)
            status, description, value = "passed", "All required records satisfy the policy.", 0
        except (ValueError, KeyError, TypeError, ArithmeticError) as error:
            sample, status, description, value = 0, "failed", str(error), 1
        checks.append(
            {
                "check_id": check_id,
                "policy_version": DEMAND_VERSION,
                "use_case": "source_daily_demand",
                "severity": "hard",
                "status": status,
                "sample_size": sample,
                "value": value,
                "threshold": 0,
                "description": description,
                "evidence": "demand_report.json",
            }
        )
    passed = all(c["status"] == "passed" for c in checks)
    counts = Counter(
        r.get("observation_status") for r in tables.get("daily_demand_observations", [])
    )
    return {
        "policy_version": DEMAND_VERSION,
        "status": "passed" if passed else "failed",
        "checks": checks,
        "complete_daily_panel": passed,
        "daily_panel_coverage_percent": 100 if passed else None,
        "valid_daily_combinations": len(tables.get("daily_demand_observations", [])),
        "nominal_daily_combinations": config.days * config.products * config.stores,
        "inactive_combinations": len(tables.get("daily_demand_exclusions", [])),
        "observation_status_counts": dict(sorted(counts.items())),
        "inventory_ready": False,
        "returns_ready": False,
        "sampling": "stochastic_rounding_without_inventory_cap",
    }


def validate_demand(tables: dict, config: ResolvedGenerationConfig) -> dict:
    report = build_demand_report(tables, config)
    if report["status"] != "passed":
        msg = "Demand hard gate failed: " + "; ".join(
            c["check_id"] + ": " + c["description"]
            for c in report["checks"]
            if c["status"] == "failed"
        )
        raise ValueError(msg)
    return report


def demand_report_markdown(report: dict) -> str:
    rows = [
        "# Daily demand quality",
        "",
        f"Policy: {report['policy_version']}. Status: {report['status']}.",
        "",
        "| Check | Status | Sample size |",
        "|---|---|---:|",
    ]
    rows.extend(
        f"| {c['check_id']} | {c['status']} | {c['sample_size']} |" for c in report["checks"]
    )
    rows.extend(
        [
            "",
            f"Valid panel rows: {report['valid_daily_combinations']}; excluded inactive: {report['inactive_combinations']}.",
            "Inventory and return reconciliation are not ready.",
            "",
        ]
    )
    return "\n".join(rows)


def write_demand_report(output: Path, report: dict) -> None:
    (output / "demand_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output / "demand_report.md").write_text(demand_report_markdown(report), encoding="utf-8")
