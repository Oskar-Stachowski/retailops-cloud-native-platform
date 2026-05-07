from __future__ import annotations

import json
from collections import defaultdict
from decimal import Decimal
from pathlib import Path


ALLOWED_DATA_QUALITY_STATUSES = {
    "",
    "ok",
    "late_event",
    "duplicate_candidate",
    "missing_optional_context",
}


def _decimal(value: str | int | float | Decimal | None) -> Decimal:
    if value is None or value == "":
        return Decimal("0")
    return Decimal(str(value))


def _date(value: object) -> str:
    if isinstance(value, tuple):
        value = value[0]
    return str(value)[:10]


def _ids(rows: list[dict[str, str]]) -> set[str]:
    return {row["id"] for row in rows}


def _check(
    checks: list[dict[str, object]],
    name: str,
    passed: bool,
    details: dict[str, object] | None = None,
) -> None:
    checks.append(
        {
            "name": name,
            "status": "passed" if passed else "failed",
            "details": details or {},
        }
    )


def build_quality_report(
    profile: str,
    tables: dict[str, list[dict[str, str]]],
) -> dict[str, object]:
    checks: list[dict[str, object]] = []
    products = tables["products"]
    users = tables["users"]
    stores = tables["stores"]
    warehouses = tables["warehouses"]
    orders = tables["orders"]
    order_items = tables["order_items"]
    price_history = tables["price_history"]
    promotions = tables["promotions"]
    stock_movements = tables["stock_movements"]
    returns = tables["returns"]
    sales = tables["sales"]
    inventory_snapshots = tables["inventory_snapshots"]
    forecasts = tables["forecasts"]
    anomalies = tables["anomalies"]
    alerts = tables["alerts"]
    recommendations = tables["recommendations"]
    workflow_actions = tables["workflow_actions"]

    product_ids = _ids(products)
    user_ids = _ids(users)
    store_ids = _ids(stores)
    warehouse_ids = _ids(warehouses)
    warehouse_codes = {warehouse["warehouse_code"] for warehouse in warehouses}
    order_ids = _ids(orders)
    order_item_ids = _ids(order_items)
    anomaly_ids = _ids(anomalies)
    alert_ids = _ids(alerts)

    all_ids = [
        row["id"]
        for rows in tables.values()
        for row in rows
        if row.get("id")
    ]
    _check(
        checks,
        "primary_keys_are_unique",
        len(all_ids) == len(set(all_ids)),
        {"ids": len(all_ids), "unique_ids": len(set(all_ids))},
    )

    _check(
        checks,
        "sales_reference_products",
        all(sale["product_id"] in product_ids for sale in sales),
        {"sales": len(sales)},
    )
    _check(
        checks,
        "orders_reference_stores",
        all(order["store_id"] in store_ids for order in orders),
        {"orders": len(orders)},
    )
    _check(
        checks,
        "order_items_reference_orders_and_products",
        all(
            order_item["order_id"] in order_ids
            and order_item["product_id"] in product_ids
            for order_item in order_items
        ),
        {"order_items": len(order_items)},
    )
    _check(
        checks,
        "pricing_references_products",
        all(row["product_id"] in product_ids for row in price_history)
        and all(row["product_id"] in product_ids for row in promotions),
        {
            "price_history": len(price_history),
            "promotions": len(promotions),
        },
    )
    _check(
        checks,
        "inventory_references_products_and_warehouses",
        all(
            row["product_id"] in product_ids
            and row["warehouse_code"] in warehouse_codes
            for row in inventory_snapshots
        ),
        {"inventory_snapshots": len(inventory_snapshots)},
    )
    _check(
        checks,
        "stock_movements_reference_products_and_warehouses",
        all(
            row["product_id"] in product_ids
            and row["warehouse_id"] in warehouse_ids
            and row["warehouse_code"] in warehouse_codes
            for row in stock_movements
        ),
        {"stock_movements": len(stock_movements)},
    )
    _check(
        checks,
        "returns_reference_orders_order_items_and_products",
        all(
            row["order_id"] in order_ids
            and row["order_item_id"] in order_item_ids
            and row["product_id"] in product_ids
            for row in returns
        ),
        {"returns": len(returns)},
    )
    _check(
        checks,
        "operational_records_reference_valid_entities",
        all(row["product_id"] in product_ids for row in forecasts)
        and all(row["product_id"] in product_ids for row in anomalies)
        and all(
            row["product_id"] in product_ids
            and (not row.get("anomaly_id") or row["anomaly_id"] in anomaly_ids)
            and (
                not row.get("assigned_to_user_id")
                or row["assigned_to_user_id"] in user_ids
            )
            for row in alerts
        )
        and all(
            row["product_id"] in product_ids
            and (not row.get("alert_id") or row["alert_id"] in alert_ids)
            and (not row.get("anomaly_id") or row["anomaly_id"] in anomaly_ids)
            for row in recommendations
        )
        and all(
            row["alert_id"] in alert_ids
            and row["performed_by_user_id"] in user_ids
            for row in workflow_actions
        ),
        {
            "forecasts": len(forecasts),
            "anomalies": len(anomalies),
            "alerts": len(alerts),
            "recommendations": len(recommendations),
            "workflow_actions": len(workflow_actions),
        },
    )

    _check(
        checks,
        "sales_values_are_positive",
        all(
            int(sale["quantity"]) > 0
            and _decimal(sale["unit_price"]) >= 0
            and _decimal(sale["total_amount"]) >= 0
            for sale in sales
        ),
    )
    _check(
        checks,
        "inventory_and_returns_are_non_negative",
        all(int(row["stock_quantity"]) >= 0 for row in inventory_snapshots)
        and all(int(row["quantity"]) > 0 for row in returns)
        and all(_decimal(row["refund_amount"]) >= 0 for row in returns),
    )

    order_item_total_by_order: dict[str, Decimal] = defaultdict(Decimal)
    for order_item in order_items:
        order_item_total_by_order[order_item["order_id"]] += _decimal(
            order_item["total_amount"]
        )
    order_total_mismatches = [
        order["order_reference"]
        for order in orders
        if order_item_total_by_order[order["id"]]
        != _decimal(order["order_total"])
    ]
    _check(
        checks,
        "order_totals_match_order_items",
        not order_total_mismatches,
        {"mismatches": len(order_total_mismatches)},
    )

    order_item_quantity = {
        order_item["id"]: int(order_item["quantity"])
        for order_item in order_items
    }
    invalid_returns = [
        returned_item["id"]
        for returned_item in returns
        if int(returned_item["quantity"])
        > order_item_quantity.get(returned_item["order_item_id"], 0)
    ]
    _check(
        checks,
        "returns_do_not_exceed_order_item_quantity",
        not invalid_returns,
        {"invalid_returns": len(invalid_returns)},
    )

    _check(
        checks,
        "date_windows_are_ordered",
        all(
            not row.get("valid_to")
            or _date(row["valid_from"]) <= _date(row["valid_to"])
            for row in price_history
        )
        and all(_date(row["starts_at"]) <= _date(row["ends_at"]) for row in promotions)
        and all(
            _date(row["forecast_period_start"])
            <= _date(row["forecast_period_end"])
            for row in forecasts
        )
        and all(
            _date(row["period_start"]) <= _date(row["period_end"])
            for row in anomalies
        ),
    )

    _check(
        checks,
        "sales_data_quality_statuses_are_known",
        all(
            sale.get("data_quality_status", "") in ALLOWED_DATA_QUALITY_STATUSES
            for sale in sales
        ),
        {"allowed_statuses": sorted(ALLOWED_DATA_QUALITY_STATUSES)},
    )

    failed_checks = [
        check for check in checks if check["status"] == "failed"
    ]
    return {
        "profile": profile,
        "status": "passed" if not failed_checks else "failed",
        "summary": {
            "checks": len(checks),
            "passed": len(checks) - len(failed_checks),
            "failed": len(failed_checks),
        },
        "row_counts": {
            table_name: len(rows)
            for table_name, rows in sorted(tables.items())
        },
        "checks": checks,
    }


def write_quality_report(
    output_dir: Path,
    profile: str,
    tables: dict[str, list[dict[str, str]]],
) -> Path:
    report_path = output_dir / "quality_report.json"
    report = build_quality_report(profile, tables)
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report_path
