from __future__ import annotations

import copy
import json
import random
import subprocess
import sys
from pathlib import Path

import pytest

from data.generator.common import deterministic_uuid
from data.inventory.ledger import InventoryLedger
from data.inventory.reorder import review_reorder
from data.inventory.reorder_contract import (
    ReorderConfig,
    history_coverage_schema,
    parse_history_coverage,
    reorder_schema,
)
from data.inventory.replenishment import ReplenishmentBook
from data.inventory.run_reorder import run
from data.inventory.supplier_fulfillment import (
    FulfillmentConfig,
    fulfillment_schema,
    simulate_fulfillment,
)
from data.inventory.supplier_truth import validate_supplier_truth

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).parent / "fixtures"
ORIGIN = "2026-07-03T00:00:00Z"
NAMES = {
    "supply": "reorder-supply-v1.json",
    "ledger": "reorder-ledger-v1.json",
    "config": "reorder-config-v1.json",
    "coverage": "inventory-history-coverage-v1.json",
    "fulfillment": "supplier-fulfillment-config-v1.json",
    "truth": "supplier-simulation-truth-v1.json",
}


@pytest.fixture
def inputs():
    return {key: json.loads((FIXTURES / name).read_text()) for key, name in NAMES.items()}


def review(inputs, origin=ORIGIN):
    return review_reorder(
        InventoryLedger.from_payload(inputs["ledger"]),
        ReplenishmentBook.from_payload(inputs["supply"]),
        ReorderConfig.from_payload(inputs["config"]),
        parse_history_coverage(inputs["coverage"]),
        origin,
    )


def with_orders(inputs, result):
    candidate = copy.deepcopy(inputs)
    candidate["supply"]["replenishment_orders"].extend(o.model_dump() for o in result.orders)
    candidate["supply"]["delivery_plan_versions"].extend(p.model_dump() for p in result.plans)
    return candidate


def execute(inputs, tmp_path, origin=ORIGIN):
    paths = {}
    for key, payload in inputs.items():
        paths[key] = tmp_path / (key + ".json")
        paths[key].write_text(json.dumps(payload))
    return run(
        paths["supply"],
        paths["ledger"],
        paths["config"],
        paths["coverage"],
        paths["fulfillment"],
        paths["truth"],
        origin,
    )


def test_reorder_uses_stock_position_known_sales_and_explicit_floor(inputs):
    result = review(inputs)
    assert [d.status for d in result.decisions] == ["ordered", "ordered"]
    assert [d.on_hand for d in result.decisions] == [4, 0]
    assert [d.observed_sales_quantity for d in result.decisions] == [4, 0]
    assert [d.target_quantity for d in result.decisions] == [9, 8]
    assert [o.ordered_quantity for o in result.orders] == [5, 8]
    assert all(o.expected_delivery_at == "2026-07-05T00:00:00+00:00" for o in result.orders)
    assert all(o.ordered_at == o.ingested_at == o.available_at for o in result.orders)
    candidate = with_orders(inputs, result)
    book = ReplenishmentBook.from_payload(candidate["supply"])
    book.reconcile_ledger(InventoryLedger.from_payload(candidate["ledger"]))


def test_same_review_is_idempotent_and_existing_orders_are_counted(inputs):
    initial = review(inputs)
    repeated = review(with_orders(inputs, initial))
    assert repeated.orders == repeated.plans == ()
    assert [d.status for d in repeated.decisions] == ["already_ordered", "already_ordered"]
    assert [d.on_order for d in repeated.decisions] == [5, 8]
    later = with_orders(inputs, initial)
    for c in later["coverage"]["coverage"]:
        c["covered_through_at"] = c["available_at"] = "2026-07-04T00:00:00Z"
    next_day = review(later, "2026-07-04T00:00:00Z")
    assert [d.stock_position for d in next_day.decisions] == [9, 8]
    assert [d.status for d in next_day.decisions] == ["no_order", "no_order"]


