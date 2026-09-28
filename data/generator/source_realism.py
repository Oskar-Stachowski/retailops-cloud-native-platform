from __future__ import annotations

import json
import math
from collections import defaultdict
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

REALISM_POLICY = "observed-sales-realism-1.0.0"


def _metric(
    name: str, sample: int, value: object, threshold: object, status: str, reason: str
) -> dict:
    return {
        "metric_id": name,
        "policy_version": REALISM_POLICY,
        "use_case": "forecast_source",
        "sample_size": sample,
        "value": value,
        "threshold": threshold,
        "status": status,
        "severity": "diagnostic",
        "description": reason,
        "evidence": "realism_report.json",
    }


def build_source_realism(profile: str, seed: int, tables: dict) -> dict:
    revenue = dict.fromkeys((r["id"] for r in tables["product_catalog"]), Decimal(0))
    for row in tables["sales"]:
        revenue[row["product_id"]] += Decimal(row["total_amount"])
    total = sum(revenue.values(), Decimal(0))
    share = (
        float(
            sum(sorted(revenue.values(), reverse=True)[: max(1, math.ceil(len(revenue) * 0.2))])
            / total
        )
        if total
        else None
    )
    basket = len(tables["order_items"]) / len(tables["orders"]) if tables["orders"] else None
    open_rows = [r for r in tables["daily_demand_observations"] if r["location_open"] == "true"]
    zeros = sum(r["observation_status"] == "observed_zero" for r in open_rows)
    metrics = [
        _metric(
            "top_20_percent_catalog_revenue_share",
            len(revenue),
            share,
            {"min": 0.2, "max": 0.95},
            "not_evaluable"
            if len(revenue) < 50 or share is None
            else "passed"
            if 0.2 <= share <= 0.95
            else "warning",
            "Denominator includes unsold catalog products; fewer than 50 products is diagnostic only.",
        ),
        _metric(
            "average_distinct_order_items",
            len(tables["orders"]),
            basket,
            {"min": 1, "max": 5},
            "not_evaluable" if basket is None else "passed" if 1 <= basket <= 5 else "warning",
            "One row per distinct product in an order; units are not item count.",
        ),
        _metric(
            "open_panel_zero_rate",
            len(open_rows),
            zeros / len(open_rows) if open_rows else None,
            {"min": 0, "max": 1},
            "passed" if open_rows else "not_evaluable",
            "Closed days are excluded from denominator; missing never becomes zero.",
        ),
        _metric(
            "causal_promotion_uplift",
            len(tables["sales"]),
            None,
            None,
            "not_ready",
            "Observed promoted/non-promoted means are confounded; simulation truth is not an observed effect.",
        ),
        _metric(
            "stockout_rate",
            0,
            None,
            None,
            "not_ready",
            "Inventory ledger is not qualified before AI-06.",
        ),
    ]
    products = {r["id"]: r["category"] for r in tables["products"]}
    sales = {r["id"]: r for r in tables["sales"]}
    sold, refunded = defaultdict(int), defaultdict(int)
    for row in sales.values():
        sold[(products[row["product_id"]], row["channel"])] += int(row["quantity"])
    for row in tables["return_events"]:
        if row["status"] == "refunded":
            sale = sales[row["sale_id"]]
            refunded[(products[sale["product_id"]], sale["channel"])] += int(row["quantity"])
    for key, units in sorted(sold.items()):
        metrics.append(
            _metric(
                "final_refunded_unit_rate:" + "/".join(key),
                units,
                refunded[key] / units,
                {"min": 0, "max": 1},
                "passed" if 0 <= refunded[key] / units <= 1 else "warning",
                "Qualified refunded quantities over original sold units; includes mature return tail, not historical net labels.",
            )
        )
    return {
        "policy_version": REALISM_POLICY,
        "profile": profile,
        "seed": seed,
        "status": "diagnostic",
        "metrics": metrics,
        "limitations": "Bounded synthetic data is not a production distribution or model benchmark.",
    }


def realism_markdown(report: dict) -> str:
    lines = [
        "# Observed-sales realism",
        "",
        f"Policy: {report['policy_version']}. Status: diagnostic.",
        "",
        "| Metric | Sample | Value | Threshold | Status |",
        "|---|---:|---|---|---|",
    ]
    lines.extend(
        f"| {r['metric_id']} | {r['sample_size']} | {r['value']} | {r['threshold']} | {r['status']} |"
        for r in report["metrics"]
    )
    return "\n".join([*lines, "", report["limitations"], ""])


def write_source_realism(output: Path, report: dict) -> None:
    (output / "realism_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output / "realism_report.md").write_text(realism_markdown(report), encoding="utf-8")
