from __future__ import annotations

import copy
import json
import random
import subprocess
import sys
from pathlib import Path

import pytest

from data.generator.common import deterministic_uuid
from data.generator.identity import json_sha256
from data.inventory.fulfillment_routes import resolve_route
from data.inventory.ledger import InventoryLedger
from data.inventory.replenishment import ReplenishmentBook
from data.inventory.run_simulation import run
from data.inventory.simulation_contract import (
    ChronologicalScenario,
    commerce_output_schema,
    fulfillment_routes_schema,
    scenario_schema,
)
from data.inventory.simulation_reconciliation import reconcile_simulation, verify_demand_outcomes
from data.inventory.simulator import ChronologicalSimulator

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).parent / "fixtures"
NAMES = {
    "ledger": "chronological-opening-v1.json",
    "supply": "reorder-supply-v1.json",
    "scenario": "chronological-scenario-v1.json",
    "policy": "reorder-config-v1.json",
    "fulfillment": "supplier-fulfillment-config-v1.json",
    "truth": "chronological-supplier-truth-v1.json",
}


@pytest.fixture
def inputs():
    return {k: json.loads((FIXTURES / v).read_text()) for k, v in NAMES.items()}


def simulate(inputs):
    result = ChronologicalSimulator(
        inputs["ledger"],
        inputs["supply"],
        inputs["scenario"],
        inputs["policy"],
        inputs["fulfillment"],
        inputs["truth"],
    ).execute()
    reconcile_simulation(result["operational"])
    verify_demand_outcomes(
        result["operational"],
        result["simulation_truth"],
        tuple(ChronologicalScenario.from_payload(inputs["scenario"]).demand_arrivals),
    )
    return result


def no_actions(inputs):
    inputs["scenario"]["return_events"] = []
    inputs["scenario"]["inventory_actions"] = []


def correction(inputs, available="2026-07-02T00:00:00Z"):
    route = copy.deepcopy(inputs["scenario"]["fulfillment_routes"][0])
    route.update(
        id=deterministic_uuid("route", "correction"),
        version=2,
        stock_location_id=inputs["ledger"]["stock_locations"][1]["id"],
        available_at=available,
    )
    inputs["scenario"]["fulfillment_routes"].append(route)
    return route


def test_shared_stock_is_consumed_once_and_conserved(inputs):
    result = simulate(inputs)
    op, truth = result["operational"], result["simulation_truth"]
    assert [s["quantity"] for s in op["sales"]] == [6, 2, 4, 10, 3]
    assert [s["gross_revenue"] for s in op["sales"]] == ["15.00", "5.00", "10.00", "25.00", "7.50"]
    assert verify_demand_outcomes(op, truth) == {
        "arrivals": 6,
        "latent_quantity": 29,
        "observed_quantity": 25,
        "lost_sales_quantity": 4,
    }
    counts = reconcile_simulation(op)
    assert counts["sales"] == counts["sale_issues"] == 5
    assert counts["returns"] == 2 and counts["accepted_restocks"] == 1
    assert sum(r["received_quantity"] for r in op["supply"]["replenishment_receipts"]) == 45
    assert [r["on_hand"] for r in result["final_physical_positions"]] == [24, 6]
    assert sum(r["on_hand"] for r in result["final_physical_positions"]) == 8 + 45 + 2 - 25 - 1 + 1
    assert op["ledger"]["reservation_policy"] == "none"
    assert not any(s["quantity"] == 0 for s in op["sales"])
    assert len({s["order_id"] for s in op["sales"]}) == len(op["sales"])


def test_sequence_controls_competing_channels(inputs):
    baseline = simulate(inputs)
    no_actions(inputs)
    a, b = inputs["scenario"]["demand_arrivals"][:2]
    a["sequence"], b["sequence"] = b["sequence"], a["sequence"]
    changed = simulate(inputs)
    assert [s["channel"] for s in changed["operational"]["sales"][:2]] == ["online", "store"]
    assert [s["quantity"] for s in changed["operational"]["sales"][:2]] == [6, 2]
    assert sum(s["quantity"] for s in baseline["operational"]["sales"][:2]) == 8