def test_partial_receipt_preserves_stock_position_and_prevents_duplicate_order(inputs):
    initial = review(inputs)
    candidate = with_orders(inputs, initial)
    settings = FulfillmentConfig.from_payload(candidate["fulfillment"])
    truth = validate_supplier_truth(
        candidate["truth"], {s["supplier_id"] for s in candidate["supply"]["suppliers"]}
    )
    supplier = next(t for t in truth if t.supplier_id == initial.orders[0].supplier_id)
    supplier = supplier.model_copy(update={"reliability": "0", "lead_time_std_days": "0"})
    receipts = simulate_fulfillment(
        initial.orders[0], supplier, settings, first_sequence=3
    ).receipts
    candidate["supply"]["replenishment_receipts"] = [receipts[0].model_dump()]
    book = ReplenishmentBook.from_payload(candidate["supply"])
    candidate["ledger"]["movements"].extend(m.record() for m in book.receipt_movements())
    cutoff = "2026-07-08T00:00:00Z"
    for c in candidate["coverage"]["coverage"]:
        c["covered_through_at"] = c["available_at"] = cutoff
    result = review(candidate, cutoff)
    assert result.decisions[0].on_hand == 6
    assert result.decisions[0].on_order == 3
    assert result.decisions[0].stock_position == 9
    assert result.orders == ()


def test_policy_and_supplier_moq_are_both_resolved(inputs):
    inputs["config"]["rules"][0]["minimum_order_quantity"] = 12
    result = review(inputs)
    assert result.orders[0].ordered_quantity == result.decisions[0].effective_moq == 12
    inputs["supply"]["suppliers"][0]["minimum_order_quantity"] = 15
    result = review(inputs)
    assert result.orders[0].ordered_quantity == result.decisions[0].effective_moq == 15


def test_no_demand_with_zero_floor_does_not_invent_orders(inputs):
    inputs["ledger"]["movements"] = inputs["ledger"]["movements"][:2]
    for rule in inputs["config"]["rules"]:
        rule["reorder_point"] = rule["safety_stock"] = 0
    result = review(inputs)
    assert result.orders == ()
    assert all(d.status == "no_order" and d.observed_sales_quantity == 0 for d in result.decisions)


@pytest.mark.parametrize(
    "origin", ["2026-07-03T00:00:00.000001Z", "2026-07-03T12:00:00Z", "2026-07-02T00:00:00Z"]
)
def test_review_cadence_is_exact_and_does_not_floor_time(inputs, origin):
    assert all(d.status == "not_due" for d in review(inputs, origin).decisions)


def test_unknown_history_remains_missing_not_zero(inputs):
    inputs["coverage"]["coverage"] = []
    result = review(inputs)
    assert result.orders == ()
    assert all(
        d.status == "history_missing" and d.observed_sales_quantity is None
        for d in result.decisions
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("covered_from_at", "2026-07-02T00:00:00Z"),
        ("covered_through_at", "2026-07-02T23:59:59Z"),
        ("available_at", "2026-07-03T00:00:00.000001Z"),
    ],
)
def test_history_must_cover_the_entire_window_and_be_known(inputs, field, value):
    inputs["coverage"]["coverage"][0][field] = value
    result = review(inputs)
    assert result.decisions[0].status == "history_missing"


def test_missing_quote_and_future_config_have_explicit_states(inputs):
    for q in inputs["supply"]["product_suppliers"]:
        q["available_at"] = "2026-07-04T00:00:00Z"
    assert all(d.status == "supplier_missing" for d in review(inputs).decisions)
    inputs["config"]["available_at"] = "2026-07-04T00:00:00Z"
    assert all(d.status == "config_unavailable" for d in review(inputs).decisions)


def test_unknown_inventory_cannot_be_replaced_with_future_opening(inputs):
    inputs["config"]["review_anchor_at"] = "2026-06-30T00:00:00Z"
    result = review(inputs, "2026-06-30T00:00:00Z")
    assert all(d.status == "inventory_unknown" and d.on_hand is None for d in result.decisions)


def test_future_and_late_sales_cannot_change_an_earlier_review(inputs):
    baseline = review(inputs)
    sale = copy.deepcopy(inputs["ledger"]["movements"][-1])
    sale.update(
        inventory_event_id=deterministic_uuid("sale", "late"),
        sequence=3,
        quantity_delta=-1,
        occurred_at="2026-07-02T18:00:00Z",
        ingested_at="2026-07-04T00:00:00Z",
        available_at="2026-07-04T00:00:00Z",
    )
    inputs["ledger"]["movements"].append(sale)
    assert review(inputs) == baseline
    sale["occurred_at"] = sale["ingested_at"] = sale["available_at"] = "2026-07-04T12:00:00Z"
    assert review(inputs) == baseline


def test_order_not_yet_available_does_not_enter_stock_position(inputs):
    baseline = review(inputs)
    candidate = with_orders(inputs, baseline)
    for order, plan in zip(
        candidate["supply"]["replenishment_orders"], candidate["supply"]["delivery_plan_versions"]
    ):
        order["available_at"] = plan["available_at"] = "2026-07-04T00:00:00Z"
    assert review(candidate) == baseline


