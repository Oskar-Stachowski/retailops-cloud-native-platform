"""Adapt operational availability to existing observation builders, preserving raw ingestion."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from data.generator.common import deterministic_uuid
from data.generator.demand_panel import build_daily_panel
from data.generator.observation_history import HISTORY_TABLE, build_daily_versions
from data.generator.pricing_plans import daily_price_observations
from data.generator.return_reconciliation import (
    ReturnLedger,
    legacy_return_projection,
    return_boundaries,
)
from data.generator.return_schema import RETURN_GRAIN, RETURNS_VERSION
from data.inventory.contract import utc_timestamp

if TYPE_CHECKING:
    from data.generator.configuration import ResolvedGenerationConfig


def known_commerce_view(tables: dict, inventory_sales: list[dict]) -> dict:
    availability = {row["sale_id"]: row["available_at"] for row in inventory_sales}
    # Existing builders use ingestion as their knowledge cutoff. This read-only
    # adapter feeds causal availability; persisted source facts retain raw ingestion.
    return {
        **tables,
        "sales": [{**sale, "ingested_at": availability[sale["id"]]} for sale in tables["sales"]],
    }


def rebuild_observations(
    tables: dict, inventory_sales: list[dict], generation: ResolvedGenerationConfig
) -> None:
    view = known_commerce_view(tables, inventory_sales)
    tables["daily_price_observations"] = daily_price_observations(
        tables["sales"], tables["sale_price_references"]
    )
    tables["daily_demand_observations"] = build_daily_panel(view, generation)
    tables[HISTORY_TABLE] = build_daily_versions(view, generation)
    tables["daily_return_cohorts"] = source_return_cohorts(view, generation)
    tables["returns"] = source_legacy_returns(view, return_boundaries(generation)["history"])


def source_return_cohorts(view: dict, generation: ResolvedGenerationConfig) -> list[dict]:
    ledger = ReturnLedger(view)
    grouped = defaultdict(list)
    for sale in view["sales"]:
        grouped[tuple(ledger.refs[sale["id"]][f] for f in RETURN_GRAIN)].append(sale)
    rows = []
    for panel in sorted(
        view["daily_demand_observations"], key=lambda r: tuple(r[f] for f in RETURN_GRAIN)
    ):
        key = tuple(panel[f] for f in RETURN_GRAIN)
        for kind, boundary in return_boundaries(generation).items():
            cutoff = utc_timestamp(boundary)
            facts = grouped[key]
            visible = [sale for sale in facts if utc_timestamp(sale["ingested_at"]) <= cutoff]
            values = ledger.reconcile(visible, cutoff)
            if len(visible) != len(facts):
                values["return_data_complete"] = "false"
            rows.append(
                {
                    "id": deterministic_uuid("return_cohort", ":".join(key) + ":" + boundary),
                    **dict(zip(RETURN_GRAIN, key, strict=True)),
                    "snapshot_kind": kind,
                    "as_of_time": boundary,
                    **values,
                    "currency": panel["currency"],
                    "available_at": boundary,
                    "returns_policy_version": RETURNS_VERSION,
                }
            )
    return rows


def source_legacy_returns(view: dict, boundary: str) -> list[dict]:
    cutoff = utc_timestamp(boundary)
    known_sales = {r["id"] for r in view["sales"] if utc_timestamp(r["ingested_at"]) <= cutoff}
    return legacy_return_projection(
        {
            **view,
            "return_events": [r for r in view["return_events"] if r["sale_id"] in known_sales],
        },
        boundary,
    )
