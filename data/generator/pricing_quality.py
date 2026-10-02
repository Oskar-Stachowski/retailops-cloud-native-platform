from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from itertools import pairwise
from typing import TYPE_CHECKING, Any

from data.generator.business_calendar import utc_midnight
from data.generator.dimension_quality import require, timestamp
from data.generator.dimensions import DimensionIndex
from data.generator.price_resolver import PriceResolver
from data.generator.pricing_contract import validate_pricing_row
from data.generator.pricing_plans import (
    daily_price_observations,
    legacy_pricing_projection,
    plan_key,
)
from data.generator.pricing_schema import PRICING_COLUMNS, PRICING_VERSION
from data.generator.promotion_truth import build_promotion_truth

if TYPE_CHECKING:
    from pathlib import Path

    from data.generator.configuration import ResolvedGenerationConfig


def _schema(tables: dict[str, list[dict[str, Any]]], config: ResolvedGenerationConfig) -> int:
    products = {r["id"] for r in tables["products"]}
    locations = {r["id"] for r in tables["selling_locations"]}
    count = 0
    for name in PRICING_COLUMNS:
        rows = tables[name]
        require(len({r["id"] for r in rows}) == len(rows), "Duplicate pricing primary key.")
        for row in rows:
            validate_pricing_row(name, row)
            for field in {"effective_from", "effective_to", "business_date"} & row.keys():
                date.fromisoformat(row[field])
            for field in {"known_at", "available_at", "as_of_time"} & row.keys():
                timestamp(row[field])
            count += 1
    require(bool(tables["price_plans"]), "Price plans are required.")
    for name, key_field in (("price_plans", "plan_key"), ("promotion_plans", "promotion_key")):
        grouped = defaultdict(list)
        for row in tables[name]:
            require(row["product_id"] in products, "Unknown plan product.")
            require(
                row["scope"] in {"location", "location_channel"}
                if row["selling_location_id"]
                else row["scope"] in {"global", "channel"},
                "Plan location scope is inconsistent.",
            )
            require(
                row["scope"] in {"channel", "location_channel"}
                if row["channel"] != "all"
                else row["scope"] in {"global", "location"},
                "Plan channel scope is inconsistent.",
            )
            require(
                not row["selling_location_id"] or row["selling_location_id"] in locations,
                "Unknown plan location.",
            )
            key = plan_key(
                row["product_id"], row["scope"], row["selling_location_id"], row["channel"]
            )
            require(
                row[key_field] == (key if name == "price_plans" else "campaign:" + key),
                "Plan key disagrees with scope.",
            )
            require(row["effective_from"] < row["effective_to"], "Reversed or empty plan period.")
            require(
                timestamp(row["known_at"]) <= timestamp(row["available_at"]),
                "Plan is available before it is known.",
            )
            if name == "price_plans":
                require(Decimal(row["price"]) > 0, "Regular price must be positive.")
            else:
                require(
                    Decimal(row["discount_percent"]) < 100,
                    "Promotion discount must be below 100 percent.",
                )
                require(
                    int(row["minimum_quantity"]) == (2 if row["promotion_type"] == "bundle" else 1),
                    "Promotion quantity rule is inconsistent.",
                )
            grouped[row[key_field]].append(row)
        for rows in grouped.values():
            require(len({r["version"] for r in rows}) == len(rows), "Repeated plan version.")
            windows = sorted({(r["effective_from"], r["effective_to"]) for r in rows})
            require(
                all(a[1] <= b[0] for a, b in pairwise(windows)),
                "Ambiguous overlapping plan periods.",
            )
            if name == "promotion_plans":
                require(
                    len(windows) == 1, "Campaign revisions cannot change their effective period."
                )
            for window in windows:
                revisions = sorted(
                    (r for r in rows if (r["effective_from"], r["effective_to"]) == window),
                    key=lambda r: int(r["version"]),
                )
                require(
                    all(
                        timestamp(a["available_at"]) < timestamp(b["available_at"])
                        and timestamp(a["known_at"]) <= timestamp(b["known_at"])
                        for a, b in pairwise(revisions)
                    ),
                    "Revision knowledge must increase strictly.",
                )
    for row in tables["daily_price_observations"]:
        require(
            config.start_date.isoformat() <= row["business_date"] <= config.end_date.isoformat(),
            "Price observation outside history.",
        )
    return count


