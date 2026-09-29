"""Build and independently reconcile the inventory extension before source publication."""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from typing import Any, Literal

from data.inventory.contract import UTC_TIMESTAMP_PATTERN, Timestamp, require, utc_timestamp
from data.inventory.projection import reconcile_projection
from data.inventory.projection_contract import ProjectionConfig  # noqa: TC001 - Pydantic annotation
from data.inventory.reorder_contract import ReorderConfig, parse_history_coverage
from data.inventory.replenishment_contract import SupplyRecord
from data.inventory.simulation_contract import DemandArrival
from data.inventory.simulation_reconciliation import verify_demand_outcomes
from data.inventory.simulator import money_amount
from data.inventory.source_commerce import RESTOCKABLE_REASONS
from data.inventory.source_tables_contract import TABLES, field_rules


class PolicyHeader(SupplyRecord):
    contract_version: Literal["reorder-config-1.0.0"]
    policy_version: Literal["periodic-review-stock-position-1.0.0"]
    business_timezone: Literal["UTC"]
    review_anchor_at: Timestamp
    known_at: Timestamp
    available_at: Timestamp


class TableContext(SupplyRecord):
    opening_at: Timestamp
    policy: PolicyHeader
    projection: ProjectionConfig
    evaluated_at: Timestamp


def normalize_tables(tables: dict[str, list[dict]]) -> dict[str, list[dict]]:
    require(set(tables) == set(TABLES), "Missing/extra inventory table.")
    result = {}
    for name, definition in TABLES.items():
        rows = [definition.model.model_validate(row).model_dump() for row in tables[name]]
        properties = field_rules(definition.model)
        for row in rows:
            for field, value in row.items():
                if value is not None and properties[field].get("pattern") == UTC_TIMESTAMP_PATTERN:
                    row[field] = utc_timestamp(value).isoformat()
        keys = [tuple(row[field] for field in definition.grain) for row in rows]
        require(len(set(keys)) == len(keys), "Duplicate inventory table grain: " + name)
        result[name] = sorted(rows, key=lambda r: tuple(r[f] for f in definition.grain))
    return result


def tables_from_source(source: dict, projection: dict) -> tuple[dict, TableContext]:
    operational = source["inventory"]
    ledger, supply = operational["ledger"], operational["supply"]
    inputs = source["effective_configuration"]
    tables = {
        "inventory_products": ledger["products"],
        "inventory_stock_locations": ledger["stock_locations"],
        "inventory_scope": ledger["inventory_scope"],
        "inventory_ledger": ledger["movements"],
        "inventory_selling_locations": operational["selling_locations"],
        "inventory_fulfillment_routes": operational["fulfillment_routes"],
        "inventory_route_versions": operational["source_route_versions"],
        **{
            n: supply[n]
            for n in (
                "suppliers",
                "product_suppliers",
                "replenishment_orders",
                "delivery_plan_versions",
                "replenishment_receipts",
            )
        },
        "inventory_sales": operational["sales"],
        "inventory_returns": operational["returns"],
        "return_events": [
            {**r, "quantity": int(r["quantity"])} for r in source["commerce"]["return_events"]
        ],
        "return_inventory_decisions": source["return_inventory_decisions"],
        "inventory_history_coverage": operational["history_coverage"],
        "inventory_reorder_rules": inputs["policy"]["rules"],
        "inventory_daily_snapshots": projection["operational"],
        "inventory_demand_arrivals": inputs["scenario"]["demand_arrivals"],
        **{
            "inventory_" + n: source["simulation_truth"][n]
            for n in ("demand_outcomes", "supplier_samples", "scheduled_receipt_tail")
        },
        **{
            ("inventory_" + n if n != "stockout_episodes" else n): projection["simulation_truth"][n]
            for n in (
                "physical_daily_balances",
                "stockout_episodes",
                "lost_sales_impacts",
                "window_diagnostics",
            )
        },
    }
    evaluations = {r["evaluated_at"] for r in tables["inventory_window_diagnostics"]}
    require(len(evaluations) == 1, "Inventory diagnostics require one evaluation cutoff.")
    context = TableContext.model_validate(
        {
            "opening_at": ledger["opening_at"],
            "policy": {k: v for k, v in inputs["policy"].items() if k != "rules"},
            "projection": projection["configuration"],
            "evaluated_at": evaluations.pop(),
        }
    )
    return normalize_tables(tables), context