def test_quality_decision_and_original_price_determine_return(inputs):
    result = simulate(inputs)
    rows = result["operational"]["returns"]
    assert [r["refund_amount"] for r in rows] == ["5.00", "2.50"]
    restocks = [
        m
        for m in result["operational"]["ledger"]["movements"]
        if m["movement_type"] == "return_to_stock"
    ]
    assert len(restocks) == 1 and restocks[0]["source_reference"] == rows[0]["return_id"]
    assert restocks[0]["quantity_delta"] == 2
    inputs["scenario"]["demand_arrivals"][2]["unit_price"] = "9.99"
    assert simulate(inputs)["operational"]["returns"] == rows


def test_route_change_does_not_move_return_from_original_warehouse(inputs):
    old = inputs["scenario"]["fulfillment_routes"][0]["stock_location_id"]
    new = correction(inputs)
    result = simulate(inputs)
    assert result["operational"]["sales"][0]["stock_location_id"] == old
    later = next(
        s
        for s in result["operational"]["sales"]
        if s["source_reference"] == inputs["scenario"]["demand_arrivals"][2]["demand_id"]
    )
    assert later["stock_location_id"] == new["stock_location_id"]
    assert all(r["stock_location_id"] == old for r in result["operational"]["returns"])


@pytest.mark.parametrize(
    "available,expected_version",
    [
        ("2026-07-01T10:00:00.000001Z", 1),
        ("2026-07-01T10:00:00Z", 2),
        ("2026-07-01T09:59:59Z", 2),
    ],
)
def test_route_availability_is_exact(inputs, available, expected_version):
    correction(inputs, available)
    scenario = ChronologicalScenario.from_payload(inputs["scenario"])
    d = scenario.demand_arrivals[0]
    assert (
        resolve_route(
            tuple(scenario.fulfillment_routes), d.selling_location_id, d.channel, d.occurred_at
        ).version
        == expected_version
    )


def test_half_open_route_period_and_no_other_warehouse_fallback(inputs):
    route = inputs["scenario"]["fulfillment_routes"][0]
    route["effective_to"] = "2026-07-05"
    with pytest.raises(ValueError, match="Missing known fulfillment"):
        simulate(inputs)
    route["effective_to"] = "2026-08-01"
    route["available_at"] = "2026-07-01T10:00:00.000001Z"
    with pytest.raises(ValueError, match="Missing known fulfillment"):
        simulate(inputs)


def test_receipt_business_time_and_availability_are_separate(inputs):
    result = simulate(inputs)
    op = result["operational"]
    near = next(s for s in op["sales"] if s["sold_at"] == "2026-07-05T00:01:00+00:00")
    assert near["available_at"] == "2026-07-05T00:03:00+00:00"
    ledger = InventoryLedger.from_payload(op["ledger"])
    before_known = ledger.balances_at("2026-07-05T00:02:00Z", known_at="2026-07-05T00:02:00Z")
    after_known = ledger.balances_at("2026-07-05T00:03:00Z", known_at="2026-07-05T00:03:00Z")
    assert [r["on_hand"] for r in before_known] == [1, 1]
    assert [r["on_hand"] for r in after_known] == [11, 9]
    at_due = next(r for r in op["reviews"] if r["origin"] == "2026-07-05T00:00:00+00:00")
    assert [d["on_hand"] for d in at_due["decisions"]] == [1, 1]
    assert [d["on_order"] for d in at_due["decisions"]] == [14, 8]


def test_review_sees_transfer_in_transit_without_future_destination_stock(inputs):
    result = simulate(inputs)
    ledger = InventoryLedger.from_payload(result["operational"]["ledger"])
    transit = ledger.transit_at("2026-07-03T00:00:00Z", known_at="2026-07-03T00:00:00Z")
    assert len(transit) == 1 and transit[0]["quantity"] == 1
    first = result["operational"]["reviews"][0]
    assert [d["on_hand"] for d in first["decisions"]] == [1, 0]
    assert ledger.transit_at("2026-07-04T12:00:00Z", known_at="2026-07-04T12:00:00Z") == []