def test_late_receipt_cannot_rewrite_earlier_inventory_or_pending_quantity(inputs):
    initial = review(inputs)
    candidate = with_orders(inputs, initial)
    baseline = review(candidate)
    order = initial.orders[0]
    # The receipt happened before the cutoff but was ingested afterwards.
    receipt = {
        "receipt_id": deterministic_uuid("receipt", "late-known"),
        "replenishment_order_id": order.replenishment_order_id,
        "product_id": order.product_id,
        "supplier_id": order.supplier_id,
        "stock_location_id": order.stock_location_id,
        "received_quantity": 2,
        "unit_of_measure": "pcs",
        "received_at": ORIGIN,
        "ingested_at": "2026-07-04T00:00:00Z",
        "available_at": "2026-07-04T00:01:00Z",
        "sequence": 3,
        "source_reference": "goods-receipt:late",
    }
    candidate["supply"]["replenishment_receipts"].append(receipt)
    book = ReplenishmentBook.from_payload(candidate["supply"])
    candidate["ledger"]["movements"].extend(m.record() for m in book.receipt_movements())
    assert review(candidate) == baseline


def test_ceil_target_uses_integer_arithmetic_and_never_rounds_down(inputs):
    inputs["ledger"]["movements"][0]["quantity_delta"] = 5
    inputs["ledger"]["movements"][-1]["quantity_delta"] = -3
    inputs["config"]["rules"][0]["reorder_point"] = 2
    result = review(inputs)
    assert result.decisions[0].on_hand == 2
    assert result.decisions[0].observed_sales_quantity == 3
    assert result.decisions[0].target_quantity == 8
    assert result.orders[0].ordered_quantity == 6


def test_normalized_config_and_shuffled_inputs_produce_identical_decisions(inputs):
    reference = review(inputs)
    for seed in range(5):
        candidate = copy.deepcopy(inputs)
        for payload in candidate.values():
            for rows in payload.values():
                if isinstance(rows, list):
                    random.Random(seed).shuffle(rows)
        for key in ("known_at", "available_at", "review_anchor_at"):
            candidate["config"][key] = candidate["config"][key].replace("Z", "+00:00")
        assert review(candidate, ORIGIN.replace("Z", "+00:00")) == reference


@pytest.mark.parametrize(
    "change",
    [
        "extra_rule",
        "missing_rule",
        "duplicate_rule",
        "wrong_unit",
        "wrong_location",
        "unknown_coverage",
        "coverage_before_opening",
    ],
)
def test_policy_context_rejects_wrong_scope_and_catalog(inputs, change):
    if change == "extra_rule":
        rule = copy.deepcopy(inputs["config"]["rules"][0])
        rule["product_id"] = deterministic_uuid("product", "unknown")
        inputs["config"]["rules"].append(rule)
    elif change == "missing_rule":
        inputs["config"]["rules"].pop()
    elif change == "duplicate_rule":
        inputs["config"]["rules"].append(inputs["config"]["rules"][0])
    elif change == "wrong_unit":
        inputs["supply"]["products"][0]["unit_of_measure"] = "kg"
        for q in inputs["supply"]["product_suppliers"]:
            q["unit_of_measure"] = "kg"
    elif change == "wrong_location":
        inputs["supply"]["stock_locations"][0]["location_code"] = "WRONG"
    elif change == "unknown_coverage":
        inputs["coverage"]["coverage"][0]["product_id"] = deterministic_uuid("product", "unknown")
    else:
        inputs["coverage"]["coverage"][0]["covered_from_at"] = "2026-06-30T00:00:00Z"
    with pytest.raises(ValueError):
        review(inputs)


@pytest.mark.parametrize(
    "field,value",
    [
        ("reorder_point", -1),
        ("safety_stock", True),
        ("history_window_days", 0),
        ("review_cadence_days", "1"),
        ("minimum_order_quantity", 0),
        ("latent_demand", 100),
        ("reliability", "0.9"),
        ("lead_time_mean_days", "2"),
    ],
)
def test_policy_rules_reject_bad_values_and_truth(inputs, field, value):
    inputs["config"]["rules"][0][field] = value
    with pytest.raises(ValueError):
        ReorderConfig.from_payload(inputs["config"])


@pytest.mark.parametrize(
    "field,value",
    [
        ("business_timezone", "Europe/Warsaw"),
        ("available_at", "2026-06-01T00:00:00"),
        ("known_at", "2026-06-02T00:00:00Z"),
        ("review_anchor_at", "2026-02-30T00:00:00Z"),
        ("seed", 42),
        ("supplier_truth", {}),
    ],
)
def test_policy_config_is_strict_known_and_operational(inputs, field, value):
    inputs["config"][field] = value
    with pytest.raises(ValueError):
        ReorderConfig.from_payload(inputs["config"])


