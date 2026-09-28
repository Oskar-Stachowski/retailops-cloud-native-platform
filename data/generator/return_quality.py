from __future__ import annotations

import json
from collections import Counter
from datetime import timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from data.generator.dimension_quality import require, timestamp
from data.generator.return_contract import validate_return_row
from data.generator.return_events import build_return_policies
from data.generator.return_reconciliation import (
    build_return_cohorts,
    legacy_return_projection,
    return_boundaries,
)
from data.generator.return_schema import RETURN_COLUMNS, RETURN_TAIL_DAYS, RETURNS_VERSION

if TYPE_CHECKING:
    from pathlib import Path

    from data.generator.configuration import ResolvedGenerationConfig


def _index(rows: list[dict]) -> dict[str, dict]:
    result = {r["id"]: r for r in rows}
    require(len(result) == len(rows), "Duplicate transaction primary key.")
    return result


def _schema(tables: dict, _config: ResolvedGenerationConfig) -> int:
    count = 0
    for name in RETURN_COLUMNS:
        _index(tables[name])
        for row in tables[name]:
            validate_return_row(name, row)
            count += 1
    return count


def _policies(tables: dict, config: ResolvedGenerationConfig) -> int:
    require(
        sorted(tables["return_policies"], key=lambda r: r["id"])
        == sorted(build_return_policies(tables, config), key=lambda r: r["id"]),
        "Return windows/availability disagree with category/channel policy.",
    )
    return len(tables["return_policies"])


def _chronology(tables: dict, _config: ResolvedGenerationConfig) -> int:
    sales, items, orders = (_index(tables[name]) for name in ("sales", "order_items", "orders"))
    refs = tables["sale_price_references"]
    require(
        len(refs) == len(sales) == len(items)
        and {r["sale_id"] for r in refs} == sales.keys()
        and {r["order_item_id"] for r in refs} == items.keys(),
        "Sales and purchased lines must have one-to-one references.",
    )
    for ref in refs:
        sale, item = sales[ref["sale_id"]], items[ref["order_item_id"]]
        order = orders[item["order_id"]]
        require(
            sale["order_reference"] == order["order_reference"]
            and sale["product_id"] == item["product_id"]
            and sale["channel"] == order["channel"] == ref["channel"],
            "Sale does not belong to referenced order/line/channel.",
        )
        require(
            timestamp(order["ordered_at"])
            <= timestamp(sale["sold_at"])
            <= timestamp(sale["ingested_at"]),
            "Transaction chronology requires ordered_at <= sold_at <= ingested_at.",
        )
    return len(sales)


def _references(tables: dict, _config: ResolvedGenerationConfig) -> int:
    sales, items, orders, policies, catalog = (
        _index(tables[name])
        for name in ("sales", "order_items", "orders", "return_policies", "product_catalog")
    )
    refs = {r["sale_id"]: r for r in tables["sale_price_references"]}
    for event in tables["return_events"]:
        sale, item, order, policy = (
            sales[event["sale_id"]],
            items[event["order_item_id"]],
            orders[event["order_id"]],
            policies[event["policy_id"]],
        )
        ref = refs[sale["id"]]
        require(
            item["id"] == ref["order_item_id"]
            and item["order_id"] == order["id"]
            and event["product_id"] == sale["product_id"] == item["product_id"]
            and event["selling_location_id"] == ref["selling_location_id"]
            and event["channel"] == sale["channel"] == order["channel"] == policy["channel"]
            and policy["category_id"] == catalog[item["product_id"]]["category_id"],
            "Return must reference the concrete purchased line and its category/channel policy.",
        )
        sold, returned, ingested, available = (
            timestamp(row[field])
            for row, field in (
                (sale, "sold_at"),
                (event, "returned_at"),
                (event, "ingested_at"),
                (event, "available_at"),
            )
        )
        require(
            timestamp(policy["known_at"])
            <= timestamp(order["ordered_at"])
            <= sold
            <= returned
            <= sold + timedelta(days=int(policy["window_days"]))
            and returned
            <= ingested
            <= available
            <= returned + timedelta(days=int(policy["max_ingestion_delay_days"])),
            "Return chronology/window/known_at/availability is invalid.",
        )
    return len(tables["return_events"])


def _quantities(tables: dict, _config: ResolvedGenerationConfig) -> int:
    items = _index(tables["order_items"])
    quantities = Counter()
    for event in tables["return_events"]:
        item = items[event["order_item_id"]]
        quantity = int(event["quantity"])
        require(quantity > 0, "Return quantity must be positive.")
        quantities[item["id"]] += quantity
        refund = (
            Decimal(item["unit_price"]) * quantity if event["status"] == "refunded" else Decimal(0)
        )
        require(
            quantities[item["id"]] <= int(item["quantity"])
            and Decimal(event["refund_amount"]) == refund
            and event["currency"] == item["currency"],
            "Cumulative returns exceed purchase or refund disagrees with actual paid unit price.",
        )
    return len(tables["return_events"])


