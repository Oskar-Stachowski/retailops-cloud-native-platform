"""Qualify private physical labels using historical eligibility and stream coverage."""

from __future__ import annotations

from collections import Counter, OrderedDict, defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import TYPE_CHECKING

from data.generator.dimensions import DimensionIndex, resolve_version
from data.inventory.contract import require, utc_timestamp
from data.inventory.qualification_contract import (
    GRAIN,
    QUALIFICATION_POLICY,
    QUALIFICATION_VERSION,
    QualifiedWindow,
)

if TYPE_CHECKING:
    from data.inventory.source_tables import TableContext


@dataclass(frozen=True, slots=True)
class PhysicalDay:
    reason: str | None
    routes: tuple[str, ...] = ()
    sales_keys: tuple[tuple[str, str, str, str], ...] = ()


class Eligibility:
    def __init__(self, tables: dict) -> None:
        self.index = DimensionIndex(tables)
        self.products = {r["id"]: r for r in tables["product_catalog"]}
        self.pairs = sorted(
            self.index.routes.keys()
            | {(r["selling_location_id"], r["channel"]) for r in tables["channel_assignments"]}
        )
        self.assignments = defaultdict(list)
        for row in tables["channel_assignments"]:
            self.assignments[row["selling_location_id"], row["channel"]].append(row)
        self.cache: OrderedDict[tuple[str, str, str, str], PhysicalDay] = OrderedDict()

    def day(self, product: str, stock: str, day: str, cutoff: str) -> PhysicalDay:
        key = product, stock, day, cutoff
        if key not in self.cache:
            self.cache[key] = self._day(product, stock, day, cutoff)
            if len(self.cache) > 4096:
                self.cache.popitem(last=False)
        self.cache.move_to_end(key)
        return self.cache[key]

    def _day(self, product: str, stock: str, day: str, cutoff: str) -> PhysicalDay:
        catalog = self.products[product]
        if utc_timestamp(catalog["available_at"]) > utc_timestamp(cutoff):
            return PhysicalDay("dimension_not_available")
        if day < catalog["launch_date"] or (
            catalog["discontinue_date"] and day >= catalog["discontinue_date"]
        ):
            return PhysicalDay("inactive_lifecycle")
        routes, keys, blockers = [], [], []
        for selling, channel in self.pairs:
            assignment = resolve_version(self.assignments[selling, channel], day)
            assortment = resolve_version(self.index.assortments[product, selling, channel], day)
            if assignment is None or assortment is None:
                continue
            route = self.index.route(selling, channel, day)
            # Unknown destination can affect every physical position; never use today's warehouse.
            if route is None:
                blockers.append("route_missing")
                continue
            if route["stock_location_id"] != stock:
                continue
            if any(
                utc_timestamp(r["available_at"]) > utc_timestamp(cutoff)
                for r in (assignment, assortment, route)
            ):
                blockers.append("dimension_not_available")
                continue
            calendar = self.index.calendar.get((day, selling, channel))
            if calendar is None:
                blockers.append("calendar_missing")
                continue
            routes.append(route["id"])
            keys.append((day, product, selling, channel))
        if blockers:
            return PhysicalDay(min(blockers))
        if not routes:
            return PhysicalDay("inactive_assortment")
        # Closed days remain active and observed. Several channels still share one position.
        return PhysicalDay(None, tuple(sorted(set(routes))), tuple(sorted(set(keys))))


def _future_days(origin: str, finish: str) -> list[str]:
    start, end = utc_timestamp(origin), utc_timestamp(finish)
    require(
        start.time() == time(23, 59, 59, 999999),
        "Qualification requires UTC daily snapshot origins.",
    )
    current = start.date() + timedelta(days=1)
    days = []
    while current <= end.date():
        days.append(current.isoformat())
        current += timedelta(days=1)
    return days