def operational_from_tables(tables: dict, context: TableContext) -> dict:
    masters = {
        "products": tables["inventory_products"],
        "stock_locations": tables["inventory_stock_locations"],
    }
    return {
        "ledger": {
            "contract_version": "inventory-ledger-1.0.0",
            "opening_policy": "single_opening_movement",
            "reservation_policy": "none",
            "opening_at": context.opening_at,
            **masters,
            "inventory_scope": tables["inventory_scope"],
            "movements": tables["inventory_ledger"],
        },
        "supply": {
            "contract_version": "replenishment-1.0.0",
            "over_receipt_policy": "reject",
            **masters,
            **{
                n: tables[n]
                for n in (
                    "suppliers",
                    "product_suppliers",
                    "replenishment_orders",
                    "delivery_plan_versions",
                    "replenishment_receipts",
                )
            },
        },
        "sales": tables["inventory_sales"],
        "returns": tables["inventory_returns"],
        "selling_locations": tables["inventory_selling_locations"],
        "fulfillment_routes": tables["inventory_fulfillment_routes"],
        "source_route_versions": tables["inventory_route_versions"],
        "history_coverage": tables["inventory_history_coverage"],
    }


def projection_from_tables(tables: dict, context: TableContext) -> dict:
    return {
        "contract_version": "inventory-projection-1.0.0",
        "configuration": context.projection.model_dump(),
        "operational": tables["inventory_daily_snapshots"],
        "simulation_truth": {
            "data_class": "simulation_truth",
            **{
                n: tables[("inventory_" + n) if n != "stockout_episodes" else n]
                for n in (
                    "physical_daily_balances",
                    "stockout_episodes",
                    "lost_sales_impacts",
                    "window_diagnostics",
                )
            },
        },
    }


def _returns(tables: dict, context: TableContext) -> None:
    sales = {r["sale_id"]: r for r in tables["inventory_sales"]}
    decisions = {r["return_id"]: r for r in tables["return_inventory_decisions"]}
    processed = {r["return_id"]: r for r in tables["inventory_returns"]}
    financial = {r["id"]: r for r in tables["return_events"]}
    require(set(financial) == set(decisions), "Return disposition coverage differs from refunds.")
    returned: dict[str, int] = defaultdict(int)
    expected_processed = set()
    end = utc_timestamp(context.projection.end_at)
    for identifier, event in financial.items():
        require(event["sale_id"] in sales, "Financial return has no actual sale.")
        sale, decision = sales[event["sale_id"]], decisions[identifier]
        returned[event["sale_id"]] += event["quantity"]
        quality = "accepted" if event["reason"] in RESTOCKABLE_REASONS else "rejected"
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
            all(
                event[f] == sale[f]
                for f in ("product_id", "selling_location_id", "channel", "currency", "order_id")
            )
            and returned[event["sale_id"]] <= sale["quantity"]
            and event["refund_amount"]
            == (
                money_amount(sale["unit_price"], event["quantity"])
                if event["status"] == "refunded"
                else "0.00"
            )
            and utc_timestamp(sale["sold_at"])
            <= utc_timestamp(event["returned_at"])
            <= utc_timestamp(event["ingested_at"])
            <= utc_timestamp(event["available_at"])
            and utc_timestamp(sale["available_at"]) <= utc_timestamp(event["available_at"]),
            "Financial return differs from actual purchase or causal availability.",
        )
        require(
            all(
                decision[f] == event[f]
                for f in ("sale_id", "product_id", "quantity", "returned_at")
            )
            and decision["stock_location_id"] == sale["stock_location_id"]
            and decision["financial_available_at"] == event["available_at"]
            and (decision["quality_status"], decision["inventory_disposition"])
            == (quality, disposition),
            "Return inventory disposition differs from financial eligibility, quality or tail.",
        )
        if disposition in {"restocked", "quality_rejected"}:
            expected_processed.add(identifier)
            require(identifier in processed, "Physical return processing is missing.")
            physical = processed[identifier]
            require(
                all(
                    physical[f] == decision[f]
                    for f in (
                        "sale_id",
                        "product_id",
                        "stock_location_id",
                        "quantity",
                        "quality_status",
                        "returned_at",
                    )
                )
                and physical["available_at"] == decision["inventory_available_at"],
                "Return disposition differs from physical return.",
            )
        else:
            require(
                decision["inventory_available_at"] is None,
                "Unprocessed return has inventory availability.",
            )
    require(set(processed) == expected_processed, "Ineligible financial return changed inventory.")


