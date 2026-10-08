"""Declare event days from public native facts, never from truth or cohort flags."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime, timedelta

from data.day_coverage.contract import MAX_ROWS, TABLES, Day
from data.inventory.contract import require, utc_timestamp

KEY = ("product_id", "selling_location_id", "channel", "currency")


def days(tables: dict, source: dict) -> list[dict]:
    require(set(tables) == set(TABLES), "Day coverage operational table allowlist differs.")
    require(
        source["schema_version"] == "2.8.0" and source["facts_ready"],
        "Verified source 2.8 required.",
    )
    params = source["descriptor"]["resolved_parameters"]
    start = date.fromisoformat(params["start_date"])
    sales: dict[tuple, list[dict]] = defaultdict(list)
    claims: dict[tuple, list[dict]] = defaultdict(list)
    for sale in tables["inventory_sales"]:
        sales[tuple(sale[k] for k in KEY)].append(sale)
    for claim in tables["return_events"]:
        claims[(claim["returned_at"][:10], *(claim[k] for k in KEY))].append(claim)
    catalog = {p["id"]: p for p in tables["product_catalog"]}
    policies = {(p["category_id"], p["channel"]): p for p in tables["return_policies"]}
    result = []
    for observation in tables["daily_demand_observations"]:
        day = date.fromisoformat(observation["business_date"])
        series = tuple(observation[k] for k in KEY)
        native = [s for s in sales[series] if s["sold_at"][:10] == day.isoformat()]
        end = datetime.combine(day + timedelta(days=1), datetime.min.time(), UTC)
        complete = (
            observation["source_data_complete"] == "true"
            and observation["quality_status"] == "valid"
        )
        closed = observation["observation_status"] == "closed"
        require(not closed or not native, "Closed location has native sales.")
        require(
            not complete
            or sum(int(s["quantity"]) for s in native) == int(observation["observed_units"]),
            "Complete sales observation disagrees with native sales.",
        )
        result.append(
            Day(
                event_type="sale_completed",
                business_date=day.isoformat(),
                **dict(zip(KEY, series, strict=True)),
                window_end=end.isoformat(),
                known_at=max(
                    [
                        end,
                        utc_timestamp(observation["available_at"]),
                        *(utc_timestamp(s["available_at"]) for s in native),
                    ]
                ).isoformat(),
                source_complete=complete,
                activity="closed" if closed else "open" if complete else "missing",
                expected_business_ids=sorted(s["sale_id"] for s in native),
                required_sale_ids=[],
            ).model_dump()
        )
    # This is an explicit publisher assertion for this verified finite synthetic
    # export. It says nothing about purchases outside the source or cohort maturity.
    for series, purchases in sorted(sales.items()):
        product, _, channel, _ = series
        rule = policies[catalog[product]["category_id"], channel]
        last = max(date.fromisoformat(s["sold_at"][:10]) for s in purchases) + timedelta(
            days=int(rule["window_days"])
        )
        first_known = min(utc_timestamp(s["available_at"]) for s in purchases)
        day = start
        while day <= last:
            end = datetime.combine(day + timedelta(days=1), datetime.min.time(), UTC)
            native = claims[(day.isoformat(), *series)]
            known = max(
                end + timedelta(days=int(rule["max_ingestion_delay_days"])),
                first_known,
                utc_timestamp(rule["known_at"]),
            )
            require(
                all(utc_timestamp(c["available_at"]) <= known for c in native),
                "Native return exceeds declared closure bound.",
            )
            result.append(
                Day(
                    event_type="return_completed",
                    business_date=day.isoformat(),
                    **dict(zip(KEY, series, strict=True)),
                    window_end=end.isoformat(),
                    known_at=known.isoformat(),
                    source_complete=True,
                    activity="open",
                    expected_business_ids=sorted(c["id"] for c in native),
                    required_sale_ids=sorted(
                        s["sale_id"] for s in purchases if utc_timestamp(s["sold_at"]) < end
                    ),
                ).model_dump()
            )
            day += timedelta(days=1)
    require(0 < len(result) <= MAX_ROWS, "Day coverage exceeds row budget.")
    result.sort(key=lambda r: (r["event_type"], r["business_date"], *(r[k] for k in KEY)))
    require(
        len({(r["event_type"], r["business_date"], *(r[k] for k in KEY)) for r in result})
        == len(result),
        "Repeated day grain.",
    )
    return result
