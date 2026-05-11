from __future__ import annotations

import json
from collections import Counter, defaultdict
from decimal import Decimal
from statistics import mean
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def _decimal(value: str | float | Decimal) -> Decimal:
    return Decimal(str(value or "0"))


def _share_top_products(
    sales: list[dict[str, str]],
    top_percent: Decimal = Decimal("0.20"),
) -> str:
    revenue_by_product: dict[str, Decimal] = defaultdict(Decimal)
    for sale in sales:
        revenue_by_product[sale["product_id"]] += _decimal(sale["total_amount"])

    if not revenue_by_product:
        return "0.0000"

    product_count = len(revenue_by_product)
    top_count = max(1, int(product_count * top_percent))
    top_revenue = sum(
        sorted(revenue_by_product.values(), reverse=True)[:top_count],
        Decimal("0"),
    )
    total_revenue = sum(revenue_by_product.values(), Decimal("0"))
    return str((top_revenue / total_revenue).quantize(Decimal("0.0001")))


def _average_order_items(order_items: list[dict[str, str]]) -> str:
    item_count_by_order = Counter(order_item["order_id"] for order_item in order_items)
    if not item_count_by_order:
        return "0.0000"

    return str(Decimal(str(mean(item_count_by_order.values()))).quantize(Decimal("0.0001")))


def _return_rate_by_category(
    products: list[dict[str, str]],
    order_items: list[dict[str, str]],
    returns: list[dict[str, str]],
) -> dict[str, str]:
    product_category = {product["id"]: product["category"] for product in products}
    ordered_by_category: dict[str, int] = defaultdict(int)
    returned_by_category: dict[str, int] = defaultdict(int)

    for order_item in order_items:
        ordered_by_category[product_category[order_item["product_id"]]] += int(
            order_item["quantity"],
        )

    for returned_item in returns:
        returned_by_category[product_category[returned_item["product_id"]]] += int(
            returned_item["quantity"],
        )

    return {
        category: str(
            (Decimal(returned_by_category[category]) / Decimal(ordered_quantity)).quantize(
                Decimal("0.0001"),
            ),
        )
        for category, ordered_quantity in sorted(ordered_by_category.items())
        if ordered_quantity
    }


def _promotion_uplift(sales: list[dict[str, str]]) -> str:
    promoted = [
        int(sale["observed_sales"]) for sale in sales if sale.get("promotion_applied") == "true"
    ]
    baseline = [
        int(sale["observed_sales"]) for sale in sales if sale.get("promotion_applied") != "true"
    ]
    if not promoted or not baseline:
        return "0.0000"

    return str(
        (Decimal(str(mean(promoted))) / Decimal(str(mean(baseline)))).quantize(Decimal("0.0001")),
    )


def _stockout_rate(sales: list[dict[str, str]]) -> str:
    if not sales:
        return "0.0000"

    stockout_count = sum(1 for sale in sales if sale.get("stockout_flag") == "true")
    return str((Decimal(stockout_count) / Decimal(len(sales))).quantize(Decimal("0.0001")))


def _data_quality_status_counts(
    sales: list[dict[str, str]],
) -> dict[str, int]:
    return dict(
        sorted(
            Counter(sale.get("data_quality_status") or "not_applicable" for sale in sales).items(),
        ),
    )


def build_realism_report(
    profile: str,
    seed: int,
    tables: dict[str, list[dict[str, str]]],
) -> dict[str, object]:
    sales = tables["sales"]
    order_items = tables["order_items"]
    products = tables["products"]
    returns = tables["returns"]
    demand_classes = Counter(
        product.get("demand_class") or "not_applicable" for product in products
    )

    return {
        "profile": profile,
        "seed": seed,
        "row_counts": {table_name: len(rows) for table_name, rows in sorted(tables.items())},
        "realism_metrics": {
            "top_20_percent_product_revenue_share": _share_top_products(sales),
            "average_order_items": _average_order_items(order_items),
            "promotion_uplift_ratio": _promotion_uplift(sales),
            "stockout_rate": _stockout_rate(sales),
            "return_rate_by_category": _return_rate_by_category(
                products,
                order_items,
                returns,
            ),
            "data_quality_status_counts": _data_quality_status_counts(sales),
            "demand_class_counts": dict(sorted(demand_classes.items())),
        },
        "validation_notes": [
            "Top product revenue share should show a long-tail distribution.",
            "Average order items should be above 1 for synthetic profiles.",
            "Promotion uplift should be positive but not perfect.",
            "Stockout rate should be non-zero for operational realism.",
            "Data quality issues are intentionally low and controlled.",
        ],
    }


def write_realism_report(
    output_dir: Path,
    profile: str,
    seed: int,
    tables: dict[str, list[dict[str, str]]],
) -> Path:
    report_path = output_dir / "realism_report.json"
    report = build_realism_report(profile, seed, tables)
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report_path
