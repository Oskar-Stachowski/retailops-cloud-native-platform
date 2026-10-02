from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from itertools import pairwise
from typing import TYPE_CHECKING, Any

from data.generator.business_calendar import calendar_attributes, utc_midnight
from data.generator.dimension_contract import (
    DATE_FIELDS,
    TIMESTAMP_FIELDS,
    validate_dimension_row,
)
from data.generator.dimension_schema import (
    AI_CALENDAR_VERSION,
    CATEGORY_POLICIES,
    CHANNELS,
    DIMENSION_COLUMNS,
    DIMENSIONS_VERSION,
    SKU_PATTERN,
    SKU_POLICY_VERSION,
)
from data.generator.dimensions import DimensionIndex, legacy_projection

if TYPE_CHECKING:
    from pathlib import Path

    from data.generator.configuration import ResolvedGenerationConfig


def require(condition: bool, message: str) -> None:  # noqa: FBT001 - check condition, not mode
    if not condition:
        raise ValueError(message)


def timestamp(value: str) -> datetime:
    result = datetime.fromisoformat(value)
    require(
        result.tzinfo is not None and result.utcoffset().total_seconds() == 0,
        "Dimension timestamps require UTC.",
    )
    return result


def _schema(tables: dict[str, list[dict[str, Any]]], config: ResolvedGenerationConfig) -> int:
    count = 0
    for name in DIMENSION_COLUMNS:
        rows = tables[name]
        require(bool(rows), "Required dimension table is empty.")
        require(len({row["id"] for row in rows}) == len(rows), "Duplicate dimension primary key.")
        for row in rows:
            validate_dimension_row(name, row)
            for key, value in row.items():
                if key in DATE_FIELDS and value:
                    date.fromisoformat(value)
                if key in TIMESTAMP_FIELDS:
                    timestamp(value)
            count += 1
    require(
        len(tables["product_catalog"]) == config.products, "Product count disagrees with config."
    )
    require(len(tables["stock_locations"]) == config.warehouses, "Stock location count disagrees.")
    catalog = tables["product_catalog"]
    require(len({r["sku"] for r in catalog}) == len(catalog), "Duplicate SKU.")
    require(
        all(
            re.fullmatch(SKU_PATTERN, r["sku"]) and r["sku_policy_version"] == SKU_POLICY_VERSION
            for r in catalog
        ),
        "SKU policy failed.",
    )
    return count


def _locations(tables: dict[str, list[dict[str, Any]]], config: ResolvedGenerationConfig) -> int:
    selling = {row["id"]: row for row in tables["selling_locations"]}
    stock = {row["id"]: row for row in tables["stock_locations"]}
    require(
        not selling.keys() & stock.keys(), "Selling and stock locations must have distinct IDs."
    )
    for row in [*selling.values(), *stock.values()]:
        require(
            row["country_code"] in {"PL", "DE"}
            and row["region_code"].startswith(row["country_code"] + "-"),
            "Region/country mismatch.",
        )
    for row in selling.values():
        country = row["country_code"]
        require(
            row["calendar_jurisdiction"] == ("PL" if country == "PL" else "DE-BE"),
            "Unsupported calendar jurisdiction.",
        )
        require(
            row["local_timezone"] == ("Europe/Warsaw" if country == "PL" else "Europe/Berlin")
            and row["business_timezone"] == "UTC",
            "Location timezone mismatch.",
        )
    pairs = set()
    for row in tables["channel_assignments"]:
        require(
            row["selling_location_id"] in selling and row["channel"] in CHANNELS,
            "Invalid assignment location/channel.",
        )
        pairs.add((row["selling_location_id"], row["channel"]))
    require(
        len(pairs) == config.stores,
        "Active pairs count disagrees; channels are not a Cartesian multiplier.",
    )
    return len(pairs)