def test_poor_supply_delays_and_partially_receives_actual_units(inputs):
    normal = simulate(inputs)
    for row in inputs["truth"]["suppliers"]:
        row["reliability"] = "0"
    poor = simulate(inputs)
    assert poor["operational"]["reviews"][:2] == normal["operational"]["reviews"][:2]
    assert (
        verify_demand_outcomes(poor["operational"], poor["simulation_truth"])["lost_sales_quantity"]
        == 19
    )
    assert (
        verify_demand_outcomes(poor["operational"], poor["simulation_truth"])["observed_quantity"]
        == 10
    )
    receipts = poor["operational"]["supply"]["replenishment_receipts"]
    assert len(receipts) == 4
    assert sorted(r["received_quantity"] for r in receipts) == [4, 4, 7, 7]
    assert all(
        s["disrupted"] and s["lead_days"] == 4 for s in poor["simulation_truth"]["supplier_samples"]
    )
    book = ReplenishmentBook.from_payload(poor["operational"]["supply"])
    at_partial = book.orders_at("2026-07-07T00:03:00Z")
    assert sorted(r["outstanding_quantity"] for r in at_partial) == [4, 7]


def test_end_tail_is_not_received_or_added_to_stock(inputs):
    inputs["scenario"]["settings"]["end_at"] = "2026-07-05T00:00:00Z"
    inputs["scenario"]["demand_arrivals"] = inputs["scenario"]["demand_arrivals"][:2]
    result = simulate(inputs)
    assert result["operational"]["supply"]["replenishment_receipts"] == []
    assert len(result["simulation_truth"]["scheduled_receipt_tail"]) == 2
    assert [r["on_hand"] for r in result["final_physical_positions"]] == [1, 1]


def test_generated_receipt_sequence_and_review_tie_are_explicit(inputs):
    inputs["scenario"]["demand_arrivals"][2]["occurred_at"] = "2026-07-05T00:00:00Z"
    result = simulate(inputs)
    arrival = result["simulation_truth"]["demand_outcomes"][2]
    assert arrival["stock_before"] == arrival["observed_quantity"] == 1
    at_same_time = [
        m
        for m in result["operational"]["ledger"]["movements"]
        if m["occurred_at"] == "2026-07-05T00:00:00+00:00"
    ]
    assert [m["movement_type"] for m in at_same_time] == [
        "sale",
        "replenishment_received",
        "replenishment_received",
    ]
    assert [m["sequence"] for m in at_same_time] == [12, 13, 14]


def test_return_same_time_requires_sale_to_happen_first(inputs):
    event = inputs["scenario"]["return_events"][0]
    event.update(
        returned_at="2026-07-01T10:00:00Z",
        ingested_at="2026-07-01T10:00:00Z",
        available_at="2026-07-01T10:00:00Z",
        sequence=9,
    )
    with pytest.raises(ValueError, match="preceding fulfilled sale"):
        simulate(inputs)
    event["sequence"] = 12
    result = simulate(inputs)
    row = result["operational"]["returns"][0]
    assert row["ingested_at"] == "2026-07-01T10:00:30+00:00"
    assert row["available_at"] == "2026-07-01T10:01:00+00:00"


def test_future_route_correction_cannot_change_earlier_execution(inputs):
    original = simulate(inputs)
    correction(inputs, "2026-07-08T00:00:00Z")
    changed = simulate(inputs)
    assert changed["operational"]["sales"] == original["operational"]["sales"]
    assert changed["operational"]["reviews"] == original["operational"]["reviews"]


@pytest.mark.parametrize(
    "mutation", ["extra_opening", "missing_rule", "wrong_master_code", "existing_order"]
)
def test_initial_foundation_cannot_be_silently_replaced(inputs, mutation):
    if mutation == "extra_opening":
        inputs["ledger"]["movements"].append(copy.deepcopy(inputs["ledger"]["movements"][0]))
    elif mutation == "missing_rule":
        inputs["policy"]["rules"].pop()
    elif mutation == "wrong_master_code":
        inputs["supply"]["stock_locations"][0]["location_code"] = "DIFFERENT"
    else:
        result = simulate(inputs)
        inputs["supply"]["replenishment_orders"] = result["operational"]["supply"][
            "replenishment_orders"
        ]
        inputs["supply"]["delivery_plan_versions"] = result["operational"]["supply"][
            "delivery_plan_versions"
        ]
    with pytest.raises(ValueError):
        simulate(inputs)


