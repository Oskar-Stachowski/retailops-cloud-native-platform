from __future__ import annotations

import json
import math
from collections import defaultdict
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

REALISM_POLICY = "observed-sales-realism-1.1.0"
MIN_SEGMENT_SAMPLE = 30


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


def _segment_metrics(tables: dict) -> list[dict]:
    products = {r["id"]: r["category"] for r in tables["products"]}
    buckets = {r["product_id"]: r["demand_class"] for r in tables["product_simulation_parameters"]}

    def segment(row: dict) -> tuple[str, str, str]:
        return buckets[row["product_id"]], products[row["product_id"]], row["channel"]

    open_days, zero_days = defaultdict(int), defaultdict(int)
    for row in tables["daily_demand_observations"]:
        key = segment(row)
        open_days[key] += row["location_open"] == "true"
        zero_days[key] += row["observation_status"] == "observed_zero"
    sales = {r["id"]: r for r in tables["sales"]}
    sold, refunded = defaultdict(int), defaultdict(int)
    for row in sales.values():
        sold[segment(row)] += int(row["quantity"])
    for row in tables["return_events"]:
        if row["status"] == "refunded":
            refunded[segment(sales[row["sale_id"]])] += int(row["quantity"])
    metrics = []
    for name, numerators, denominators, description in (
        (
            "open_panel_zero_rate",
            zero_days,
            open_days,
            "Open active days only; closed/missing are not zero observations.",
        ),
        (
            "final_refunded_unit_rate",
            refunded,
            sold,
            "Qualified refunded units over original sold units, including mature tail; no historical label rewrite.",
        ),
    ):
        for key, sample in sorted(denominators.items()):
            value = numerators[key] / sample if sample else None
            metric = _metric(
                name + ":" + "/".join(key),
                sample,
                value,
                {"min": 0, "max": 1, "minimum_sample": MIN_SEGMENT_SAMPLE},
                "not_evaluable"
                if sample < MIN_SEGMENT_SAMPLE
                else "passed"
                if 0 <= value <= 1
                else "warning",
                description,
            )
            metric["segment"] = dict(
                zip(("demand_bucket", "category", "channel"), key, strict=True)
            )
            metrics.append(metric)
    return metrics


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
            {"min": 0.45, "max": 0.80, "minimum_sample": 50},
            "not_evaluable"
            if len(revenue) < 50 or share is None
            else "passed"
            if 0.45 <= share <= 0.80
            else "warning",
            "Denominator includes unsold catalog products; fewer than 50 products is diagnostic only.",
        ),
        _metric(
            "average_distinct_order_items",
            len(tables["orders"]),
            basket,
            {"min": 1.2, "max": 3.5, "minimum_sample": MIN_SEGMENT_SAMPLE},
            "not_evaluable"
            if len(tables["orders"]) < MIN_SEGMENT_SAMPLE
            else "passed"
            if 1.2 <= basket <= 3.5
            else "warning",
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
    metrics.extend(_segment_metrics(tables))
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