def _periods(tables: dict[str, list[dict[str, Any]]], config: ResolvedGenerationConfig) -> int:
    selling = {row["id"] for row in tables["selling_locations"]}
    stock = {row["id"] for row in tables["stock_locations"]}
    products = {row["id"] for row in tables["product_catalog"]}
    for name, key in [
        ("channel_assignments", "assignment_key"),
        ("fulfillment_routes", "route_key"),
        ("assortment", "assortment_key"),
    ]:
        groups = defaultdict(list)
        for row in tables[name]:
            require(
                row["selling_location_id"] in selling and row["channel"] in CHANNELS,
                "Invalid period reference.",
            )
            require(
                row["effective_from"] < row["effective_to"], "Empty or reversed effective period."
            )
            require(
                timestamp(row["available_at"])
                <= timestamp(utc_midnight(date.fromisoformat(row["effective_from"]))),
                "Plan version was not available before its effective period.",
            )
            if name == "fulfillment_routes":
                require(row["stock_location_id"] in stock, "Unknown physical stock location.")
            if name == "assortment":
                require(row["product_id"] in products, "Unknown assortment product.")
            require(
                config.start_date.isoformat() <= row["effective_from"]
                and row["effective_to"]
                <= (config.planning_end_date + timedelta(days=1)).isoformat(),
                "Effective period exceeds declared history and known forecast plans.",
            )
            expected_key = f"{row['selling_location_id']}:{row['channel']}"
            require(
                row[key]
                == (f"{row['product_id']}:" if name == "assortment" else "") + expected_key,
                "Effective key disagrees with grain.",
            )
            groups[row[key]].append(row)
        for rows in groups.values():
            ordered = sorted(rows, key=lambda row: row["effective_from"])
            require(
                len({row["version"] for row in rows}) == len(rows), "Duplicate effective version."
            )
            require(
                all(a["effective_to"] <= b["effective_from"] for a, b in pairwise(ordered)),
                "Overlapping effective periods.",
            )
    index = DimensionIndex(tables)
    require(
        {r["assignment_key"] for r in tables["channel_assignments"]}
        == {r["route_key"] for r in tables["fulfillment_routes"]},
        "Routing has missing or unrelated active pairs.",
    )
    for assignment in tables["channel_assignments"]:
        for offset in range(
            (
                date.fromisoformat(assignment["effective_to"])
                - date.fromisoformat(assignment["effective_from"])
            ).days
        ):
            day = (
                date.fromisoformat(assignment["effective_from"]) + timedelta(days=offset)
            ).isoformat()
            route = index.route(
                assignment["selling_location_id"],
                assignment["channel"],
                day,
                utc_midnight(date.fromisoformat(day)),
            )
            require(route is not None, "Missing or unavailable fulfillment route.")
    return len(tables["channel_assignments"])


def _catalog_and_assortment(
    tables: dict[str, list[dict[str, Any]]], config: ResolvedGenerationConfig
) -> int:
    categories = {row["id"]: row for row in tables["catalog_categories"]}
    require(
        {row["name"] for row in categories.values()} == set(CATEGORY_POLICIES),
        "Category hierarchy is incomplete.",
    )
    products = {row["id"]: row for row in tables["product_catalog"]}
    for category in categories.values():
        code, department, segment, _, _, months = CATEGORY_POLICIES[category["name"]]
        require(
            (
                category["category_code"],
                category["department"],
                category["segment"],
                category["seasonal_months"],
            )
            == (code, department, segment, ",".join(map(str, months))),
            "Category hierarchy metadata disagrees with policy.",
        )
    brands = defaultdict(set)
    for row in products.values():
        require(row["category_id"] in categories, "Unknown product category.")
        require(
            row["sku"].startswith(categories[row["category_id"]]["category_code"] + "-"),
            "SKU category prefix disagrees.",
        )
        require(
            timestamp(row["available_at"]) <= timestamp(utc_midnight(config.start_date)),
            "Catalog unavailable at history start.",
        )
        require(
            row["brand"] and row["brand"] != categories[row["category_id"]]["name"],
            "Brand cannot copy category.",
        )
        require(
            Decimal(row["unit_cost"]).is_finite() and Decimal(row["unit_cost"]) > 0,
            "Invalid product cost.",
        )
        require(
            row["unit_of_measure"] == "pcs" and row["pack_unit"] in {"pcs", "g", "ml"},
            "Unsupported product units.",
        )
        require(
            row["currency"] == "PLN" and row["margin_band"] in {"low", "standard", "high"},
            "Invalid cost/margin metadata.",
        )
        require(
            config.start_date.isoformat() <= row["launch_date"] <= config.end_date.isoformat(),
            "Launch is outside configured history.",
        )
        if row["discontinue_date"]:
            require(row["launch_date"] < row["discontinue_date"], "Lifecycle interval is empty.")
        expected_status = (
            "inactive"
            if row["discontinue_date"] and row["discontinue_date"] <= config.end_date.isoformat()
            else "active"
        )
        require(
            row["status"] == expected_status,
            "Catalog status disagrees with lifecycle at export end.",
        )
        brands[row["category_id"]].add(row["brand"])
    if config.products >= 16:
        require(
            any(len(values) > 1 for values in brands.values()),
            "Brand/category mapping is artificially one-to-one.",
        )
    assignments = tables["channel_assignments"]
    valid_days = 0
    for row in tables["assortment"]:
        product = products[row["product_id"]]
        require(
            row["effective_from"] >= product["launch_date"]
            and (
                not product["discontinue_date"]
                or row["effective_to"] <= product["discontinue_date"]
            ),
            "Assortment exceeds lifecycle.",
        )
        matching = [
            assignment
            for assignment in assignments
            if assignment["selling_location_id"] == row["selling_location_id"]
            and assignment["channel"] == row["channel"]
            and assignment["effective_from"] <= row["effective_from"]
            and row["effective_to"] <= assignment["effective_to"]
        ]
        require(len(matching) == 1, "Assortment has no unique channel assignment.")
        # Future plans must not enlarge the denominator of observed demand.
        valid_days += max(
            0,
            (
                min(date.fromisoformat(row["effective_to"]), config.end_date + timedelta(days=1))
                - date.fromisoformat(row["effective_from"])
            ).days,
        )
    require(
        valid_days <= config.days * config.products * config.stores,
        "Assortment denominator exceeds declared grid.",
    )
    return valid_days