def test_no_demand_zero_floor_does_not_invent_sales_or_orders(inputs):
    no_actions(inputs)
    for demand in inputs["scenario"]["demand_arrivals"]:
        demand["latent_quantity"] = 0
    for rule in inputs["policy"]["rules"]:
        rule.update(reorder_point=0, safety_stock=0)
    result = simulate(inputs)
    assert result["operational"]["sales"] == []
    assert result["operational"]["supply"]["replenishment_orders"] == []
    assert all(r["reason"] == "no_demand" for r in result["simulation_truth"]["demand_outcomes"])
    assert [r["on_hand"] for r in result["final_physical_positions"]] == [8, 0]


def test_zero_stock_is_a_supply_constraint_instead_of_zero_demand(inputs):
    no_actions(inputs)
    for opening in inputs["ledger"]["movements"]:
        opening["quantity_delta"] = 0
    result = simulate(inputs)
    first = result["simulation_truth"]["demand_outcomes"][0]
    assert first["observed_quantity"] == 0 and first["lost_sales_quantity"] == 6
    assert first["reason"] == "inventory_constraint"
    assert len(result["operational"]["supply"]["replenishment_orders"]) > 0


def test_future_demand_cannot_change_prior_decisions(inputs):
    baseline = simulate(inputs)
    inputs["scenario"]["demand_arrivals"][-1]["latent_quantity"] = 100
    changed = simulate(inputs)
    cutoff = "2026-07-07T00:00:00+00:00"
    assert [r for r in changed["operational"]["reviews"] if r["origin"] <= cutoff] == [
        r for r in baseline["operational"]["reviews"] if r["origin"] <= cutoff
    ]
    assert changed["operational"]["sales"][:5] == baseline["operational"]["sales"]


def test_delayed_sale_is_not_observed_by_earlier_review(inputs):
    no_actions(inputs)
    inputs["scenario"]["settings"]["sale_availability_delay_seconds"] = 4 * 86400
    result = simulate(inputs)
    first = result["operational"]["reviews"][0]
    assert [d["on_hand"] for d in first["decisions"]] == [8, 0]
    assert all(d["observed_sales_quantity"] == 0 for d in first["decisions"])
    assert result["operational"]["sales"][0]["quantity"] == 6


def test_input_order_and_equivalent_utc_encoding_do_not_change_logical_output(inputs):
    baseline = simulate(inputs)
    rng = random.Random(137)
    for payload in inputs.values():
        for value in payload.values():
            if isinstance(value, list):
                rng.shuffle(value)

    def normalize(value):
        if isinstance(value, dict):
            return {k: normalize(v) for k, v in value.items()}
        if isinstance(value, list):
            return [normalize(v) for v in value]
        if isinstance(value, str) and "T" in value and value.endswith("Z"):
            return value[:-1] + "+00:00"
        return value

    changed = simulate(normalize(inputs))
    assert json_sha256(changed) == json_sha256(baseline)


@pytest.mark.parametrize(
    "field,value",
    [
        ("latent_quantity", True),
        ("latent_quantity", "6"),
        ("latent_quantity", -1),
        ("sequence", True),
        ("sequence", -1),
        ("currency", "USD"),
        ("channel", "other"),
        ("unit_price", "2.5"),
        ("unit_price", "0.00"),
        ("product_id", deterministic_uuid("invalid", "product")),
        ("selling_location_id", deterministic_uuid("invalid", "selling")),
        ("occurred_at", "2026-07-10T00:00:00Z"),
        ("occurred_at", "2026-07-01T12:00:00+02:00"),
    ],
)
def test_invalid_arrivals_fail_without_coercion(inputs, field, value):
    inputs["scenario"]["demand_arrivals"][0][field] = value
    with pytest.raises(ValueError):
        simulate(inputs)


@pytest.mark.parametrize(
    "field,value",
    [
        ("stock_location_id", deterministic_uuid("invalid", "stock")),
        ("selling_location_id", deterministic_uuid("invalid", "selling")),
        ("effective_from", "2026-08-01"),
        ("available_at", "2026-02-30T00:00:00Z"),
        ("version", 2),
    ],
)
def test_invalid_routes_fail(inputs, field, value):
    inputs["scenario"]["fulfillment_routes"][0][field] = value
    with pytest.raises(ValueError):
        simulate(inputs)


