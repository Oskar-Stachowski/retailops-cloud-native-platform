"""Independently reconcile fulfilled source facts, pricing, censoring and financial returns."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from data.generator.csv_writer import source_columns
from data.generator.demand_grid import demand_grid
from data.generator.demand_panel import build_daily_panel
from data.generator.demand_schema import DEMAND_GRAIN
from data.generator.dimension_quality import validate_dimensions
from data.generator.dimension_schema import DIMENSION_COLUMNS
from data.generator.observation_history import (
    HISTORY_TABLE,
    build_daily_versions,
    validate_daily_versions,
)
from data.generator.pricing_quality import validate_pricing
from data.generator.progress import stage
from data.generator.return_quality import build_return_report
from data.generator.return_reconciliation import return_boundaries
from data.inventory.contract import require, utc_timestamp
from data.inventory.ledger import InventoryLedger
from data.inventory.projection_contract import InventorySnapshot
from data.inventory.simulation_contract import ChronologicalScenario
from data.inventory.simulation_reconciliation import reconcile_simulation, verify_demand_outcomes
from data.inventory.source_commerce import RESTOCKABLE_REASONS
from data.inventory.source_observations import (
    known_commerce_view,
    source_legacy_returns,
    source_return_cohorts,
)

if TYPE_CHECKING:
    from data.generator.configuration import ResolvedGenerationConfig


@stage("source_reconciliation")
def reconcile_source_commerce(
    candidate: dict, output: dict, generation: ResolvedGenerationConfig, scenario: dict
) -> dict[str, Any]:
    inventory, tables = output["inventory"], output["commerce"]
    commerce = reconcile_simulation(inventory)
    demand = verify_demand_outcomes(
        inventory,
        output["simulation_truth"],
        tuple(ChronologicalScenario.from_payload(scenario).demand_arrivals),
    )
    for name, rows in tables.items():
        require(len({r["id"] for r in rows}) == len(rows), "Duplicate source fact ID: " + name)
        require(
            all(set(row) == set(source_columns(name, generation.profile, "2.6.0")) for row in rows),
            "Unpublished commerce facts contain unexpected/private columns: " + name,
        )
    for name in (
        "products",
        "stores",
        "warehouses",
        *DIMENSION_COLUMNS,
        "price_plans",
        "promotion_plans",
        "return_policies",
        "daily_demand_exclusions",
    ):
        require(
            tables[name] == candidate[name],
            "Integration changed immutable input facts/plans: " + name,
        )
    _reconcile_routes(inventory, tables)
    sales = {r["id"]: r for r in tables["sales"]}
    actual = {r["sale_id"]: r for r in inventory["sales"]}
    refs = {r["sale_id"]: r for r in tables["sale_price_references"]}
    items = {r["id"]: r for r in tables["order_items"]}
    orders = {r["id"]: r for r in tables["orders"]}
    require(
        len(sales) == len(actual) == len(refs) == len(items)
        and sales.keys() == actual.keys() == refs.keys(),
        "Actual source sales, items, price references and inventory sales must be bijective.",
    )
    _reconcile_sales(inventory, tables, candidate)
    validate_dimensions(tables, generation)
    items_by_order = defaultdict(list)
    for item in items.values():
        items_by_order[item["order_id"]].append(item)
    for order_id, order in orders.items():
        lines = items_by_order[order_id]
        require(
            bool(lines)
            and len({item["product_id"] for item in lines}) == len(lines)
            and sum((Decimal(item["total_amount"]) for item in lines), Decimal(0))
            == Decimal(order["order_total"]),
            "Empty, repeated-SKU or incorrectly totalled fulfilled basket.",
        )
    pricing = validate_pricing(
        {**tables, "promotion_effect_truth": candidate["promotion_effect_truth"]}, generation
    )
    view = known_commerce_view(tables, inventory["sales"])
    returns = _reconcile_observations(tables, view, generation)
    grid, exclusions = demand_grid(tables, generation)
    require(tables["daily_demand_exclusions"] == exclusions, "Lifecycle exclusions changed.")
    require(
        len(tables["daily_demand_observations"]) == len(grid),
        "Missing fulfilled daily panel grain.",
    )
    _reconcile_daily_demand(candidate, output)
    _reconcile_returns(output)
    snapshots = _reconcile_snapshots(output, scenario)
    return {
        **commerce,
        **demand,
        "daily_grains": len(grid),
        "latent_daily_grains": len(candidate["daily_demand_truth"]),
        "pricing_checks": len(pricing["checks"]),
        "return_checks": len(returns["checks"]),
        "observation_versions": len(tables[HISTORY_TABLE]),
        "financial_returns": len(tables["return_events"]),
        "inventory_snapshots": snapshots,
    }


def _reconcile_routes(inventory: dict, tables: dict) -> None:
    source_routes = {r["id"]: r for r in tables["fulfillment_routes"]}
    mappings = {r["route_id"]: r for r in inventory["source_route_versions"]}
    require(
        len(mappings) == len(inventory["source_route_versions"]) == len(source_routes),
        "Route version lineage is incomplete/duplicated.",
    )
    require(
        {r["id"] for r in inventory["fulfillment_routes"]} == source_routes.keys(),
        "Inventory route IDs differ from source routes.",
    )
    for row in inventory["fulfillment_routes"]:
        original, mapping = source_routes[row["id"]], mappings[row["id"]]
        require(
            mapping
            == {
                "route_id": row["id"],
                "source_version": int(original["version"]),
                "inventory_revision": row["version"],
            },
            "Route version lineage disagrees.",
        )
        for field in row:
            if field not in {"version", "available_at"}:
                require(
                    row[field] == original[field], "Source fulfillment route changed in adapter."
                )
        require(
            utc_timestamp(row["available_at"]) == utc_timestamp(original["available_at"]),
            "Source route availability changed in adapter.",
        )


def _reconcile_sales(inventory: dict, tables: dict, candidate: dict) -> None:
    sales = {r["id"]: r for r in tables["sales"]}
    actual = {r["sale_id"]: r for r in inventory["sales"]}
    refs = {r["sale_id"]: r for r in tables["sale_price_references"]}
    items = {r["id"]: r for r in tables["order_items"]}
    orders = {r["id"]: r for r in tables["orders"]}
    original_refs = {r["sale_id"]: r for r in candidate["sale_price_references"]}
    original_items = {r["id"]: r for r in candidate["order_items"]}
    original_orders = {r["id"]: r for r in candidate["orders"]}
    for sale_id, row in actual.items():
        sale, ref = sales[sale_id], refs[sale_id]
        item = items[ref["order_item_id"]]
        order = orders[item["order_id"]]
        original_ref = original_refs[row["source_reference"]]
        original_item = original_items[original_ref["order_item_id"]]
        original_order = original_orders[original_item["order_id"]]
        require(
            item["id"] == original_item["id"]
            and order["id"] == original_order["id"]
            and all(order[f] == original_order[f] for f in order if f != "order_total"),
            "Fulfillment reassigned an original basket or purchased line.",
        )
        require(
            sale["product_id"] == item["product_id"] == row["product_id"]
            and item["order_id"] == row["order_id"]
            and sale["order_reference"] == order["order_reference"]
            and ref["selling_location_id"] == row["selling_location_id"]
            and ref["channel"] == row["channel"] == sale["channel"] == order["channel"]
            and utc_timestamp(order["ordered_at"]) == utc_timestamp(row["ordered_at"]),
            "Fulfilled sale references wrong source basket/line/location/channel.",
        )
        for fact in (sale, item):
            require(
                (int(fact["quantity"]), fact["unit_price"], fact["total_amount"], fact["currency"])
                == (row["quantity"], row["unit_price"], row["gross_revenue"], row["currency"]),
                "Fulfilled source quantity or paid price differs from inventory commerce.",
            )
        require(
            utc_timestamp(sale["sold_at"]) == utc_timestamp(row["sold_at"])
            and utc_timestamp(sale["ingested_at"]) == utc_timestamp(row["ingested_at"]),
            "Fulfilled source sale chronology differs from inventory issue.",
        )


def _reconcile_observations(tables: dict, view: dict, generation: ResolvedGenerationConfig) -> dict:
    returns = build_return_report(view, generation)
    require(
        all(
            c["status"] == "passed"
            for c in returns["checks"]
            if c["check_id"] != "return_snapshot_reconciliation"
        ),
        "Source financial-return gate failed: "
        + "; ".join(
            c["check_id"] + ": " + c["description"]
            for c in returns["checks"]
            if c["status"] != "passed" and c["check_id"] != "return_snapshot_reconciliation"
        ),
    )
    require(
        tables["daily_return_cohorts"] == source_return_cohorts(view, generation)
        and tables["returns"]
        == source_legacy_returns(view, return_boundaries(generation)["history"]),
        "Return snapshots ignore causal sale availability.",
    )
    require(
        tables["daily_demand_observations"] == build_daily_panel(view, generation)
        and tables[HISTORY_TABLE] == build_daily_versions(view, generation),
        "Daily panel/history differs from causally available fulfilled sales.",
    )
    validate_daily_versions(tables)
    return returns


def _reconcile_daily_demand(candidate: dict, output: dict) -> None:
    tables = output["commerce"]
    requested: Counter[tuple] = Counter()
    observed: Counter[tuple] = Counter()
    lost: Counter[tuple] = Counter()
    for row in output["simulation_truth"]["demand_outcomes"]:
        key = (
            utc_timestamp(row["occurred_at"]).date().isoformat(),
            row["product_id"],
            row["selling_location_id"],
            row["channel"],
        )
        requested[key] += row["latent_quantity"]
        observed[key] += row["observed_quantity"]
        lost[key] += row["lost_sales_quantity"]
    truth = {
        tuple(r[field] for field in DEMAND_GRAIN): int(r["latent_units"])
        for r in candidate["daily_demand_truth"]
    }
    require(requested.keys() <= truth.keys(), "Demand arrival outside original daily truth.")
    for key, units in truth.items():
        require(
            requested[key] == observed[key] + lost[key] == units,
            "Daily fulfilled plus lost units differ from original sampled demand.",
        )
    require(
        all(
            int(row["observed_units"]) == observed[tuple(row[field] for field in DEMAND_GRAIN)]
            for row in tables["daily_demand_observations"]
        ),
        "Source observations include unfulfilled latent units.",
    )


def _reconcile_returns(output: dict) -> None:
    inventory, tables = output["inventory"], output["commerce"]
    financial = {r["id"]: r for r in tables["return_events"]}
    decisions = {r["return_id"]: r for r in output["return_inventory_decisions"]}
    processed = {r["return_id"]: r for r in inventory["returns"]}
    sales = {r["sale_id"]: r for r in inventory["sales"]}
    require(
        len(financial) == len(decisions) == len(output["return_inventory_decisions"])
        and financial.keys() == decisions.keys(),
        "Financial returns require exactly one inventory disposition.",
    )
    executed = set()
    for return_id, event in financial.items():
        decision, sale = decisions[return_id], sales[event["sale_id"]]
        quality = "accepted" if event["reason"] in RESTOCKABLE_REASONS else "rejected"
        end = utc_timestamp(inventory["history_end_at"])
        disposition = (
            "not_refunded"
            if event["status"] != "refunded"
            else "outside_inventory_window"
            if utc_timestamp(event["returned_at"]) >= end
            else "restocked"
            if quality == "accepted"
            else "quality_rejected"
        )
        require(
            decision
            == {
                "return_id": return_id,
                "sale_id": event["sale_id"],
                "product_id": event["product_id"],
                "stock_location_id": sale["stock_location_id"],
                "quantity": int(event["quantity"]),
                "quality_status": quality,
                "inventory_disposition": disposition,
                "returned_at": event["returned_at"],
                "financial_available_at": event["available_at"],
                "inventory_available_at": (
                    processed[return_id]["available_at"] if return_id in processed else None
                ),
            },
            "Return inventory disposition disagrees with financial eligibility/original warehouse.",
        )
        if disposition in {"restocked", "quality_rejected"}:
            executed.add(return_id)
            require(return_id in processed, "Missing within-window inventory return.")
            row = processed[return_id]
            require(
                row["sale_id"] == event["sale_id"]
                and row["quantity"] == int(event["quantity"])
                and row["quality_status"] == quality
                and row["refund_amount"] == event["refund_amount"]
                and utc_timestamp(row["returned_at"]) == utc_timestamp(event["returned_at"])
                and utc_timestamp(row["available_at"])
                == utc_timestamp(decision["inventory_available_at"]),
                "Processed inventory return differs from concrete financial refund.",
            )
    require(processed.keys() == executed, "Financial rejection/tail produced an inventory return.")


def _reconcile_snapshots(output: dict, scenario: dict) -> int:
    ledger = InventoryLedger.from_payload(output["inventory"]["ledger"])
    start = utc_timestamp(scenario["settings"]["start_at"])
    end = utc_timestamp(scenario["settings"]["end_at"])
    require(
        utc_timestamp(output["inventory"]["history_end_at"]) == end,
        "Inventory history boundary differs from observed demand window.",
    )
    expected: set[tuple[str, str, str]] = set()
    day = start
    while day < end:
        expected.update((day.date().isoformat(), p, s) for p, s in ledger.scope)
        day += timedelta(days=1)
    rows = output["inventory_snapshots"]
    keys = [(r["business_date"], r["product_id"], r["stock_location_id"]) for r in rows]
    require(
        len(set(keys)) == len(keys) and set(keys) == expected,
        "Missing, duplicate or extra source inventory snapshot grain.",
    )
    grouped = defaultdict(list)
    for movement in ledger.movements:
        grouped[movement.position].append(
            (movement, utc_timestamp(movement.occurred_at), utc_timestamp(movement.available_at))
        )
    for row in rows:
        InventorySnapshot.model_validate(row)
        cutoff = utc_timestamp(row["snapshot_at"])
        midnight = cutoff.replace(hour=0, minute=0, second=0, microsecond=0)
        require(
            cutoff == midnight + timedelta(days=1, microseconds=-1)
            and cutoff == utc_timestamp(row["as_of_time"]),
            "Wrong source snapshot cutoff.",
        )
        visible = [
            m
            for m, occurred, available in grouped[row["product_id"], row["stock_location_id"]]
            if occurred <= cutoff and available <= cutoff
        ]
        known = any(m.movement_type == "opening_stock" for m in visible)
        quantity = sum(m.quantity_delta for m in visible) if known else None
        require(
            (row["on_hand"], row["reserved_qty"], row["available_qty"], row["movement_count"])
            == (quantity, 0 if known else None, quantity, len(visible)),
            "Source inventory snapshot differs from independently summed known ledger.",
        )
        require(
            row["status"] == ("known" if known else "not_available")
            and row["last_inventory_event_id"]
            == (visible[-1].inventory_event_id if visible else None)
            and row["source_available_at"]
            == (
                max(utc_timestamp(m.available_at) for m in visible).isoformat() if visible else None
            )
            and row["unit_of_measure"]
            == next(
                m.unit_of_measure for m in ledger.movements if m.product_id == row["product_id"]
            )
            and utc_timestamp(row["period_from_at"]) == midnight
            and utc_timestamp(row["period_to_at"]) == midnight + timedelta(days=1)
            and row["is_full_business_day"],
            "Source snapshot lineage, unit, period or known status is inconsistent.",
        )
    legacy = output["legacy_stock_movements"]
    require(
        len(legacy) == len(ledger.movements) and len({r["id"] for r in legacy}) == len(legacy),
        "Legacy ledger projection duplicated/missed events.",
    )
    aliases = {"opening_stock": "initial_stock", "replenishment_received": "replenishment"}
    for row, movement in zip(legacy, ledger.movements, strict=True):
        require(
            row["id"] == movement.inventory_event_id
            and row["product_id"] == movement.product_id
            and row["warehouse_id"] == movement.stock_location_id
            and int(row["quantity"]) == movement.quantity_delta
            and row["source_reference"] == movement.source_reference
            and row["movement_type"] == aliases.get(movement.movement_type, movement.movement_type),
            "Legacy stock movement lost lineage, location, sign or opening semantics.",
        )
    return len(rows)