@pytest.mark.parametrize(
    "change", ["duplicate", "invalid_time", "reversed", "before_availability", "oracle"]
)
def test_history_coverage_contract_rejects_invalid_proofs(inputs, change):
    row = inputs["coverage"]["coverage"][0]
    if change == "duplicate":
        inputs["coverage"]["coverage"].append(row)
    elif change == "invalid_time":
        row["covered_from_at"] = "2026-07-01T00:00:00+02:00"
    elif change == "reversed":
        row["covered_from_at"] = row["covered_through_at"]
    elif change == "before_availability":
        row["available_at"] = "2026-07-02T00:00:00Z"
    else:
        row["latent_demand"] = 5
    with pytest.raises(ValueError):
        parse_history_coverage(inputs["coverage"])


def truth_for(inputs, order, **changes):
    rows = validate_supplier_truth(
        inputs["truth"], {s["supplier_id"] for s in inputs["supply"]["suppliers"]}
    )
    return next(t for t in rows if t.supplier_id == order.supplier_id).model_copy(update=changes)


def test_reliability_controls_partial_delay_without_affecting_policy(inputs, tmp_path):
    initial = review(inputs)
    config = FulfillmentConfig.from_payload(inputs["fulfillment"])
    order = initial.orders[0]
    normal = simulate_fulfillment(
        order,
        truth_for(inputs, order, reliability="1", lead_time_std_days="0"),
        config,
        first_sequence=3,
    )
    poor = simulate_fulfillment(
        order,
        truth_for(inputs, order, reliability="0", lead_time_std_days="0"),
        config,
        first_sequence=3,
    )
    assert not normal.disrupted and len(normal.receipts) == 1 and normal.lead_days == 2
    assert poor.disrupted and len(poor.receipts) == 2 and poor.lead_days == 4
    assert [r.received_quantity for r in poor.receipts] == [2, 3]
    assert poor.receipts[0].received_at > order.expected_delivery_at
    first = execute(inputs, tmp_path)
    for row in inputs["truth"]["suppliers"]:
        row.update(reliability="0", lead_time_mean_days="12", lead_time_std_days="3")
    inputs["fulfillment"]["seed"] = 2026
    second = execute(inputs, tmp_path)
    assert first["operational"] == second["operational"]
    assert first["operational_sha256"] == second["operational_sha256"]
    assert first["simulation_sha256"] != second["simulation_sha256"]
    assert review(inputs) == initial


def test_two_point_variation_is_bounded_reproducible_and_keyed_per_order(inputs):
    orders = review(inputs).orders
    settings = FulfillmentConfig.from_payload(inputs["fulfillment"])
    observed = set()
    for seed in range(20):
        config = settings.model_copy(update={"seed": seed})
        truth = truth_for(
            inputs, orders[0], reliability="1", lead_time_mean_days="3", lead_time_std_days="1"
        )
        sample = simulate_fulfillment(orders[0], truth, config, first_sequence=3)
        assert sample == simulate_fulfillment(orders[0], truth, config, first_sequence=3)
        observed.add(sample.lead_days)
    assert observed == {2, 4}
    a = simulate_fulfillment(orders[0], truth_for(inputs, orders[0]), settings, first_sequence=3)
    simulate_fulfillment(orders[1], truth_for(inputs, orders[1]), settings, first_sequence=10)
    assert (
        simulate_fulfillment(orders[0], truth_for(inputs, orders[0]), settings, first_sequence=3)
        == a
    )


@pytest.mark.parametrize("quantity", [1, 2, 5, 101])
def test_fulfillment_conserves_small_and_odd_quantities_with_provenance(inputs, quantity):
    order = review(inputs).orders[0].model_copy(update={"ordered_quantity": quantity})
    result = simulate_fulfillment(
        order,
        truth_for(inputs, order, reliability="0"),
        FulfillmentConfig.from_payload(inputs["fulfillment"]),
        first_sequence=3,
    )
    assert sum(r.received_quantity for r in result.receipts) == quantity
    assert all(r.received_quantity > 0 for r in result.receipts)
    assert [r.sequence for r in result.receipts] == list(range(3, 3 + len(result.receipts)))
    assert all(r.received_at <= r.ingested_at <= r.available_at for r in result.receipts)
    assert all(
        r.product_id == order.product_id and r.stock_location_id == order.stock_location_id
        for r in result.receipts
    )
    assert len({r.receipt_id for r in result.receipts}) == len(result.receipts)


