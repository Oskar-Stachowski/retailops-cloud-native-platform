"""Recheck persisted inventory source facts without regenerating source baskets."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

from data.generator.commerce_pricing import CommercePricing
from data.generator.demand_grid import demand_grid
from data.generator.demand_model import daily_demand
from data.generator.demand_quality import build_demand_report
from data.generator.dimension_quality import build_dimensions_report
from data.generator.dimension_schema import CHANNELS
from data.generator.dimensions import DimensionIndex
from data.generator.observation_history import build_daily_versions
from data.generator.pricing_quality import build_pricing_report
from data.generator.progress import stage
from data.generator.return_quality import build_return_report
from data.generator.return_reconciliation import return_boundaries
from data.generator.simulation import simulation_entities, validate_simulation
from data.generator.source_quality import project_facts
from data.generator.source_realism import build_source_realism
from data.inventory.contract import require, utc_timestamp
from data.inventory.ledger import InventoryLedger
from data.inventory.reorder import review_reorder
from data.inventory.reorder_contract import ReorderConfig, parse_history_coverage
from data.inventory.replenishment import ReplenishmentBook
from data.inventory.replenishment_contract import ReplenishmentOrder
from data.inventory.source_dataset_contract import SOURCE_POLICY, grain
from data.inventory.source_observations import (
    known_commerce_view,
    source_legacy_returns,
    source_return_cohorts,
)
from data.inventory.source_tables import operational_from_tables, reconcile_tables
from data.inventory.source_tables_contract import TABLES
from data.inventory.supplier_fulfillment import simulate_fulfillment
from data.inventory.supplier_truth import SupplierTruth
from ml.features.worker import transform

if TYPE_CHECKING:
    from data.anomalies.contract import AnomalyPlan
    from data.generator.configuration import ResolvedGenerationConfig
    from data.inventory.source_contract import SourceInventoryConfig
    from data.inventory.source_tables import TableContext


def commerce_view(tables: dict) -> dict:
    # Shared return_events is native in 2.7; existing finance builders expect CSV strings.
    legacy = {
        **tables,
        "return_events": [{**r, "quantity": str(r["quantity"])} for r in tables["return_events"]],
    }
    # Legacy PAIR numbering follows selling-location/channel order, rather than
    # physical CSV row order. Source 2.7 sorts each table by its declared grain.
    locations = {r["id"]: r["location_code"] for r in tables["selling_locations"]}
    legacy["channel_assignments"] = sorted(
        tables["channel_assignments"],
        key=lambda r: (
            CHANNELS.index(r["channel"]),
            locations[r["selling_location_id"]],
            int(r["version"]),
        ),
    )
    return known_commerce_view(legacy, tables["inventory_sales"])


def demand_budget(
    tables: dict, generation: ResolvedGenerationConfig, anomaly_plan: AnomalyPlan | None = None
) -> int:
    grid, _ = demand_grid(tables, generation)
    products, stores = (
        {r["id"]: r for r in simulation_entities(tables, "products")},
        {r["id"]: r for r in simulation_entities(tables, "stores")},
    )
    pricing = CommercePricing(tables, DimensionIndex(tables))
    factors = anomaly_plan.factors(tables, generation) if anomaly_plan else {}
    expected = [
        daily_demand(
            products[k[1]],
            stores[f["legacy_store_id"]],
            k,
            pricing,
            generation,
            anomaly_factor=factors.get(k, "1"),
        )
        for k, f in sorted(grid.items())
        if f["location_open"] == "true"
    ]
    key_fields = ("business_date", "product_id", "selling_location_id", "channel")

    def key(row: dict) -> tuple:
        return tuple(row[f] for f in key_fields)

    require(
        sorted(tables["daily_demand_truth"], key=key) == expected,
        "Private daily demand formula differs from its versioned policy.",
    )
    latent: Counter[tuple] = Counter()
    observed: Counter[tuple] = Counter()
    lost: Counter[tuple] = Counter()
    for arrival in tables["inventory_demand_arrivals"]:
        k = (
            utc_timestamp(arrival["occurred_at"]).date().isoformat(),
            arrival["product_id"],
            arrival["selling_location_id"],
            arrival["channel"],
        )
        latent[k] += arrival["latent_quantity"]
    for outcome in tables["inventory_demand_outcomes"]:
        k = (
            utc_timestamp(outcome["occurred_at"]).date().isoformat(),
            outcome["product_id"],
            outcome["selling_location_id"],
            outcome["channel"],
        )
        observed[k] += outcome["observed_quantity"]
        lost[k] += outcome["lost_sales_quantity"]
    expected_keys = {key(r) for r in expected}
    require(latent.keys() <= expected_keys, "Demand arrival outside active/open daily grid.")
    require(
        all(
            latent[key(r)] == int(r["latent_units"]) == observed[key(r)] + lost[key(r)]
            for r in expected
        ),
        "Daily latent units != observed + lost inventory units.",
    )
    return len(expected)


def commerce_linkage(tables: dict) -> int:
    sales = {r["id"]: r for r in tables["sales"]}
    executed = {r["sale_id"]: r for r in tables["inventory_sales"]}
    refs = {r["sale_id"]: r for r in tables["sale_price_references"]}
    orders = {r["order_reference"]: r for r in tables["orders"]}
    require(
        len(sales) == len(tables["sales"]) == len(executed) and sales.keys() == executed.keys(),
        "Commerce sales and inventory issues require identical unique sale IDs.",
    )
    index = DimensionIndex(tables)
    for identifier, sale in sales.items():
        actual, ref = executed[identifier], refs[identifier]
        route = index.route(
            ref["selling_location_id"],
            ref["channel"],
            ref["business_date"],
            orders[sale["order_reference"]]["ordered_at"],
        )
        require(
            route is not None and route["stock_location_id"] == actual["stock_location_id"],
            "Commerce issue uses an unavailable/wrong historical physical route.",
        )
        require(
            actual["product_id"] == sale["product_id"] == ref["product_id"]
            and actual["selling_location_id"] == ref["selling_location_id"]
            and actual["channel"] == sale["channel"] == ref["channel"]
            and actual["quantity"] == int(sale["quantity"])
            and int(sale["observed_sales"]) == int(sale["quantity"])
            and actual["currency"] == sale["currency"]
            and Decimal(actual["unit_price"]) == Decimal(sale["unit_price"])
            and Decimal(actual["gross_revenue"]) == Decimal(sale["total_amount"])
            and utc_timestamp(actual["sold_at"]) == utc_timestamp(sale["sold_at"])
            and utc_timestamp(actual["ingested_at"]) == utc_timestamp(sale["ingested_at"]),
            "Persisted commerce and inventory sale facts differ.",
        )
    require(
        {r["id"] for r in tables["inventory_products"]}
        == {r["id"] for r in tables["product_catalog"]},
        "Inventory/catalog product coverage differs.",
    )
    require(
        {r["id"] for r in tables["inventory_stock_locations"]}
        == {r["id"] for r in tables["stock_locations"]},
        "Inventory/physical dimension coverage differs.",
    )
    return len(sales)


def configuration_linkage(tables: dict, config: SourceInventoryConfig) -> int:
    opening = [r for r in tables["inventory_ledger"] if r["movement_type"] == "opening_stock"]
    require(
        all(r["quantity_delta"] == config.stock.opening_quantity for r in opening),
        "Opening movements differ from the bound source configuration.",
    )
    for rule in tables["inventory_reorder_rules"]:
        require(
            all(
                rule[k] == getattr(config.stock, k)
                for k in (
                    "reorder_point",
                    "safety_stock",
                    "history_window_days",
                    "review_cadence_days",
                    "minimum_order_quantity",
                )
            ),
            "Reorder facts differ from the bound source configuration.",
        )
    require(
        all(
            r["quoted_lead_time_days"] == config.stock.quoted_lead_time_days
            for r in tables["product_suppliers"]
        ),
        "Supplier quote differs from source configuration.",
    )
    require(
        all(
            r["minimum_order_quantity"] == config.stock.minimum_order_quantity
            for r in tables["suppliers"]
        ),
        "Supplier minimum quantity differs from source configuration.",
    )
    return len(opening)


def historical_routes(tables: dict) -> int:
    source = {r["id"]: r for r in tables["fulfillment_routes"]}
    native = {r["id"]: r for r in tables["inventory_fulfillment_routes"]}
    versions = {r["route_id"]: r for r in tables["inventory_route_versions"]}
    require(
        source.keys() == native.keys() == versions.keys(),
        "Inventory/source route coverage differs.",
    )
    for identifier, row in source.items():
        require(
            versions[identifier]["source_version"] == int(row["version"])
            and versions[identifier]["inventory_revision"] == native[identifier]["version"]
            and all(
                row[k] == native[identifier][k]
                for k in (
                    "selling_location_id",
                    "channel",
                    "stock_location_id",
                    "effective_from",
                    "effective_to",
                    "available_at",
                )
            ),
            "Historical source route and inventory adapter version differ.",
        )
    return len(source)


def supplier_replay(tables: dict, config: SourceInventoryConfig) -> int:
    samples = {r["order_id"]: r for r in tables["inventory_supplier_samples"]}
    receipts: dict[str, list] = defaultdict(list)
    for receipt in [*tables["replenishment_receipts"], *tables["inventory_scheduled_receipt_tail"]]:
        receipts[receipt["replenishment_order_id"]].append(receipt)
    for row in tables["replenishment_orders"]:
        order = ReplenishmentOrder.model_validate(row)
        truth = SupplierTruth.model_validate(
            {
                "supplier_id": order.supplier_id,
                **config.supplier_parameters.model_dump(exclude={"data_class"}),
            }
        )
        replay = simulate_fulfillment(order, truth, config.fulfillment, first_sequence=0)
        require(
            samples[order.replenishment_order_id]
            == {
                "order_id": order.replenishment_order_id,
                "simulation_id": replay.simulation_id,
                "disrupted": replay.disrupted,
                "lead_days": replay.lead_days,
            },
            "Supplier sample differs from bound private configuration.",
        )
        actual = {r["receipt_id"]: r for r in receipts[order.replenishment_order_id]}
        require(
            actual.keys() == {r.receipt_id for r in replay.receipts},
            "Supplier receipt IDs/parts differ from replay.",
        )
        for receipt in replay.receipts:
            fields = receipt.model_dump(exclude={"sequence", "available_at"})
            observed = actual[receipt.receipt_id]
            require(
                all(observed[k] == v for k, v in fields.items())
                and utc_timestamp(observed["available_at"]) >= utc_timestamp(receipt.available_at),
                "Supplier receipt facts differ from configured realization.",
            )
    return len(samples)


def reorder_replay(tables: dict, context: TableContext, config: SourceInventoryConfig) -> int:
    operational = operational_from_tables(tables, context)
    ledger = InventoryLedger.from_payload(operational["ledger"])
    book = ReplenishmentBook.from_payload(operational["supply"])
    policy = ReorderConfig.from_payload(
        {**context.policy.model_dump(), "rules": tables["inventory_reorder_rules"]}
    )
    opening = utc_timestamp(context.opening_at)
    anchor, end = utc_timestamp(policy.review_anchor_at), utc_timestamp(context.projection.end_at)
    require(
        anchor == opening + timedelta(days=config.stock.history_window_days)
        and utc_timestamp(policy.known_at)
        == utc_timestamp(policy.available_at)
        == opening - timedelta(days=1),
        "Reorder anchor/knowledge differs from source configuration.",
    )
    origins = []
    stamp = anchor
    while stamp <= end:
        origins.append(stamp)
        stamp += timedelta(days=1)
    coverage = parse_history_coverage(
        {
            "contract_version": "inventory-history-coverage-1.0.0",
            "coverage_basis": "observed_ledger_stream",
            "coverage": tables["inventory_history_coverage"],
        }
    )
    expected_coverage = {(p, s, t.isoformat()) for p, s in ledger.scope for t in origins}
    require(
        len(coverage) == len(expected_coverage)
        and {(r.product_id, r.stock_location_id, r.covered_through_at) for r in coverage}
        == expected_coverage
        and all(
            utc_timestamp(r.covered_from_at) == opening
            and r.available_at == r.covered_through_at
            and r.source_reference == "chronological-processed-window"
            for r in coverage
        ),
        "History certificates do not cover every scheduled physical review.",
    )
    for stamp in origins:
        prior_orders = tuple(o for o in book.orders if utc_timestamp(o.ordered_at) < stamp)
        identifiers = {o.replenishment_order_id for o in prior_orders}
        # Reuse validated records and cached UTC times. A physical prefix contains
        # events already executed at review time; future facts never enter the review.
        prefix = replace(
            ledger, movements=tuple(m for m in ledger.movements if m.occurred_time <= stamp)
        )
        prior_book = replace(
            book,
            orders=prior_orders,
            plans=tuple(p for p in book.plans if p.replenishment_order_id in identifiers),
            receipts=tuple(r for r in book.receipts if utc_timestamp(r.received_at) <= stamp),
        )
        result = review_reorder(prefix, prior_book, policy, coverage, stamp.isoformat())
        expected_orders = sorted(
            (o.model_dump() for o in result.orders), key=lambda r: r["replenishment_order_id"]
        )
        actual_orders = sorted(
            (o.model_dump() for o in book.orders if utc_timestamp(o.ordered_at) == stamp),
            key=lambda r: r["replenishment_order_id"],
        )
        require(
            expected_orders == actual_orders,
            "Replenishment orders differ from known-fact policy replay.",
        )
        expected_plans = sorted(
            (p.model_dump() for p in result.plans), key=lambda r: r["plan_version_id"]
        )
        actual_ids = {r["replenishment_order_id"] for r in actual_orders}
        actual_plans = sorted(
            (
                p.model_dump()
                for p in book.plans
                if p.replenishment_order_id in actual_ids and p.version == 1
            ),
            key=lambda r: r["plan_version_id"],
        )
        require(expected_plans == actual_plans, "Initial delivery plans differ from policy replay.")
    return len(expected_coverage)


def observations(tables: dict, generation: ResolvedGenerationConfig) -> int:
    view = commerce_view(tables)

    def ordered(name: str, rows: list[dict]) -> list[dict]:
        return sorted(rows, key=lambda r: tuple(r[f] for f in grain(name)))

    require(
        tables["daily_demand_versions"]
        == ordered("daily_demand_versions", build_daily_versions(view, generation)),
        "Append-only history differs from causal availability.",
    )
    require(
        tables["daily_return_cohorts"]
        == ordered("daily_return_cohorts", source_return_cohorts(view, generation)),
        "Financial cohorts include unavailable facts or incorrect maturity.",
    )
    require(
        tables["returns"]
        == ordered(
            "returns", source_legacy_returns(view, return_boundaries(generation)["history"])
        ),
        "Legacy financial projection includes unknown/tail purchases.",
    )
    return len(tables["daily_demand_versions"])


def inventory_completeness(tables: dict) -> int:
    require(
        all(r["status"] == "known" for r in tables["inventory_daily_snapshots"]),
        "Inventory source contains unavailable origin snapshots.",
    )
    return len(tables["inventory_daily_snapshots"])


def build_source_report(
    tables: dict,
    context: TableContext,
    generation: ResolvedGenerationConfig,
    inventory_config: SourceInventoryConfig,
    *,
    anomaly_plan: AnomalyPlan | None = None,
) -> dict:
    view = commerce_view(tables)
    checks = []
    for builder in (
        build_dimensions_report,
        build_pricing_report,
        build_demand_report,
        build_return_report,
    ):
        report = (
            builder(view, generation, anomaly_plan=anomaly_plan)
            if builder is build_demand_report
            else builder(view, generation)
        )
        for check in report["checks"]:
            # Uncapped demand and legacy full-cohort assumptions are replaced by explicit
            # inventory conservation and causal finance gates below; all other gates remain.
            if check["check_id"] not in {"daily_demand_budget", "return_snapshot_reconciliation"}:
                checks.append({**check, "evidence": "source_report.json"})
    operations = {
        "inventory_graph_and_projection": lambda: sum(
            reconcile_tables({n: tables[n] for n in TABLES}, context).values()
        ),
        "commerce_inventory_parity": lambda: commerce_linkage(tables),
        "inventory_configuration_binding": lambda: configuration_linkage(tables, inventory_config),
        "historical_fulfillment_adapter": lambda: historical_routes(tables),
        "private_supplier_realization": lambda: supplier_replay(tables, inventory_config),
        "known_fact_reorder_policy": lambda: reorder_replay(tables, context, inventory_config),
        "inventory_daily_demand_conservation": lambda: demand_budget(
            tables, generation, anomaly_plan
        ),
        "causal_observation_and_finance_history": lambda: observations(tables, generation),
        "private_simulation_parameters": lambda: validate_simulation(tables),
        "forecast_feature_projection": lambda: len(transform(project_facts(view))),
        "inventory_known_completeness": lambda: inventory_completeness(tables),
    }
    for name, operation in operations.items():
        try:
            count, status, description = (
                stage("validation/" + name)(operation)(),
                "passed",
                "All required records reconcile.",
            )
        except (ValueError, KeyError, TypeError, ArithmeticError) as error:
            count, status, description = 0, "failed", str(error)
        checks.append(
            {
                "check_id": name,
                "policy_version": SOURCE_POLICY,
                "severity": "hard",
                "status": status,
                "sample_size": count,
                "description": description,
                "evidence": "source_report.json",
            }
        )
    failures = {r["check_id"] for r in checks if r["status"] != "passed"}
    passed = not failures
    status = (
        "passed"
        if passed
        else "not_ready"
        if failures <= {"daily_source_completeness", "inventory_known_completeness"}
        else "failed"
    )
    return {
        "policy_version": SOURCE_POLICY,
        "status": status,
        "checks": checks,
        "facts_ready": passed,
        "source_ready": False,
        "inventory_ready": False,
        "model_ready": False,
        "label_qualification": "not_evaluated",
        "publication_status": "awaiting_ai03_handoff",
    }


def report_markdown(report: dict) -> str:
    lines = [
        "# Inventory source acceptance",
        "",
        f"Policy: {report['policy_version']}. Status: {report['status']}.",
        "",
        "| Check | Status | Sample | Description |",
        "|---|---|---:|---|",
    ]
    lines.extend(
        f"| {r['check_id']} | {r['status']} | {r['sample_size']} | {r['description']} |"
        for r in report["checks"]
    )
    return "\n".join(
        [
            *lines,
            "",
            "Source/inventory/model readiness remains false until the AI03 handoff and lifecycle qualification.",
            "",
        ]
    )


def build_realism(tables: dict, generation: ResolvedGenerationConfig) -> dict:
    report = build_source_realism(generation.profile, generation.seed, tables)
    balances = tables["inventory_physical_daily_balances"]
    arrivals = sum(r["latent_quantity"] for r in tables["inventory_demand_arrivals"])
    lost = sum(r["lost_sales_quantity"] for r in tables["inventory_demand_outcomes"])
    report["policy_version"] = "inventory-observed-sales-realism-1.0.0"
    report["metrics"] = [r for r in report["metrics"] if r["metric_id"] != "stockout_rate"]
    report["inventory_diagnostics"] = {
        "physical_zero_balance_share": sum(r["available_qty"] == 0 for r in balances)
        / len(balances),
        "physical_scope_days": len(balances),
        "latent_units": arrivals,
        "lost_units": lost,
        "lost_unit_share": lost / arrivals if arrivals else None,
        "stockout_episodes": len(tables["stockout_episodes"]),
        "label_qualification": "not_evaluated",
        "denominator": "All physical inventory positions/days, including inactive assortment; not an AI08 sample.",
    }
    return report