def test_overlapping_periods_and_backdated_corrections_are_rejected(inputs):
    route = correction(inputs)
    route["effective_from"] = "2026-07-02"
    with pytest.raises(ValueError, match="overlapping"):
        simulate(inputs)
    route["effective_from"] = "2026-07-01"
    route["available_at"] = "2026-05-31T00:00:00Z"
    with pytest.raises(ValueError, match="backdated"):
        simulate(inputs)


@pytest.mark.parametrize(
    "table",
    [
        "selling_locations",
        "fulfillment_routes",
        "demand_arrivals",
        "return_events",
        "inventory_actions",
    ],
)
def test_duplicate_primary_keys_fail(inputs, table):
    inputs["scenario"][table].append(copy.deepcopy(inputs["scenario"][table][0]))
    with pytest.raises(ValueError, match="Duplicate"):
        simulate(inputs)


def test_duplicate_timestamp_sequence_fails_even_for_zero_demand(inputs):
    a, b = inputs["scenario"]["demand_arrivals"][:2]
    b.update(sequence=a["sequence"], latent_quantity=0)
    with pytest.raises(ValueError, match="timestamp/sequence"):
        simulate(inputs)


@pytest.mark.parametrize(
    "field,value",
    [
        ("returned_quantity", 7),
        ("returned_quantity", True),
        ("returned_quantity", 0),
        ("demand_id", deterministic_uuid("invalid", "demand")),
        ("stock_location_id", "7db7acb8-6e46-5a3e-b39a-faaa449238a3"),
        ("unit_of_measure", "kg"),
        ("quality_status", "pending"),
        ("returned_at", "2026-07-01T09:00:00Z"),
        ("ingested_at", "2026-07-02T08:59:59Z"),
    ],
)
def test_ineligible_returns_fail(inputs, field, value):
    inputs["scenario"]["return_events"][0][field] = value
    with pytest.raises(ValueError):
        simulate(inputs)


def test_all_return_dispositions_count_against_fulfilled_quantity(inputs):
    inputs["scenario"]["return_events"][0]["returned_quantity"] = 6
    with pytest.raises(ValueError, match="Cumulative"):
        simulate(inputs)


def test_unfulfilled_latent_request_cannot_be_returned(inputs):
    inputs["ledger"]["movements"][0]["quantity_delta"] = 0
    with pytest.raises(ValueError, match="preceding fulfilled sale"):
        simulate(inputs)


@pytest.mark.parametrize(
    "field,value",
    [
        ("quantity_delta", 1),
        ("quantity_delta", -100),
        ("unit_of_measure", "kg"),
        ("source_process", "sale"),
        ("movement_type", "sale"),
    ],
)
def test_illegal_or_negative_physical_actions_fail(inputs, field, value):
    inputs["scenario"]["inventory_actions"][0][field] = value
    with pytest.raises(ValueError):
        simulate(inputs)


def test_transfer_pair_is_mandatory(inputs):
    del inputs["scenario"]["inventory_actions"][2]
    with pytest.raises(ValueError, match="transfer"):
        simulate(inputs)


def test_warmup_and_policy_truth_separation_are_required(inputs):
    inputs["policy"]["review_anchor_at"] = "2026-07-02T00:00:00Z"
    with pytest.raises(ValueError, match="warmup"):
        simulate(inputs)
    inputs["policy"]["review_anchor_at"] = "2026-07-03T00:00:00Z"
    inputs["policy"]["reliability"] = "1"
    with pytest.raises(ValueError):
        simulate(inputs)


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_sale",
        "missing_issue",
        "wrong_issue",
        "wrong_route",
        "wrong_revenue",
        "missing_restock",
        "rejected_restock",
        "wrong_refund",
        "wrong_return_currency",
        "too_many_returns",
        "missing_master",
    ],
)
def test_independent_reconciliation_rejects_corrupted_results(inputs, mutation):
    op = simulate(inputs)["operational"]
    movements = op["ledger"]["movements"]
    sale_issue = next(m for m in movements if m["movement_type"] == "sale")
    restock = next(m for m in movements if m["movement_type"] == "return_to_stock")
    if mutation == "missing_sale":
        op["sales"].pop()
    elif mutation == "missing_issue":
        movements.remove(sale_issue)
    elif mutation == "wrong_issue":
        sale_issue["source_reference"] = deterministic_uuid("invalid", "sale")
    elif mutation == "wrong_route":
        op["sales"][0]["fulfillment_route_id"] = op["fulfillment_routes"][0]["id"]
        if (
            op["sales"][0]["fulfillment_route_id"]
            == inputs["scenario"]["fulfillment_routes"][0]["id"]
        ):
            op["sales"][0]["fulfillment_route_id"] = deterministic_uuid("invalid", "route")
    elif mutation == "wrong_revenue":
        op["sales"][0]["gross_revenue"] = "0.01"
    elif mutation == "missing_restock":
        movements.remove(restock)
    elif mutation == "rejected_restock":
        op["returns"][0]["quality_status"] = "rejected"
    elif mutation == "wrong_refund":
        op["returns"][1]["refund_amount"] = "9.99"
    elif mutation == "wrong_return_currency":
        op["returns"][1]["currency"] = "EUR"
    elif mutation == "too_many_returns":
        op["returns"][1]["quantity"] = 6
    else:
        op["selling_locations"] = []
    with pytest.raises(ValueError):
        reconcile_simulation(op)