def _calendar(tables: dict[str, list[dict[str, Any]]], config: ResolvedGenerationConfig) -> int:
    selling = {row["id"]: row for row in tables["selling_locations"]}
    index = DimensionIndex(tables)
    pairs = {
        (r["selling_location_id"], r["channel"], r["legacy_store_id"])
        for r in tables["channel_assignments"]
    }
    require(len(pairs) == config.stores, "Assignment compatibility IDs are not stable.")
    expected = {}
    for offset in range(config.planning_days):
        current = (config.start_date + timedelta(days=offset)).isoformat()
        for location, channel, adapter_id in pairs:
            assignment = index.assignment(
                adapter_id, current, utc_midnight(date.fromisoformat(current))
            )
            require(assignment is not None, "Missing or unavailable assignment day.")
            expected[current, location, channel] = assignment
    rows = tables["business_calendar"]
    actual = {
        (row["business_date"], row["selling_location_id"], row["channel"]): row for row in rows
    }
    require(
        len(actual) == len(rows) and actual.keys() == expected.keys(),
        "Calendar missing/extra day or duplicate combination.",
    )
    require(
        len(actual) == config.planning_days * config.stores,
        "Calendar denominator must use valid active pairs.",
    )
    known = utc_midnight(config.start_date - timedelta(days=1))
    for key, row in actual.items():
        assignment = expected[key]
        location = selling[row["selling_location_id"]]
        require(
            row["assignment_id"] == assignment["id"],
            "Calendar references wrong effective assignment.",
        )
        attributes = calendar_attributes(
            date.fromisoformat(row["business_date"]),
            location["calendar_jurisdiction"],
            row["channel"],
            known,
        )
        require(
            all(row[name] == value for name, value in attributes.items()),
            "Calendar flags, availability or DST boundaries disagree.",
        )
    return len(actual)


def _category_calendar(
    tables: dict[str, list[dict[str, Any]]], config: ResolvedGenerationConfig
) -> int:
    categories = {row["id"]: row for row in tables["catalog_categories"]}
    expected = {
        (config.start_date + timedelta(days=offset)).isoformat()
        for offset in range(config.planning_days)
    }
    rows = tables["category_calendar"]
    keys = {(row["business_date"], row["category_id"]) for row in rows}
    require(
        len(keys) == len(rows)
        and keys == {(day, category) for day in expected for category in categories},
        "Category calendar coverage is incomplete.",
    )
    for row in rows:
        require(
            row["calendar_version"] == AI_CALENDAR_VERSION
            and row["available_at"] == utc_midnight(config.start_date - timedelta(days=1)),
            "Category calendar policy or availability disagrees.",
        )
        months = {
            int(value)
            for value in categories[row["category_id"]]["seasonal_months"].split(",")
            if value
        }
        require(
            row["is_category_season"]
            == str(date.fromisoformat(row["business_date"]).month in months).lower(),
            "Category season disagrees.",
        )
    return len(rows)