def _qualify(
    row: dict, eligibility: Eligibility, observations: dict, coverage: dict, context: TableContext
) -> dict:
    result = {
        **row,
        "status": "not_evaluable",
        "reason": None,
        "incident_stockout": None,
        "label_available_at": None,
        "origin_route_ids": [],
        "window_route_ids": [],
        "inventory_coverage_id": None,
        "covered_sales_days": 0,
    }
    product, stock, origin = row["product_id"], row["stock_location_id"], row["origin"]
    origin_day = eligibility.day(product, stock, utc_timestamp(origin).date().isoformat(), origin)
    result["origin_route_ids"] = list(origin_day.routes)
    if origin_day.reason:
        result["reason"] = origin_day.reason
        return result
    if row["status"] != "evaluable":
        result.update(status=row["status"], reason=row["reason"])
        return result
    finish, evaluation = utc_timestamp(row["window_end_at"]), utc_timestamp(row["evaluated_at"])
    candidates = [
        r
        for r in coverage[product, stock]
        if utc_timestamp(r["covered_from_at"]) <= utc_timestamp(context.opening_at)
        and utc_timestamp(r["covered_through_at"]) > finish
    ]
    if not candidates:
        result["reason"] = "inventory_coverage_incomplete"
        return result
    certificate = min(candidates, key=lambda r: (r["available_at"], r["coverage_id"]))
    result["inventory_coverage_id"] = certificate["coverage_id"]
    available = max(
        utc_timestamp(row["label_available_at"]), utc_timestamp(certificate["available_at"])
    )
    routes: set[str] = set()
    for day in _future_days(origin, row["window_end_at"]):
        cutoff = datetime.combine(date.fromisoformat(day), time.min, tzinfo=UTC).isoformat()
        physical = eligibility.day(product, stock, day, cutoff)
        if physical.reason:
            result["reason"] = "window_" + physical.reason
            return result
        routes.update(physical.routes)
        for key in physical.sales_keys:
            observed = observations.get(key)
            calendar = eligibility.index.calendar[key[0], key[2], key[3]]
            if (
                observed is None
                or observed["source_data_complete"] != "true"
                or observed["is_active_assortment"] != "true"
                or observed["quality_status"] != "valid"
                or observed["observation_status"]
                not in {"observed_positive", "observed_zero", "closed"}
                or observed["location_open"] != calendar["location_open"]
            ):
                result["reason"] = "sales_coverage_incomplete"
                return result
            available = max(
                available,
                utc_timestamp(observed["available_at"]),
                datetime.combine(date.fromisoformat(day) + timedelta(days=1), time.min, tzinfo=UTC),
            )
        result["covered_sales_days"] += 1
    result["window_route_ids"] = sorted(routes)
    result["label_available_at"] = available.isoformat()
    if evaluation < available:
        result["reason"] = "outcomes_not_available"
        return result
    result.update(status="evaluable", incident_stockout=row["incident_stockout"])
    return result


def qualify_windows(tables: dict, context: TableContext) -> list[dict]:
    """Input must be verified source 2.7; upstream diagnostics prove physical process."""
    eligibility = Eligibility(tables)
    observations = {
        (r["business_date"], r["product_id"], r["selling_location_id"], r["channel"]): r
        for r in tables["daily_demand_observations"]
    }
    require(
        len(observations) == len(tables["daily_demand_observations"]),
        "Duplicate sales coverage grain.",
    )
    coverage = defaultdict(list)
    for row in tables["inventory_history_coverage"]:
        coverage[row["product_id"], row["stock_location_id"]].append(row)
    normalized = [
        QualifiedWindow.model_validate(
            _qualify(r, eligibility, observations, coverage, context)
        ).model_dump()
        for r in tables["inventory_window_diagnostics"]
    ]
    keys = [tuple(r[k] for k in GRAIN) for r in normalized]
    require(len(keys) == len(set(keys)), "Duplicate qualified inventory grain.")
    return sorted(normalized, key=lambda r: tuple(r[k] for k in GRAIN))


def qualification_report(rows: list[dict], parent: dict) -> dict:
    counts = Counter(str(r["incident_stockout"]) for r in rows if r["status"] == "evaluable")
    both_classes = counts["0"] > 0 and counts["1"] > 0
    qualified = both_classes and parent["facts_ready"]
    return {
        "schema_version": QUALIFICATION_VERSION,
        "policy_version": QUALIFICATION_POLICY,
        "parent_source_id": parent["dataset_id"],
        "data_class": "simulation_truth",
        "label_qualification": "qualified" if qualified else "not_evaluable",
        "class_qualification_reason": (
            "source_facts_not_ready"
            if not parent["facts_ready"]
            else None
            if both_classes
            else "insufficient_classes"
        ),
        "scope": "source lifecycle/coverage only; model08 and temporal splits not qualified",
        "source_facts_ready": parent["facts_ready"],
        "rows": len(rows),
        "statuses": dict(sorted(Counter(r["status"] for r in rows).items())),
        "reasons": dict(sorted(Counter(r["reason"] for r in rows if r["reason"]).items())),
        "negative_labels": counts["0"],
        "positive_labels": counts["1"],
        "source_ready": False,
        "inventory_ready": False,
        "model_ready": False,
    }
