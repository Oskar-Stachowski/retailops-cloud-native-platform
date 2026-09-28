from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

from data.generator.business_calendar import utc_midnight
from data.generator.common import deterministic_uuid
from data.generator.demand_schema import DEMAND_VERSION
from data.generator.dimension_quality import require
from data.generator.dimensions import DimensionIndex, resolve_version

if TYPE_CHECKING:
    from data.generator.configuration import ResolvedGenerationConfig


def demand_grid(
    tables: dict[str, list[dict[str, Any]]], config: ResolvedGenerationConfig
) -> tuple[dict, list]:
    index = DimensionIndex(tables)
    products = {r["id"]: r for r in tables["product_catalog"]}
    pairs = sorted(
        {
            (r["selling_location_id"], r["channel"], r["legacy_store_id"])
            for r in tables["channel_assignments"]
        }
    )
    valid, exclusions = {}, []
    for offset in range(config.days):
        current = config.start_date + timedelta(days=offset)
        day, cutoff = current.isoformat(), utc_midnight(current)
        for location, channel, adapter in pairs:
            assignment = index.assignment(adapter, day, cutoff)
            calendar = index.calendar.get((day, location, channel))
            require(calendar is not None, "Missing calendar cannot become zero demand.")
            for product_id, product in sorted(products.items()):
                key = (day, product_id, location, channel)
                active = product["launch_date"] <= day and (
                    not product["discontinue_date"] or day < product["discontinue_date"]
                )
                assortment = resolve_version(
                    index.assortments[product_id, location, channel], day, cutoff
                )
                reason = (
                    "inactive_lifecycle"
                    if not active
                    else "inactive_assignment"
                    if assignment is None
                    else "inactive_assortment"
                    if assortment is None
                    else ""
                )
                if reason:
                    exclusions.append(
                        {
                            "id": deterministic_uuid("demand_exclusion", ":".join(key)),
                            **dict(
                                zip(
                                    (
                                        "business_date",
                                        "product_id",
                                        "selling_location_id",
                                        "channel",
                                    ),
                                    key,
                                    strict=True,
                                )
                            ),
                            "observation_status": "inactive",
                            "exclusion_reason": reason,
                            "demand_policy_version": DEMAND_VERSION,
                        }
                    )
                else:
                    valid[key] = {
                        "legacy_store_id": adapter,
                        "location_open": calendar["location_open"],
                    }
    return valid, exclusions