def _adapter(tables: dict[str, list[dict[str, Any]]], config: ResolvedGenerationConfig) -> int:
    expected = legacy_projection(tables, config.end_date.isoformat())
    count = 0
    for name, rows in zip(("products", "stores", "warehouses"), expected, strict=True):
        actual = {row["id"]: row for row in tables[name]}
        require(len(actual) == len(rows), "Compatibility view has missing/extra entity.")
        for row in rows:
            require(
                row["id"] in actual
                and all(actual[row["id"]].get(key) == value for key, value in row.items()),
                "Compatibility view differs from canonical dimensions.",
            )
            count += 1
    return count


def _sales(tables: dict[str, list[dict[str, Any]]], config: ResolvedGenerationConfig) -> int:
    index = DimensionIndex(tables)
    orders = {row["order_reference"]: row for row in tables["orders"]}
    selling = {row["id"]: row for row in tables["selling_locations"]}
    for sale in tables["sales"]:
        ordered = orders[sale["order_reference"]]
        day = timestamp(sale["sold_at"]).date().isoformat()
        require(
            config.start_date.isoformat() <= day <= config.end_date.isoformat(),
            "Sale date outside history.",
        )
        require(
            index.eligible(sale["product_id"], ordered["store_id"], day),
            "Sale violates lifecycle, assortment or opening calendar.",
        )
        assignment = index.assignment(ordered["store_id"], day, ordered["ordered_at"])
        require(assignment is not None, "Order assignment unavailable at business time.")
        require(
            assignment["channel"] == sale["channel"] == ordered["channel"]
            and sale["region"]
            == selling[assignment["selling_location_id"]]["region_code"]
            == ordered["region"],
            "Sale/order dimensions disagree.",
        )
        require(
            index.route(
                assignment["selling_location_id"], assignment["channel"], day, ordered["ordered_at"]
            )
            is not None,
            "Order has no known fulfillment route.",
        )
    return len(tables["sales"])


def build_dimensions_report(
    tables: dict[str, list[dict[str, Any]]], config: ResolvedGenerationConfig
) -> dict[str, Any]:
    checks = []
    operations = {
        "dimension_schema_pk_sku": _schema,
        "selling_stock_channel_region": _locations,
        "assignment_routing_versions": _periods,
        "catalog_lifecycle_assortment": _catalog_and_assortment,
        "calendar_exact_coverage": _calendar,
        "category_season_coverage": _category_calendar,
        "legacy_adapter_consistency": _adapter,
        "sales_active_open_known_routing": _sales,
    }
    for name, operation in operations.items():
        try:
            count = operation(tables, config)
            status, detail = "passed", "All required records satisfy the policy."
        except (ValueError, KeyError, TypeError, ArithmeticError) as error:
            count, status, detail = 0, "failed", str(error)
        checks.append(
            {
                "check_id": name,
                "policy_version": DIMENSIONS_VERSION,
                "use_case": "source_dimensions",
                "severity": "hard",
                "status": status,
                "sample_size": count,
                "value": 0 if status == "passed" else 1,
                "threshold": 0,
                "description": detail,
                "evidence": "dimensions_report.json",
            }
        )
    return {
        "policy_version": DIMENSIONS_VERSION,
        "status": "passed" if all(c["status"] == "passed" for c in checks) else "failed",
        "checks": checks,
        "nominal_daily_grid": config.days * config.products * config.stores,
        "active_daily_combinations": next(
            c["sample_size"] for c in checks if c["check_id"] == "catalog_lifecycle_assortment"
        ),
        "observation_panel_status": "not_ready",
        "inventory_ready": False,
    }


def validate_dimensions(
    tables: dict[str, list[dict[str, Any]]], config: ResolvedGenerationConfig
) -> dict[str, Any]:
    report = build_dimensions_report(tables, config)
    require(report["status"] == "passed", "Canonical dimensions hard gate failed.")
    return report


def write_dimensions_report(output_dir: Path, report: dict[str, Any]) -> None:
    (output_dir / "dimensions_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