def reconcile_tables(tables: dict, context: TableContext) -> dict[str, Any]:
    tables = normalize_tables(tables)
    operational = operational_from_tables(tables, context)
    truth = {"demand_outcomes": tables["inventory_demand_outcomes"]}
    require(
        utc_timestamp(context.opening_at) == utc_timestamp(context.projection.start_at),
        "Table opening differs from projection start.",
    )
    require(
        all(
            r["evaluated_at"] == utc_timestamp(context.evaluated_at).isoformat()
            for r in tables["inventory_window_diagnostics"]
        ),
        "Backdated diagnostic evaluation cutoff.",
    )
    counts = reconcile_projection(projection_from_tables(tables, context), operational, truth)
    demand = verify_demand_outcomes(
        operational,
        truth,
        tuple(DemandArrival.model_validate(r) for r in tables["inventory_demand_arrivals"]),
    )
    scope = {(r["product_id"], r["stock_location_id"]) for r in tables["inventory_scope"]}
    policy = ReorderConfig.from_payload(
        {**context.policy.model_dump(), "rules": tables["inventory_reorder_rules"]}
    )
    require(
        {(r.product_id, r.stock_location_id) for r in policy.rules} == scope,
        "Reorder policy does not cover physical inventory scope.",
    )
    coverage = parse_history_coverage(
        {
            "contract_version": "inventory-history-coverage-1.0.0",
            "coverage_basis": "observed_ledger_stream",
            "coverage": tables["inventory_history_coverage"],
        }
    )
    require(
        all(
            (r.product_id, r.stock_location_id) in scope
            and utc_timestamp(r.covered_from_at) == utc_timestamp(context.opening_at)
            and utc_timestamp(r.covered_through_at) <= utc_timestamp(context.projection.end_at)
            for r in coverage
        ),
        "History coverage lies outside inventory observation scope.",
    )
    routes = {r["id"]: r for r in tables["inventory_fulfillment_routes"]}
    require(
        set(routes) == {r["route_id"] for r in tables["inventory_route_versions"]}
        and all(
            r["inventory_revision"] == routes[r["route_id"]]["version"]
            for r in tables["inventory_route_versions"]
        ),
        "Source route revision lineage differs from inventory routes.",
    )
    orders = {r["replenishment_order_id"]: r for r in tables["replenishment_orders"]}
    samples = {r["order_id"]: r for r in tables["inventory_supplier_samples"]}
    require(set(samples) == set(orders), "Supplier samples do not cover placed orders.")
    receipts = tables["replenishment_receipts"] + tables["inventory_scheduled_receipt_tail"]
    require(
        len({r["receipt_id"] for r in receipts}) == len(receipts),
        "Executed receipt repeated in future truth tail.",
    )
    for row in tables["inventory_scheduled_receipt_tail"]:
        require(
            row["replenishment_order_id"] in orders
            and utc_timestamp(row["received_at"]) >= utc_timestamp(context.projection.end_at),
            "Future receipt tail is unknown or already physical.",
        )
    received: dict[str, int] = defaultdict(int)
    for row in receipts:
        identifier = row["replenishment_order_id"]
        require(identifier in orders, "Scheduled receipt has no placed order.")
        order, sample = orders[identifier], samples[identifier]
        received[identifier] += row["received_quantity"]
        prefix = (
            f"supplier-simulation:supplier-fulfillment-two-point-1.0.0:{sample['simulation_id']}:"
        )
        require(
            all(
                row[f] == order[f]
                for f in ("product_id", "supplier_id", "stock_location_id", "unit_of_measure")
            )
            and row["source_reference"] in {prefix + "0", prefix + "1"}
            and utc_timestamp(row["received_at"])
            >= utc_timestamp(order["ordered_at"]) + timedelta(days=sample["lead_days"])
            and utc_timestamp(row["received_at"])
            <= utc_timestamp(row["ingested_at"])
            <= utc_timestamp(row["available_at"])
            and utc_timestamp(order["available_at"]) <= utc_timestamp(row["available_at"]),
            "Scheduled receipt differs from order, supplier sample or chronology.",
        )
    require(
        all(
            received[identifier] == order["ordered_quantity"]
            for identifier, order in orders.items()
        ),
        "Executed plus future receipts do not cover placed quantities exactly.",
    )
    _returns(tables, context)
    return {
        "tables": len(tables),
        "operational_tables": sum(d.data_class != "simulation_truth" for d in TABLES.values()),
        "truth_tables": sum(d.data_class == "simulation_truth" for d in TABLES.values()),
        **counts,
        **demand,
    }
