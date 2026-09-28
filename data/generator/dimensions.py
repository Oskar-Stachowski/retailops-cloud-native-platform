from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from itertools import pairwise
from typing import TYPE_CHECKING, Any

from data.generator.business_calendar import calendar_attributes, utc_midnight
from data.generator.common import deterministic_uuid, money

if TYPE_CHECKING:
    from data.generator.configuration import ResolvedGenerationConfig
from data.generator.dimension_schema import (
    AI_CALENDAR_VERSION,
    CATEGORY_POLICIES,
    CHANNELS,
    DIMENSION_COLUMNS,
    SKU_POLICY_VERSION,
)

LOCATION_BLUEPRINTS = (
    ("PL-North", "PL", "Gdansk", "PL", "Europe/Warsaw"),
    ("DE-BE", "DE", "Berlin", "DE-BE", "Europe/Berlin"),
    ("PL-Central", "PL", "Warsaw", "PL", "Europe/Warsaw"),
    ("PL-South", "PL", "Krakow", "PL", "Europe/Warsaw"),
)


def in_period(row: dict[str, Any], day: str, as_of_time: str | None = None) -> bool:
    if as_of_time is not None:
        cutoff = datetime.fromisoformat(as_of_time)
        if cutoff.tzinfo is None:
            msg = "as_of_time requires timezone."
            raise ValueError(msg)
        if datetime.fromisoformat(row["available_at"]).astimezone(UTC) > cutoff.astimezone(UTC):
            return False
    return row["effective_from"] <= day < row["effective_to"]


def resolve_version(
    rows: list[dict[str, Any]], day: str, as_of_time: str | None = None
) -> dict[str, Any] | None:
    matches = [row for row in rows if in_period(row, day, as_of_time)]
    if len(matches) > 1:
        msg = "Ambiguous effective version."
        raise ValueError(msg)
    return matches[0] if matches else None