def _snapshots(tables: dict, config: ResolvedGenerationConfig) -> int:
    expected = build_return_cohorts(tables, config)
    require(
        sorted(tables["daily_return_cohorts"], key=lambda r: r["id"])
        == sorted(expected, key=lambda r: r["id"]),
        "Gross/net revenue or snapshot includes unavailable return data.",
    )
    require(
        tables["returns"] == legacy_return_projection(tables, return_boundaries(config)["history"]),
        "Legacy return projection includes tail/unavailable events or disagrees with source.",
    )
    return len(expected)


def _tail(tables: dict, config: ResolvedGenerationConfig) -> int:
    boundary = timestamp(return_boundaries(config)["return_tail"])
    require(
        all(timestamp(r["available_at"]) <= boundary for r in tables["return_events"]),
        "Return tail contains events unavailable at its watermark.",
    )
    rows = [r for r in tables["daily_return_cohorts"] if r["snapshot_kind"] == "return_tail"]
    require(
        len(rows) == len(tables["daily_demand_observations"])
        and all(r["return_data_complete"] == "true" for r in rows),
        "Tail must mature every sales cohort including no-return cohorts.",
    )
    require(
        sum((Decimal(r["refund_amount"]) for r in rows), Decimal(0))
        == sum(
            (
                Decimal(r["refund_amount"])
                for r in tables["return_events"]
                if r["status"] == "refunded"
            ),
            Decimal(0),
        ),
        "Tail reconciliation loses refunds.",
    )
    return len(rows)


def _history_count(events: list[dict], boundary: str) -> int:
    try:
        return sum(timestamp(r["available_at"]) <= timestamp(boundary) for r in events)
    except (ValueError, KeyError, TypeError):
        return 0


def build_return_report(tables: dict, config: ResolvedGenerationConfig) -> dict[str, Any]:
    checks = []
    for check_id, function in (
        ("returns_schema", _schema),
        ("return_window_policy", _policies),
        ("transaction_chronology", _chronology),
        ("return_reference_and_window", _references),
        ("return_quantity_and_refunds", _quantities),
        ("return_snapshot_reconciliation", _snapshots),
        ("return_tail_completeness", _tail),
    ):
        try:
            sample = function(tables, config)
            status, description, value = "passed", "All required records satisfy the policy.", 0
        except (ValueError, KeyError, TypeError, ArithmeticError) as error:
            sample, status, description, value = 0, "failed", str(error), 1
        checks.append(
            {
                "check_id": check_id,
                "policy_version": RETURNS_VERSION,
                "use_case": "source_returns",
                "severity": "hard",
                "status": status,
                "sample_size": sample,
                "value": value,
                "threshold": 0,
                "description": description,
                "evidence": "returns_report.json",
            }
        )
    passed = all(c["status"] == "passed" for c in checks)
    events = tables.get("return_events", [])
    history_count = _history_count(events, return_boundaries(config)["history"])
    return {
        "policy_version": RETURNS_VERSION,
        "status": "passed" if passed else "failed",
        "checks": checks,
        "returns_ready": passed,
        "inventory_ready": False,
        "return_tail_days": RETURN_TAIL_DAYS,
        "snapshot_boundaries": return_boundaries(config),
        "event_count": len(events),
        "history_event_count": history_count,
        "tail_event_count": len(events) - history_count,
        "status_counts": dict(
            sorted(Counter(r["status"] for r in tables.get("return_events", [])).items())
        ),
        "revenue_semantics": "gross minus refunded amounts known at the explicit cutoff; final only after return-window and ingestion maturity",
    }


def validate_returns(tables: dict, config: ResolvedGenerationConfig) -> dict:
    report = build_return_report(tables, config)
    if report["status"] != "passed":
        msg = "Returns hard gate failed: " + "; ".join(
            c["check_id"] + ": " + c["description"]
            for c in report["checks"]
            if c["status"] == "failed"
        )
        raise ValueError(msg)
    return report


def returns_report_markdown(report: dict) -> str:
    rows = [
        "# Chronology and returns quality",
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
            f"Return tail: {report['return_tail_days']} days. History events: {report['history_event_count']}; tail events: {report['tail_event_count']}.",
            report["revenue_semantics"],
            "Inventory remains not ready.",
            "",
        ]
    )
    return "\n".join(rows)


def write_returns_report(output: Path, report: dict) -> None:
    (output / "returns_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output / "returns_report.md").write_text(returns_report_markdown(report), encoding="utf-8")