@pytest.mark.parametrize("mean,std,expected", [("0", "0", 1), ("100", "0", 30), ("2.01", "0", 3)])
def test_lead_time_quantization_and_clamping_are_explicit(inputs, mean, std, expected):
    order = review(inputs).orders[0]
    sample = simulate_fulfillment(
        order,
        truth_for(inputs, order, reliability="1", lead_time_mean_days=mean, lead_time_std_days=std),
        FulfillmentConfig.from_payload(inputs["fulfillment"]),
        first_sequence=3,
    )
    assert sample.lead_days == expected


@pytest.mark.parametrize(
    "field,value",
    [
        ("seed", True),
        ("minimum_lead_days", 0),
        ("maximum_lead_days", 0),
        ("partial_fraction", "0"),
        ("partial_fraction", "1"),
        ("partial_fraction", 0.5),
        ("disruption_delay_days", 0),
        ("partial_receipt_gap_days", -1),
        ("ingestion_delay_seconds", -1),
        ("availability_delay_seconds", "60"),
        ("lead_time_distribution", "normal"),
        ("oracle_demand", 10),
    ],
)
def test_simulation_effective_config_rejects_invalid_and_hidden_parameters(inputs, field, value):
    inputs["fulfillment"][field] = value
    with pytest.raises(ValueError):
        FulfillmentConfig.from_payload(inputs["fulfillment"])


def test_simulation_rejects_wrong_supplier_and_invalid_sequence(inputs):
    order = review(inputs).orders[0]
    config = FulfillmentConfig.from_payload(inputs["fulfillment"])
    truth = truth_for(inputs, order)
    with pytest.raises(ValueError):
        simulate_fulfillment(
            order,
            truth.model_copy(update={"supplier_id": deterministic_uuid("supplier", "unknown")}),
            config,
            first_sequence=3,
        )
    for invalid in (-1, True, 1.5):
        with pytest.raises(ValueError):
            simulate_fulfillment(order, truth, config, first_sequence=invalid)


def test_runtime_schemas_match_published_artifacts():
    for name, schema in [
        ("reorder_config", reorder_schema()),
        ("inventory_history_coverage", history_coverage_schema()),
        ("supplier_fulfillment_config", fulfillment_schema()),
    ]:
        assert json.loads((ROOT / f"data/contracts/{name}.v1.schema.json").read_text()) == schema


def test_runner_has_repeatable_hashes_reconciles_and_keeps_future_receipts_separate(
    inputs, tmp_path
):
    first, second = execute(inputs, tmp_path), execute(inputs, tmp_path)
    assert first["status"] == second["status"] == "passed"
    assert first["operational_sha256"] == second["operational_sha256"]
    assert first["simulation_sha256"] == second["simulation_sha256"]
    assert first["simulation_truth"]["reconciliation"]["orders"] == 2
    assert first["simulation_truth"]["reconciliation"]["received_quantity"] == 13
    assert first["inventory_ready"] is False
    assert "reliability" not in json.dumps(first["operational"])
    assert "scheduled_receipts" not in first["operational"]
    assert [r["on_hand"] for r in first["positions_at_origin"]] == [4, 0]
    assert all(r["available_at"] > ORIGIN for r in first["simulation_truth"]["scheduled_receipts"])


@pytest.mark.parametrize(
    "change,expected_status,expected_exit",
    [(None, "passed", 0), ("missing_history", "not_ready", 1), ("truth_in_config", "failed", 1)],
)
def test_cli_has_correct_exit_for_passed_missing_input_and_contract_failure(
    inputs, tmp_path, change, expected_status, expected_exit
):
    if change == "missing_history":
        inputs["coverage"]["coverage"] = []
    elif change == "truth_in_config":
        inputs["config"]["reliability"] = "1"
    for key, payload in inputs.items():
        (tmp_path / (key + ".json")).write_text(json.dumps(payload))
    command = [sys.executable, "-m", "data.inventory.run_reorder"]
    for key, option in [
        ("supply", "supply"),
        ("ledger", "ledger"),
        ("config", "config"),
        ("coverage", "coverage"),
        ("fulfillment", "fulfillment-config"),
        ("truth", "supplier-truth"),
    ]:
        command.extend(["--" + option, str(tmp_path / (key + ".json"))])
    output = tmp_path / "report.json"
    command.extend(["--origin", ORIGIN, "--output", str(output)])
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == expected_exit, result.stderr
    assert json.loads(output.read_text())["status"] == expected_status