def dated_versions(start: date, end: date) -> list[tuple[int, str, str]]:
    middle = start + timedelta(days=max(1, (end - start).days // 2))
    boundaries = [start, min(middle, end), end]
    return [
        (index + 1, first.isoformat(), last.isoformat())
        for index, (first, last) in enumerate(pairwise(boundaries))
        if first < last
    ]


def _categories() -> list[dict[str, str]]:
    return [
        {
            "id": deterministic_uuid("category", code),
            "category_code": code,
            "name": name,
            "department": department,
            "segment": segment,
            "seasonal_months": ",".join(str(month) for month in months),
        }
        for name, (code, department, segment, _, _, months) in CATEGORY_POLICIES.items()
    ]


def _catalog(
    products: list[dict[str, str]], brands: list[str], config: ResolvedGenerationConfig
) -> list[dict[str, str]]:
    known = utc_midnight(config.start_date - timedelta(days=1))
    result = []
    for index, product in enumerate(products):
        code, _, _, pack, pack_unit, _ = CATEGORY_POLICIES[product["category"]]
        sku = f"{code}-{index + 1:06d}"
        launch = config.start_date
        discontinue = None
        if index % 8 == 3:
            launch += timedelta(days=min(7, config.days // 4))
        if index % 8 == 5:
            discontinue = config.end_date - timedelta(days=min(7, config.days // 4) - 1)
        cost_ratio = Decimal("0.45") + Decimal(index % 5) * Decimal("0.08")
        cost = Decimal(product["base_price"]) * cost_ratio
        margin = Decimal(1) - cost_ratio
        result.append(
            {
                "id": deterministic_uuid("product", sku),
                "sku": sku,
                "sku_policy_version": SKU_POLICY_VERSION,
                "name": product["name"],
                "category_id": deterministic_uuid("category", code),
                "brand": brands[
                    (index * 3 + index // len(CATEGORY_POLICIES) + config.seed) % len(brands)
                ],
                "launch_date": launch.isoformat(),
                "discontinue_date": discontinue.isoformat() if discontinue else "",
                "unit_of_measure": "pcs",
                "pack_quantity": str(pack * (1 + index // 8 % 3)),
                "pack_unit": pack_unit,
                "unit_cost": money(cost),
                "currency": "PLN",
                "margin_band": "high"
                if margin >= Decimal("0.50")
                else "standard"
                if margin >= Decimal("0.30")
                else "low",
                "status": "inactive"
                if discontinue and discontinue <= config.end_date
                else "active",
                "available_at": known,
            }
        )
    return result


def _locations(count: int, role: str) -> list[dict[str, str]]:
    result = []
    for index in range(count):
        region, country, city, jurisdiction, timezone = LOCATION_BLUEPRINTS[
            index % len(LOCATION_BLUEPRINTS)
        ]
        code = f"{'SELL' if role == 'selling' else 'WH'}-{index + 1:04d}"
        row = {
            "id": deterministic_uuid(role + "_location", code),
            "location_code": code,
            "name": f"RetailOps {role} location {index + 1:04d}",
            "region_code": region,
            "country_code": country,
            "city": city,
        }
        if role == "selling":
            row.update(
                calendar_jurisdiction=jurisdiction, local_timezone=timezone, business_timezone="UTC"
            )
        else:
            row["location_type"] = "warehouse"
        result.append(row)
    return result


def _assignments(
    locations: list[dict[str, str]], config: ResolvedGenerationConfig
) -> list[dict[str, str]]:
    known = utc_midnight(config.start_date - timedelta(days=1))
    result = []
    for index in range(config.stores):
        location = locations[index % len(locations)]
        channel = CHANNELS[index // len(locations) % len(CHANNELS)]
        key = f"{location['id']}:{channel}"
        for version, first, last in dated_versions(
            config.start_date, config.end_date + timedelta(days=1)
        ):
            result.append(
                {
                    "id": deterministic_uuid("channel_assignment", f"{key}:v{version}"),
                    "assignment_key": key,
                    "version": str(version),
                    "legacy_store_id": deterministic_uuid("store_adapter", key),
                    "selling_location_id": location["id"],
                    "channel": channel,
                    "effective_from": first,
                    "effective_to": last,
                    "available_at": known,
                }
            )
    return result


def _routes(
    assignments: list[dict[str, str]], selling: list[dict[str, str]], stock: list[dict[str, str]]
) -> list[dict[str, str]]:
    countries = {row["id"]: row["country_code"] for row in selling}
    result = []
    for index, assignment in enumerate(assignments):
        eligible = [
            row
            for row in stock
            if row["country_code"] == countries[assignment["selling_location_id"]]
        ] or stock
        physical = eligible[(index // 2 + int(assignment["version"]) - 1) % len(eligible)]
        key = assignment["assignment_key"]
        result.append(
            {
                "id": deterministic_uuid("fulfillment_route", f"{key}:v{assignment['version']}"),
                "route_key": key,
                "version": assignment["version"],
                "selling_location_id": assignment["selling_location_id"],
                "channel": assignment["channel"],
                "stock_location_id": physical["id"],
                "effective_from": assignment["effective_from"],
                "effective_to": assignment["effective_to"],
                "available_at": assignment["available_at"],
            }
        )
    return result


def _assortment(
    catalog: list[dict[str, str]], assignments: list[dict[str, str]]
) -> list[dict[str, str]]:
    pair_keys = list(dict.fromkeys(row["assignment_key"] for row in assignments))
    pair_indexes = {key: index for index, key in enumerate(pair_keys)}
    result = []
    for product_index, product in enumerate(catalog):
        for assignment in assignments:
            pair_index = pair_indexes[assignment["assignment_key"]]
            if product_index and (product_index + pair_index) % 11 == 0:
                continue
            first = max(assignment["effective_from"], product["launch_date"])
            last = min(
                assignment["effective_to"],
                product["discontinue_date"] or assignment["effective_to"],
            )
            if first >= last:
                continue
            key = f"{product['id']}:{assignment['assignment_key']}"
            result.append(
                {
                    "id": deterministic_uuid("assortment", f"{key}:v{assignment['version']}"),
                    "assortment_key": key,
                    "version": assignment["version"],
                    "product_id": product["id"],
                    "selling_location_id": assignment["selling_location_id"],
                    "channel": assignment["channel"],
                    "effective_from": first,
                    "effective_to": last,
                    "available_at": assignment["available_at"],
                }
            )
    return result


def _calendar(
    assignments: list[dict[str, str]],
    selling: list[dict[str, str]],
    config: ResolvedGenerationConfig,
) -> list[dict[str, str]]:
    by_id = {row["id"]: row for row in selling}
    result = []
    for assignment in assignments:
        location = by_id[assignment["selling_location_id"]]
        current = date.fromisoformat(assignment["effective_from"])
        end = date.fromisoformat(assignment["effective_to"])
        while current < end:
            day = current.isoformat()
            key = f"{day}:{assignment['assignment_key']}"
            result.append(
                {
                    "id": deterministic_uuid("business_calendar", key),
                    "business_date": day,
                    "selling_location_id": location["id"],
                    "channel": assignment["channel"],
                    "assignment_id": assignment["id"],
                    **calendar_attributes(
                        current,
                        location["calendar_jurisdiction"],
                        assignment["channel"],
                        utc_midnight(config.start_date - timedelta(days=1)),
                    ),
                }
            )
            current += timedelta(days=1)
    return result


def build_dimensions(
    products: list[dict[str, str]],
    stores: list[dict[str, str]],
    warehouses: list[dict[str, str]],
    brands: list[str],
    config: ResolvedGenerationConfig,
) -> tuple[
    dict[str, list[dict[str, str]]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
]:
    categories = _categories()
    catalog = _catalog(products, brands, config)
    selling_count = min(config.stores, max(2, (config.stores + len(CHANNELS) - 1) // len(CHANNELS)))
    selling = _locations(selling_count, "selling")
    stock = _locations(config.warehouses, "stock")
    assignments = _assignments(selling, config)
    category_calendar = []
    for offset in range(config.days):
        day = config.start_date + timedelta(days=offset)
        for category in categories:
            months = {int(value) for value in category["seasonal_months"].split(",") if value}
            category_calendar.append(
                {
                    "id": deterministic_uuid("category_calendar", f"{day}:{category['id']}"),
                    "business_date": day.isoformat(),
                    "category_id": category["id"],
                    "calendar_version": AI_CALENDAR_VERSION,
                    "is_category_season": str(day.month in months).lower(),
                    "available_at": utc_midnight(config.start_date - timedelta(days=1)),
                }
            )
    tables = {
        "catalog_categories": categories,
        "product_catalog": catalog,
        "selling_locations": selling,
        "stock_locations": stock,
        "channel_assignments": assignments,
        "fulfillment_routes": _routes(assignments, selling, stock),
        "assortment": _assortment(catalog, assignments),
        "business_calendar": _calendar(assignments, selling, config),
        "category_calendar": category_calendar,
    }
    projected_products, projected_stores, projected_warehouses = legacy_projection(
        tables, config.end_date.isoformat()
    )
    # Simulation fields live in the legacy view until the separate truth-separation slice.
    projected_products = [
        {**raw, **projected} for raw, projected in zip(products, projected_products, strict=True)
    ]
    projected_stores = [
        {**raw, **projected} for raw, projected in zip(stores, projected_stores, strict=True)
    ]
    projected_warehouses = [
        {**raw, **projected}
        for raw, projected in zip(warehouses, projected_warehouses, strict=True)
    ]
    return tables, projected_products, projected_stores, projected_warehouses


def legacy_projection(
    tables: dict[str, list[dict[str, Any]]], day: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    categories = {row["id"]: row for row in tables["catalog_categories"]}
    selling = {row["id"]: row for row in tables["selling_locations"]}
    products = [
        {key: row[key] for key in ("id", "sku", "name", "brand", "status")}
        | {"category": categories[row["category_id"]]["name"]}
        for row in tables["product_catalog"]
    ]
    stores = []
    assignments_by_key = defaultdict(list)
    for row in tables["channel_assignments"]:
        assignments_by_key[row["assignment_key"]].append(row)
    for index, versions in enumerate(assignments_by_key.values()):
        row = resolve_version(versions, day)
        if row is None:
            msg = "No channel assignment for adapter date."
            raise ValueError(msg)
        location = selling[row["selling_location_id"]]
        stores.append(
            {
                "id": row["legacy_store_id"],
                "store_code": f"PAIR-{index + 1:04d}",
                "name": f"{location['name']} / {row['channel']}",
                "region": location["region_code"],
                "country": location["country_code"],
                "city": location["city"],
                "channel": row["channel"],
                "status": "active",
            }
        )
    warehouses = [
        {
            "id": row["id"],
            "warehouse_code": row["location_code"],
            "name": row["name"],
            "region": row["region_code"],
            "country": row["country_code"],
            "city": row["city"],
            "status": "active",
        }
        for row in tables["stock_locations"]
    ]
    return products, stores, warehouses


@dataclass
class DimensionIndex:
    tables: dict[str, list[dict[str, Any]]]

    def __post_init__(self) -> None:
        if any(name not in self.tables for name in DIMENSION_COLUMNS):
            msg = "Canonical AI dimensions are incomplete."
            raise ValueError(msg)
        self.assignments = defaultdict(list)
        self.assortments = defaultdict(list)
        self.routes = defaultdict(list)
        for row in self.tables["channel_assignments"]:
            self.assignments[row["legacy_store_id"]].append(row)
        for row in self.tables["assortment"]:
            self.assortments[row["product_id"], row["selling_location_id"], row["channel"]].append(
                row
            )
        for row in self.tables["fulfillment_routes"]:
            self.routes[row["selling_location_id"], row["channel"]].append(row)
        self.calendar = {
            (row["business_date"], row["selling_location_id"], row["channel"]): row
            for row in self.tables["business_calendar"]
        }

    def assignment(
        self, legacy_store_id: str, day: str, as_of_time: str | None = None
    ) -> dict[str, Any] | None:
        return resolve_version(self.assignments[legacy_store_id], day, as_of_time)

    def eligible(self, product_id: str, legacy_store_id: str, day: str) -> bool:
        assignment = self.assignment(legacy_store_id, day)
        if assignment is None:
            return False
        key = (day, assignment["selling_location_id"], assignment["channel"])
        calendar = self.calendar.get(key)
        if calendar is None:
            msg = "Missing calendar day is unknown, never closed or zero."
            raise ValueError(msg)
        assortment = self.assortments[
            product_id, assignment["selling_location_id"], assignment["channel"]
        ]
        return calendar["location_open"] == "true" and resolve_version(assortment, day) is not None

    def route(
        self, selling_location_id: str, channel: str, day: str, as_of_time: str | None = None
    ) -> dict[str, Any] | None:
        return resolve_version(self.routes[selling_location_id, channel], day, as_of_time)
