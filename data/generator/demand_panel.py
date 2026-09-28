from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from data.generator.business_calendar import utc_midnight
from data.generator.common import deterministic_uuid, money
from data.generator.demand_grid import demand_grid
from data.generator.demand_schema import DEMAND_GRAIN, DEMAND_VERSION
from data.generator.dimension_quality import require, timestamp

if TYPE_CHECKING:
    from data.generator.configuration import ResolvedGenerationConfig


def build_daily_panel(
    tables: dict[str, list[dict[str, Any]]],
    config: ResolvedGenerationConfig,
    *,
    missing_keys: frozenset[tuple[str, ...]] = frozenset(),
) -> list[dict[str, str]]:
    grid, _ = demand_grid(tables, config)
    require(missing_keys <= grid.keys(), "Missing status outside valid panel.")
    references = {r["sale_id"]: r for r in tables["sale_price_references"]}
    by_key = defaultdict(list)
    for sale in tables["sales"]:
        ref = references[sale["id"]]
        key = tuple(ref[field] for field in DEMAND_GRAIN)
        require(key in grid, "Sale outside active demand panel.")
        require(grid[key]["location_open"] == "true", "Sale in closed location.")
        by_key[key].append(sale)
    panel = []
    for key, flags in sorted(grid.items()):
        facts = by_key[key]
        missing, opened = key in missing_keys, flags["location_open"] == "true"
        require(not missing or not facts, "Incomplete source cannot claim complete observed sales.")
        units = sum(int(r["quantity"]) for r in facts)
        revenue = sum((Decimal(r["total_amount"]) for r in facts), Decimal(0))
        cutoff = timestamp(utc_midnight(date.fromisoformat(key[0]) + timedelta(days=1)))
        available = max(
            [
                cutoff,
                *(timestamp(r.get("ingested_at") or r["sold_at"]) for r in facts),
                *(timestamp(references[r["id"]]["as_of_time"]) for r in facts),
            ]
        )
        status = (
            "missing"
            if missing
            else "closed"
            if not opened
            else "observed_positive"
            if units
            else "observed_zero"
        )
        panel.append(
            {
                "id": deterministic_uuid("daily_demand", ":".join(key)),
                **dict(zip(DEMAND_GRAIN, key, strict=True)),
                "observed_units": "" if missing else str(units),
                "observed_orders": ""
                if missing
                else str(len({r["order_reference"] for r in facts})),
                "gross_revenue": "" if missing else money(revenue),
                "net_revenue": "",
                "return_units": "",
                "return_data_complete": "false",
                "currency": "PLN",
                "realized_unit_price": money(revenue / units) if units and not missing else "",
                "promotion_plan_ids": "|".join(
                    sorted({references[r["id"]]["promotion_plan_id"] for r in facts} - {""})
                ),
                "available_at": available.isoformat(),
                "is_active_assortment": "true",
                "location_open": flags["location_open"],
                "source_data_complete": str(not missing).lower(),
                "observation_status": status,
                "quality_status": "incomplete" if missing else "valid",
                "demand_policy_version": DEMAND_VERSION,
            }
        )
    return panel
