from __future__ import annotations

from bisect import bisect_left
from collections import defaultdict
from typing import Any

from data.inventory.contract import require, utc_timestamp
from data.inventory.fulfillment_routes import resolve_route, validate_routes
from data.inventory.ledger import InventoryLedger
from data.inventory.replenishment import ReplenishmentBook
from data.inventory.simulation_contract import (
    CommerceOutput,
    DemandArrival,
    FulfillmentRoute,
    SellingLocation,
)
from data.inventory.simulator import money_amount


def _identity(row: dict, time_field: str) -> tuple:
    return (
        row["product_id"],
        row["stock_location_id"],
        row["unit_of_measure"],
        utc_timestamp(row[time_field]),
        utc_timestamp(row["ingested_at"]),
        utc_timestamp(row["available_at"]),
        row["sequence"],
    )


def reconcile_simulation(operational: dict[str, Any]) -> dict[str, int]:
    CommerceOutput.model_validate(
        {"sales": operational["sales"], "returns": operational["returns"]}
    )
    ledger = InventoryLedger.from_payload(operational["ledger"])
    supply = ReplenishmentBook.from_payload(operational["supply"])
    counts = supply.reconcile_ledger(ledger)
    sales = {s["sale_id"]: s for s in operational["sales"]}
    returns = {r["return_id"]: r for r in operational["returns"]}
    require(
        len(sales) == len(operational["sales"]) and len(returns) == len(operational["returns"]),
        "Duplicate sale or return ID.",
    )
    routes = tuple(FulfillmentRoute.model_validate(r) for r in operational["fulfillment_routes"])
    selling = tuple(SellingLocation.model_validate(r) for r in operational["selling_locations"])
    selling_ids = {s.id for s in selling}
    require(
        len(selling_ids) == len(selling)
        and len({s.location_code for s in selling}) == len(selling)
        and len({r.id for r in routes}) == len(routes),
        "Duplicate selling location or route identity.",
    )
    require(
        all(r.selling_location_id in selling_ids for r in routes), "Unknown route selling location."
    )
    validate_routes(routes, {s for s, _code in ledger.stock_location_codes})
    sale_movements = [m for m in ledger.movements if m.movement_type == "sale"]
    require(len(sale_movements) == len(sales), "Every sale requires exactly one inventory issue.")
    seen = set()
    for movement in sale_movements:
        require(
            movement.source_reference in sales and movement.source_reference not in seen,
            "Sale issue has missing or duplicate sale reference.",
        )
        sale = sales[movement.source_reference]
        route = resolve_route(routes, sale["selling_location_id"], sale["channel"], sale["sold_at"])
        require(
            route.id == sale["fulfillment_route_id"]
            and route.stock_location_id == sale["stock_location_id"],
            "Sale used wrong historical fulfillment route.",
        )
        require(
            _identity(movement.record(), "occurred_at") == _identity(sale, "sold_at")
            and -movement.quantity_delta == sale["quantity"],
            "Sale inventory issue differs from actual sale.",
        )
        require(
            utc_timestamp(sale["ordered_at"]) <= utc_timestamp(sale["sold_at"])
            and int(sale["unit_price"].replace(".", "")) > 0
            and sale["gross_revenue"] == money_amount(sale["unit_price"], sale["quantity"]),
            "Sale chronology or revenue is inconsistent.",
        )
        seen.add(movement.source_reference)
    restocks = [m for m in ledger.movements if m.movement_type == "return_to_stock"]
    expected = {r["return_id"]: r for r in returns.values() if r["quality_status"] == "accepted"}
    require(len(restocks) == len(expected), "Only accepted returns require exactly one restock.")
    seen = set()
    for movement in restocks:
        require(
            movement.source_reference in expected and movement.source_reference not in seen,
            "Rejected, missing or duplicate return restock.",
        )
        row = expected[movement.source_reference]
        require(
            _identity(movement.record(), "occurred_at") == _identity(row, "returned_at")
            and movement.quantity_delta == row["quantity"],
            "Return restock differs from accepted return.",
        )
        seen.add(movement.source_reference)
    returned: dict[str, int] = defaultdict(int)
    for row in returns.values():
        require(
            row["sale_id"] in sales and row["quality_status"] in {"accepted", "rejected"},
            "Return references unknown sale or quality decision.",
        )
        sale = sales[row["sale_id"]]
        require(
            (row["product_id"], row["stock_location_id"], row["unit_of_measure"], row["currency"])
            == (
                sale["product_id"],
                sale["stock_location_id"],
                sale["unit_of_measure"],
                sale["currency"],
            ),
            "Return differs from original sale product/location/unit/currency.",
        )
        require(
            type(row["quantity"]) is int and row["quantity"] > 0,
            "Return quantity must be a positive integer.",
        )
        returned[row["sale_id"]] += row["quantity"]
        require(
            returned[row["sale_id"]] <= sale["quantity"],
            "Returns exceed actual fulfilled purchase.",
        )
        require(
            utc_timestamp(sale["sold_at"])
            <= utc_timestamp(row["returned_at"])
            <= utc_timestamp(row["ingested_at"])
            <= utc_timestamp(row["available_at"])
            and utc_timestamp(sale["available_at"]) <= utc_timestamp(row["available_at"]),
            "Return has invalid chronology or availability.",
        )
        require(
            (utc_timestamp(sale["sold_at"]), sale["sequence"])
            < (utc_timestamp(row["returned_at"]), row["sequence"])
            and utc_timestamp(sale["ingested_at"]) <= utc_timestamp(row["ingested_at"]),
            "Return precedes the original sale or its ingestion.",
        )
        require(
            row["refund_amount"] == money_amount(sale["unit_price"], row["quantity"]),
            "Refund differs from originally paid price.",
        )
    return {
        **counts,
        "sales": len(sales),
        "sale_issues": len(sale_movements),
        "returns": len(returns),
        "accepted_restocks": len(restocks),
        "sold_quantity": sum(s["quantity"] for s in sales.values()),
    }