def _coverage(tables: dict[str, list[dict[str, Any]]], config: ResolvedGenerationConfig) -> int:
    resolver = PriceResolver(tables)
    count = 0
    for row in tables["assortment"]:
        current = date.fromisoformat(row["effective_from"])
        while current.isoformat() < row["effective_to"]:
            day = current.isoformat()
            require(
                config.start_date <= current <= config.planning_end_date,
                "Price coverage exceeds declared history and known forecast plans.",
            )
            for quantity in (0, 1, 2):
                resolver.resolve(
                    row["product_id"],
                    row["selling_location_id"],
                    row["channel"],
                    day,
                    utc_midnight(current)
                    if current <= config.end_date
                    else (
                        timestamp(utc_midnight(config.end_date + timedelta(days=1)))
                        - timedelta(seconds=1)
                    ).isoformat(),
                    quantity,
                )
            count += 1
            current += timedelta(days=1)
    require(count > 0, "Price coverage has no valid combinations.")
    return count


def _transactions(
    tables: dict[str, list[dict[str, Any]]], _config: ResolvedGenerationConfig
) -> int:
    resolver, index = PriceResolver(tables), DimensionIndex(tables)
    sales = {r["id"]: r for r in tables["sales"]}
    refs = {r["sale_id"]: r for r in tables["sale_price_references"]}
    items = {r["id"]: r for r in tables["order_items"]}
    orders = {r["order_reference"]: r for r in tables["orders"]}
    require(
        len(refs) == len(tables["sale_price_references"]) == len(sales)
        and refs.keys() == sales.keys(),
        "Sale pricing references are incomplete or duplicated.",
    )
    require(
        len({r["order_item_id"] for r in refs.values()}) == len(items) == len(refs),
        "Order item pricing links are incomplete or repeated.",
    )
    for sale_id, sale in sales.items():
        ref, order = refs[sale_id], orders[sale["order_reference"]]
        item = items[ref["order_item_id"]]
        day = timestamp(sale["sold_at"]).date().isoformat()
        assignment = index.assignment(order["store_id"], day, order["ordered_at"])
        require(
            assignment is not None
            and ref["selling_location_id"] == assignment["selling_location_id"]
            and ref["channel"] == sale["channel"]
            and ref["product_id"] == sale["product_id"]
            and ref["business_date"] == day,
            "Sale pricing scope disagrees with dimensions.",
        )
        quote = resolver.resolve(
            sale["product_id"],
            ref["selling_location_id"],
            ref["channel"],
            day,
            order["ordered_at"],
            int(sale["quantity"]),
        )
        require(
            ref["price_plan_id"] == quote.price_plan_id
            and ref["promotion_plan_id"] == quote.promotion_plan_id,
            "Sale references wrong or inactive plan.",
        )
        require(
            timestamp(ref["as_of_time"]) == timestamp(order["ordered_at"]),
            "Sale quote cutoff differs from order business time.",
        )
        require(
            Decimal(sale["unit_price"]) == quote.unit_price
            and Decimal(sale["total_amount"]) == quote.total_amount
            and sale["currency"] == quote.currency,
            "Sale price or discount disagrees with known plan.",
        )
        require(
            sale["promotion_applied"] == str(bool(quote.promotion_plan_id)).lower(),
            "Promotion flag disagrees with qualified active plan.",
        )
        require(
            item["order_id"] == order["id"]
            and item["product_id"] == sale["product_id"]
            and all(
                item[field] == sale[field]
                for field in ("quantity", "unit_price", "total_amount", "currency")
            ),
            "Order item and sale prices disagree.",
        )
        require(
            sale.get("promotion_uplift", "") == "",
            "Promotion effects belong to simulation truth, not sales.",
        )
    totals = defaultdict(Decimal)
    for item in items.values():
        totals[item["order_id"]] += Decimal(item["total_amount"])
    for order in tables["orders"]:
        require(
            totals[order["id"]] == Decimal(order["order_total"]), "Order total does not reconcile."
        )
    return len(sales)