@pytest.mark.parametrize(
    "field,value",
    [
        ("lost_sales_quantity", 0),
        ("observed_quantity", 6),
        ("stock_before", 6),
        ("reason", "fulfilled"),
        ("latent_quantity", True),
        ("stock_location_id", "7db7acb8-6e46-5a3e-b39a-faaa449238a3"),
    ],
)
def test_private_truth_is_checked_against_actual_stock(inputs, field, value):
    result = simulate(inputs)
    result["simulation_truth"]["demand_outcomes"][1][field] = value
    with pytest.raises(ValueError):
        verify_demand_outcomes(result["operational"], result["simulation_truth"])


def test_zero_sale_arrivals_cannot_be_dropped_from_truth(inputs):
    result = simulate(inputs)
    result["simulation_truth"]["demand_outcomes"].pop()
    with pytest.raises(ValueError, match="coverage"):
        verify_demand_outcomes(
            result["operational"],
            result["simulation_truth"],
            tuple(ChronologicalScenario.from_payload(inputs["scenario"]).demand_arrivals),
        )


@pytest.mark.parametrize(
    "name,factory",
    [
        ("chronological_scenario", scenario_schema),
        ("inventory_fulfillment_routes", fulfillment_routes_schema),
        ("inventory_commerce_output", commerce_output_schema),
    ],
)
def test_published_schemas_match_strict_runtime(name, factory):
    assert (
        json.loads((ROOT / "data/contracts" / (name + ".v1.schema.json")).read_text()) == factory()
    )


def test_real_cli_and_future_policy_readiness(inputs, tmp_path):
    options = {
        "ledger": "ledger",
        "supply": "supply",
        "scenario": "scenario",
        "policy": "policy",
        "fulfillment": "fulfillment-config",
        "truth": "supplier-truth",
    }
    command = [sys.executable, "-m", "data.inventory.run_simulation"]
    paths = {}
    for k, payload in inputs.items():
        paths[k] = tmp_path / (k + ".json")
        paths[k].write_text(json.dumps(payload))
        command.extend(["--" + options[k], str(paths[k])])
    output = tmp_path / "report.json"
    command.extend(["--output", str(output)])
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=30)
    assert completed.returncode == 0, completed.stderr
    report = json.loads(output.read_text())
    assert report["status"] == "passed" and report["inventory_ready"] is False
    assert report["code_provenance"]["code_sha256"]
    assert report["seconds"] > 0 and report["peak_rss_mib"] > 0
    assert report["demand_reconciliation"]["lost_sales_quantity"] == 4
    inputs["policy"]["available_at"] = "2026-07-11T00:00:00Z"
    paths["policy"].write_text(json.dumps(inputs["policy"]))
    report = run(
        paths["scenario"],
        paths["ledger"],
        paths["supply"],
        paths["policy"],
        paths["fulfillment"],
        paths["truth"],
    )
    assert report["status"] == "not_ready" and report["inventory_ready"] is False
    paths["scenario"].write_text("{}")
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=30)
    assert completed.returncode == 1
    assert json.loads(output.read_text())["status"] == "failed"
