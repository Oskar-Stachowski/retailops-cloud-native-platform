from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

from data.generator.business_calendar import utc_midnight
from data.generator.common import deterministic_uuid, money
from data.generator.dimension_quality import require, timestamp
from data.generator.return_schema import RETURN_GRAIN, RETURN_TAIL_DAYS, RETURNS_VERSION

if TYPE_CHECKING:
    from datetime import datetime

    from data.generator.configuration import ResolvedGenerationConfig


def return_boundaries(config: ResolvedGenerationConfig) -> dict[str, str]:
    return {
        "history": utc_midnight(config.end_date + timedelta(days=1)),
        "return_tail": utc_midnight(config.end_date + timedelta(days=RETURN_TAIL_DAYS + 1)),
    }


class ReturnLedger:
    """Observed line returns only; materialization never consumes unavailable events."""

    def __init__(self, tables: dict) -> None:
        self.sales = {r["id"]: r for r in tables["sales"]}
        self.refs = {r["sale_id"]: r for r in tables["sale_price_references"]}
        self.policies = {(r["category_id"], r["channel"]): r for r in tables["return_policies"]}
        self.catalog = {r["id"]: r for r in tables["product_catalog"]}
        self.events = defaultdict(list)
        for event in tables["return_events"]:
            self.events[event["sale_id"]].append(event)

    def reconcile(self, facts: list[dict], as_of: datetime) -> dict[str, str]:
        require(
            all(
                timestamp(r["sold_at"]) <= as_of and timestamp(r["ingested_at"]) <= as_of
                for r in facts
            ),
            "Sale unavailable at return reconciliation cutoff.",
        )
        units = sum(int(r["quantity"]) for r in facts)
        gross = sum((Decimal(r["total_amount"]) for r in facts), Decimal(0))
        visible = [
            event
            for sale in facts
            for event in self.events[sale["id"]]
            if timestamp(event["returned_at"]) <= as_of
            and timestamp(event["ingested_at"]) <= as_of
            and timestamp(event["available_at"]) <= as_of
            and event["status"] == "refunded"
        ]
        returned = sum(int(r["quantity"]) for r in visible)
        refund = sum((Decimal(r["refund_amount"]) for r in visible), Decimal(0))
        mature = all(
            timestamp(sale["sold_at"])
            + timedelta(
                days=int(
                    self.policies[self.catalog[sale["product_id"]]["category_id"], sale["channel"]][
                        "window_days"
                    ]
                )
                + int(
                    self.policies[self.catalog[sale["product_id"]]["category_id"], sale["channel"]][
                        "max_ingestion_delay_days"
                    ]
                )
            )
            <= as_of
            for sale in facts
        )
        return {
            "observed_units": str(units),
            "return_units": str(returned),
            "net_units": str(units - returned),
            "gross_revenue": money(gross),
            "refund_amount": money(refund),
            "net_revenue": money(gross - refund),
            "return_data_complete": str(mature).lower(),
        }


def build_return_cohorts(tables: dict, config: ResolvedGenerationConfig) -> list[dict[str, str]]:
    ledger = ReturnLedger(tables)
    facts = defaultdict(list)
    for sale in tables["sales"]:
        facts[tuple(ledger.refs[sale["id"]][field] for field in RETURN_GRAIN)].append(sale)
    rows = []
    for panel in sorted(
        tables["daily_demand_observations"], key=lambda r: tuple(r[f] for f in RETURN_GRAIN)
    ):
        key = tuple(panel[field] for field in RETURN_GRAIN)
        for kind, boundary in return_boundaries(config).items():
            rows.append(
                {
                    "id": deterministic_uuid("return_cohort", ":".join(key) + ":" + boundary),
                    **dict(zip(RETURN_GRAIN, key, strict=True)),
                    "snapshot_kind": kind,
                    "as_of_time": boundary,
                    **ledger.reconcile(facts[key], timestamp(boundary)),
                    "currency": panel["currency"],
                    "available_at": boundary,
                    "returns_policy_version": RETURNS_VERSION,
                }
            )
    return rows


def legacy_return_projection(tables: dict, as_of_time: str) -> list[dict[str, str]]:
    from data.generator.csv_writer import TABLE_COLUMNS  # noqa: PLC0415 - avoid schema import cycle

    cutoff = timestamp(as_of_time)
    return [
        {
            **{field: event[field] for field in TABLE_COLUMNS["returns"]},
            "status": "received" if event["status"] == "refunded" else "rejected",
        }
        for event in tables["return_events"]
        if max(timestamp(event[f]) for f in ("returned_at", "ingested_at", "available_at"))
        <= cutoff
    ]