def _aggregates(tables: dict[str, list[dict[str, Any]]], _config: ResolvedGenerationConfig) -> int:
    expected = daily_price_observations(tables["sales"], tables["sale_price_references"])
    require(
        sorted(tables["daily_price_observations"], key=lambda r: r["id"])
        == sorted(expected, key=lambda r: r["id"]),
        "Realized price aggregates do not reconcile with sales.",
    )
    return len(expected)


def _adapter(tables: dict[str, list[dict[str, Any]]], _config: ResolvedGenerationConfig) -> int:
    prices, promotions = legacy_pricing_projection(tables)
    require(
        sorted(tables["price_history"], key=lambda r: r["id"])
        == sorted(prices, key=lambda r: r["id"])
        and sorted(tables["promotions"], key=lambda r: r["id"])
        == sorted(promotions, key=lambda r: r["id"]),
        "Legacy pricing projection differs from canonical plans.",
    )
    return len(prices) + len(promotions)


def _truth(tables: dict[str, list[dict[str, Any]]], _config: ResolvedGenerationConfig) -> int:
    expected = build_promotion_truth(tables["promotion_plans"])
    require(
        sorted(tables["promotion_effect_truth"], key=lambda r: r["id"])
        == sorted(expected, key=lambda r: r["id"]),
        "Promotion pre/during/post truth has wrong dates, phases or multipliers.",
    )
    return len(expected)


def build_pricing_report(
    tables: dict[str, list[dict[str, Any]]], config: ResolvedGenerationConfig
) -> dict[str, Any]:
    checks = []
    for name, operation in {
        "pricing_schema_versions_scope": _schema,
        "known_price_coverage_and_priority": _coverage,
        "transaction_price_reconciliation": _transactions,
        "realized_price_aggregates": _aggregates,
        "legacy_pricing_adapter": _adapter,
        "promotion_truth_direction": _truth,
    }.items():
        try:
            count, status, detail = (
                operation(tables, config),
                "passed",
                "All required records satisfy the policy.",
            )
        except (ValueError, KeyError, TypeError, ArithmeticError) as error:
            count, status, detail = 0, "failed", str(error)
        checks.append(
            {
                "check_id": name,
                "policy_version": PRICING_VERSION,
                "use_case": "source_pricing",
                "severity": "hard",
                "status": status,
                "sample_size": count,
                "value": 0 if status == "passed" else 1,
                "threshold": 0,
                "description": detail,
                "evidence": "pricing_report.json",
            }
        )
    coverage = checks[1]
    return {
        "policy_version": PRICING_VERSION,
        "status": "passed" if all(c["status"] == "passed" for c in checks) else "failed",
        "checks": checks,
        "valid_daily_combinations": coverage["sample_size"],
        "price_coverage_percent": 100 if coverage["status"] == "passed" else None,
        "realized_prices_are_outcomes": True,
        "complete_daily_panel": False,
        "inventory_ready": False,
    }


def validate_pricing(
    tables: dict[str, list[dict[str, Any]]], config: ResolvedGenerationConfig
) -> dict[str, Any]:
    report = build_pricing_report(tables, config)
    require(report["status"] == "passed", "Canonical pricing hard gate failed.")
    return report


def pricing_report_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Source pricing quality",
        "",
        "Policy: " + report["policy_version"],
        "Status: " + report["status"],
        "",
        "| Check | Status | Sample size |",
        "|---|---|---:|",
    ]
    lines.extend(
        f"| {r['check_id']} | {r['status']} | {r['sample_size']} |" for r in report["checks"]
    )
    lines.extend(
        ["", "Realized prices are outcomes. Complete daily panel: false. Inventory ready: false."]
    )
    return "\n".join(lines) + "\n"


def write_pricing_report(output_dir: Path, report: dict[str, Any]) -> None:
    (output_dir / "pricing_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output_dir / "pricing_report.md").write_text(pricing_report_markdown(report), encoding="utf-8")
