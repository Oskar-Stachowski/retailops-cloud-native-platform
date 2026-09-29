from __future__ import annotations

from collections import defaultdict
from datetime import date
from itertools import pairwise
from typing import TYPE_CHECKING

from data.inventory.contract import require, utc_timestamp

if TYPE_CHECKING:
    from data.inventory.simulation_contract import FulfillmentRoute


def validate_routes(routes: tuple[FulfillmentRoute, ...], stock_ids: set[str]) -> None:
    groups = defaultdict(list)
    for route in routes:
        require(
            date.fromisoformat(route.effective_from) < date.fromisoformat(route.effective_to),
            "Invalid route effective period.",
        )
        utc_timestamp(route.available_at)
        require(
            route.stock_location_id in stock_ids,
            "Route references unknown physical stock location.",
        )
        groups[(route.selling_location_id, route.channel)].append(route)
    for group in groups.values():
        for left, right in ((a, b) for i, a in enumerate(group) for b in group[i + 1 :]):
            overlaps = max(left.effective_from, right.effective_from) < min(
                left.effective_to, right.effective_to
            )
            require(
                not overlaps
                or (left.effective_from, left.effective_to)
                == (right.effective_from, right.effective_to),
                "Ambiguous overlapping fulfillment route periods.",
            )
        periods = defaultdict(list)
        for row in group:
            periods[(row.effective_from, row.effective_to)].append(row)
        for versions in periods.values():
            ordered = sorted(versions, key=lambda r: r.version)
            require(
                [r.version for r in ordered] == list(range(1, len(ordered) + 1)),
                "Route versions must be consecutive from one.",
            )
            require(
                all(
                    utc_timestamp(a.available_at) <= utc_timestamp(b.available_at)
                    for a, b in pairwise(ordered)
                ),
                "Route versions have backdated availability.",
            )


def resolve_route(
    routes: tuple[FulfillmentRoute, ...], selling_id: str, channel: str, happened_at: str
) -> FulfillmentRoute:
    cutoff = utc_timestamp(happened_at)
    day = cutoff.date()
    candidates = [
        r
        for r in routes
        if r.selling_location_id == selling_id
        and r.channel == channel
        and date.fromisoformat(r.effective_from) <= day < date.fromisoformat(r.effective_to)
        and utc_timestamp(r.available_at) <= cutoff
    ]
    require(bool(candidates), "Missing known fulfillment mapping at sale time.")
    return max(candidates, key=lambda r: r.version)