def verify_demand_outcomes(
    operational: dict[str, Any],
    truth: dict[str, Any],
    arrivals: tuple[DemandArrival, ...] | None = None,
) -> dict[str, int]:
    ledger = InventoryLedger.from_payload(operational["ledger"])
    position_keys = defaultdict(list)
    position_balances: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0])
    for movement in ledger.movements:
        position_keys[movement.position].append(movement.ordering_key)
        balances = position_balances[movement.position]
        balances.append(balances[-1] + movement.quantity_delta)
    sales = {s["source_reference"]: s for s in operational["sales"]}
    require(len(sales) == len(operational["sales"]), "Duplicate fulfilled demand reference.")
    outcomes = truth["demand_outcomes"]
    routes = tuple(FulfillmentRoute.model_validate(r) for r in operational["fulfillment_routes"])
    inputs = {a.demand_id: a for a in arrivals} if arrivals is not None else None
    require(
        len({r["demand_id"] for r in outcomes}) == len(outcomes), "Duplicate demand outcome ID."
    )
    if inputs is not None:
        require(
            set(inputs) == {r["demand_id"] for r in outcomes},
            "Demand outcome coverage differs from input arrivals.",
        )
    for row in outcomes:
        route = resolve_route(
            routes, row["selling_location_id"], row["channel"], row["occurred_at"]
        )
        require(
            route.stock_location_id == row["stock_location_id"],
            "Demand outcome used wrong historical route.",
        )
        if inputs is not None:
            arrival = inputs[row["demand_id"]]
            require(
                (
                    arrival.product_id,
                    arrival.selling_location_id,
                    arrival.channel,
                    arrival.latent_quantity,
                    utc_timestamp(arrival.occurred_at),
                    arrival.sequence,
                )
                == (
                    row["product_id"],
                    row["selling_location_id"],
                    row["channel"],
                    row["latent_quantity"],
                    utc_timestamp(row["occurred_at"]),
                    row["sequence"],
                ),
                "Demand outcome differs from input arrival.",
            )
        require(
            all(
                type(row[f]) is int and row[f] >= 0
                for f in (
                    "latent_quantity",
                    "observed_quantity",
                    "lost_sales_quantity",
                    "stock_before",
                    "stock_after",
                    "sequence",
                )
            ),
            "Invalid demand outcome quantities.",
        )
        position = row["product_id"], row["stock_location_id"]
        require(position in ledger.scope, "Demand outcome references unknown stock position.")
        key = utc_timestamp(row["occurred_at"]), row["sequence"]
        before = position_balances[position][bisect_left(position_keys[position], key)]
        observed = min(before, row["latent_quantity"])
        require(
            (
                row["stock_before"],
                row["observed_quantity"],
                row["stock_after"],
                row["lost_sales_quantity"],
            )
            == (before, observed, before - observed, row["latent_quantity"] - observed),
            "Demand was not limited by chronological shared stock.",
        )
        expected_reason = (
            "no_demand"
            if row["latent_quantity"] == 0
            else "inventory_constraint"
            if observed < row["latent_quantity"]
            else "fulfilled"
        )
        require(
            row["reason"] == expected_reason, "Demand loss reason differs from physical process."
        )
        if observed:
            require(row["demand_id"] in sales, "Fulfilled demand has no actual sale.")
            sale = sales[row["demand_id"]]
            require(
                (
                    sale["product_id"],
                    sale["stock_location_id"],
                    sale["selling_location_id"],
                    sale["channel"],
                    sale["quantity"],
                    utc_timestamp(sale["sold_at"]),
                    sale["sequence"],
                )
                == (
                    position[0],
                    position[1],
                    row["selling_location_id"],
                    row["channel"],
                    observed,
                    key[0],
                    key[1],
                ),
                "Sale differs from fulfilled demand outcome.",
            )
        else:
            require(row["demand_id"] not in sales, "Zero fulfilled demand created a sale.")
    require(
        set(sales) == {r["demand_id"] for r in outcomes if r["observed_quantity"] > 0},
        "Actual sale has no demand outcome.",
    )
    return {
        "arrivals": len(outcomes),
        "latent_quantity": sum(r["latent_quantity"] for r in outcomes),
        "observed_quantity": sum(r["observed_quantity"] for r in outcomes),
        "lost_sales_quantity": sum(r["lost_sales_quantity"] for r in outcomes),
    }
