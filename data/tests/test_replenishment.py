from __future__ import annotations

import copy
import json
import random
import subprocess
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
from pydantic import ValidationError

from data.generator.common import deterministic_uuid
from data.inventory.ledger import InventoryLedger
from data.inventory.legacy import legacy_stock_movements
from data.inventory.replenishment import ReplenishmentBook
from data.inventory.replenishment_contract import replenishment_schema
from data.inventory.supplier_truth import supplier_truth_schema, validate_supplier_truth
from data.inventory.verify_replenishment import verify

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).parent / "fixtures"
SUPPLY = FIXTURES / "replenishment-v1.json"
LEDGER = FIXTURES / "replenishment-ledger-v1.json"
TRUTH = FIXTURES / "supplier-simulation-truth-v1.json"
END = "2026-07-07T00:00:00Z"
UNKNOWN = "00000000-0000-0000-0000-000000000000"


@pytest.fixture
def payload():
    return json.loads(SUPPLY.read_text())


@pytest.fixture
def ledger_payload():
    return json.loads(LEDGER.read_text())


def balance(ledger, cutoff):
    return sum(row["on_hand"] for row in ledger.balances_at(cutoff, known_at=cutoff))


def test_partial_delayed_receipts_reconcile_with_actual_quantities(payload, ledger_payload):
    book, ledger = (
        ReplenishmentBook.from_payload(payload),
        InventoryLedger.from_payload(ledger_payload),
    )
    assert book.reconcile_ledger(ledger) == {
        "orders": 1,
        "receipts": 2,
        "receipt_movements": 2,
        "received_quantity": 12,
    }
    assert [m.quantity_delta for m in book.receipt_movements()] == [5, 7]
    assert balance(ledger, "2026-07-03T10:02:59Z") == 0
    assert balance(ledger, "2026-07-03T10:03:00Z") == 5
    assert balance(ledger, "2026-07-06T10:02:59Z") == 5
    assert balance(ledger, "2026-07-06T10:03:00Z") == 12
    assert [
        r["quantity"]
        for r in legacy_stock_movements(ledger)
        if r["movement_type"] == "replenishment"
    ] == ["5", "7"]
    assert book.receipts[-1].received_at > book.plans[-1].expected_delivery_at


@pytest.mark.parametrize(
    "cutoff,status,received,version,promise",
    [
        ("2026-07-01T10:01:00Z", "ordered", 0, 1, "2026-07-03T10:00:00+00:00"),
        ("2026-07-03T10:02:59Z", "ordered", 0, 1, "2026-07-03T10:00:00+00:00"),
        ("2026-07-03T10:03:00Z", "partially_received", 5, 1, "2026-07-03T10:00:00+00:00"),
        ("2026-07-04T09:01:59Z", "partially_received", 5, 1, "2026-07-03T10:00:00+00:00"),
        ("2026-07-04T09:02:00Z", "partially_received", 5, 2, "2026-07-05T10:00:00+00:00"),
        ("2026-07-06T10:02:59Z", "partially_received", 5, 2, "2026-07-05T10:00:00+00:00"),
        ("2026-07-06T10:03:00Z", "received", 12, 2, "2026-07-05T10:00:00+00:00"),
    ],
)
def test_known_order_status_and_promise_do_not_leak_future(
    payload, cutoff, status, received, version, promise
):
    (row,) = ReplenishmentBook.from_payload(payload).orders_at(cutoff)
    assert (row["status"], row["received_quantity"], row["outstanding_quantity"]) == (
        status,
        received,
        12 - received,
    )
    assert (row["delivery_plan_version"], row["expected_delivery_at"]) == (version, promise)


def test_unknown_order_never_falls_back_to_future(payload):
    assert ReplenishmentBook.from_payload(payload).orders_at("2026-07-01T10:00:59Z") == []


def test_late_revision_and_receipt_cannot_rewrite_an_earlier_origin(payload, ledger_payload):
    original = ReplenishmentBook.from_payload(payload)
    cutoff = "2026-07-04T08:00:00Z"
    baseline = copy.deepcopy(payload)
    baseline["delivery_plan_versions"] = baseline["delivery_plan_versions"][:1]
    baseline["replenishment_receipts"] = baseline["replenishment_receipts"][:1]
    prior = ReplenishmentBook.from_payload(baseline)
    assert prior.orders_at(cutoff) == original.orders_at(cutoff)
    payload["replenishment_receipts"][-1]["ingested_at"] = "2026-07-08T10:00:00Z"
    payload["replenishment_receipts"][-1]["available_at"] = "2026-07-08T10:01:00Z"
    later = ReplenishmentBook.from_payload(payload)
    assert later.orders_at(END)[0]["received_quantity"] == 5
    ledger_payload["movements"][-1].update(later.receipt_movements()[-1].record())
    ledger = InventoryLedger.from_payload(ledger_payload)
    later.reconcile_ledger(ledger)
    assert balance(ledger, END) == 5
    assert balance(ledger, "2026-07-08T10:01:00Z") == 12
    assert later.orders_at(cutoff) == prior.orders_at(cutoff)


def test_no_orders_and_no_receipts_create_no_inventory(payload, ledger_payload):
    for key in ("replenishment_orders", "delivery_plan_versions", "replenishment_receipts"):
        payload[key] = []
    ledger_payload["movements"] = ledger_payload["movements"][:2]
    book, ledger = (
        ReplenishmentBook.from_payload(payload),
        InventoryLedger.from_payload(ledger_payload),
    )
    assert book.orders_at(END) == []
    assert book.receipt_movements() == ()
    assert book.reconcile_ledger(ledger)["received_quantity"] == balance(ledger, END) == 0


def test_pending_or_partial_order_does_not_create_its_outstanding_stock(payload, ledger_payload):
    for count, expected in [(0, 0), (1, 5)]:
        candidate = copy.deepcopy(payload)
        candidate["replenishment_receipts"] = candidate["replenishment_receipts"][:count]
        book = ReplenishmentBook.from_payload(candidate)
        ledger_copy = copy.deepcopy(ledger_payload)
        ledger_copy["movements"] = ledger_copy["movements"][: count + 2]
        ledger = InventoryLedger.from_payload(ledger_copy)
        book.reconcile_ledger(ledger)
        assert balance(ledger, END) == expected
        assert book.orders_at(END)[0]["outstanding_quantity"] == 12 - expected


def test_immutable_sorted_records_and_equivalent_utc_encodings(payload):
    reference = ReplenishmentBook.from_payload(payload)
    for seed in range(5):
        shuffled = copy.deepcopy(payload)
        for key, rows in shuffled.items():
            if isinstance(rows, list):
                random.Random(seed).shuffle(rows)
                for row in rows:
                    for field, value in row.items():
                        if field.endswith("_at"):
                            row[field] = value.replace("Z", "+00:00")
        candidate = ReplenishmentBook.from_payload(shuffled)
        assert candidate == reference
        assert candidate.orders_at(END) == reference.orders_at(END)
        assert candidate.receipt_movements() == reference.receipt_movements()
    with pytest.raises(FrozenInstanceError):
        reference.orders = ()
    with pytest.raises(ValidationError):
        reference.orders[0].ordered_quantity = 99


def test_quote_lookup_respects_period_supplier_status_and_availability(payload):
    book = ReplenishmentBook.from_payload(payload)
    product = payload["products"][0]["id"]
    assert book.known_quotes(product, "2026-06-01", known_at="2026-06-01T00:02:59Z") == ()
    quotes = book.known_quotes(product, "2026-06-01", known_at="2026-06-01T00:03:00Z")
    assert len(quotes) == 1
    assert quotes[0].quoted_lead_time_days == 2
    assert book.known_quotes(product, "2026-08-01", known_at=END) == ()
    assert book.known_quotes(product, "2026-05-31", known_at=END) == ()
    with pytest.raises(ValueError, match="Unknown product"):
        book.known_quotes(UNKNOWN, "2026-07-01", known_at=END)


def test_multiple_active_suppliers_have_stable_priority_order(payload):
    payload["suppliers"][1]["status"] = "active"
    payload["product_suppliers"][1]["priority"] = 1
    payload["product_suppliers"][0]["priority"] = 2
    book = ReplenishmentBook.from_payload(payload)
    quotes = book.known_quotes(payload["products"][0]["id"], "2026-07-01", known_at=END)
    assert [q.supplier_id for q in quotes] == [
        payload["suppliers"][1]["supplier_id"],
        payload["suppliers"][0]["supplier_id"],
    ]


@pytest.mark.parametrize(
    "table,field,value",
    [
        ("product_suppliers", "product_id", UNKNOWN),
        ("product_suppliers", "supplier_id", UNKNOWN),
        ("product_suppliers", "unit_of_measure", "kg"),
        ("product_suppliers", "unit_cost", "0.00"),
        ("product_suppliers", "effective_from", "2026-08-01"),
        ("product_suppliers", "effective_to", "2026-07-01"),
        ("product_suppliers", "effective_from", "2026-02-30"),
        ("product_suppliers", "available_at", "2026-06-01T00:01:59Z"),
        ("product_suppliers", "known_at", "2026-05-31T23:59:59Z"),
        ("product_suppliers", "available_at", "2026-07-01T10:00:01Z"),
        ("suppliers", "status", "inactive"),
        ("replenishment_orders", "product_supplier_id", UNKNOWN),
        ("replenishment_orders", "product_id", UNKNOWN),
        ("replenishment_orders", "supplier_id", UNKNOWN),
        ("replenishment_orders", "stock_location_id", UNKNOWN),
        ("replenishment_orders", "unit_of_measure", "kg"),
        ("replenishment_orders", "ordered_quantity", 4),
        ("replenishment_orders", "expected_delivery_at", "2026-07-01T09:59:59Z"),
        ("replenishment_orders", "available_at", "2026-07-01T10:00:00Z"),
        ("replenishment_receipts", "replenishment_order_id", UNKNOWN),
        ("replenishment_receipts", "product_id", UNKNOWN),
        ("replenishment_receipts", "supplier_id", UNKNOWN),
        ("replenishment_receipts", "stock_location_id", UNKNOWN),
        ("replenishment_receipts", "unit_of_measure", "kg"),
        ("replenishment_receipts", "received_quantity", 13),
        ("replenishment_receipts", "received_at", "2026-07-01T09:59:59Z"),
        ("replenishment_receipts", "available_at", "2026-07-03T10:01:00Z"),
        ("delivery_plan_versions", "replenishment_order_id", UNKNOWN),
        ("delivery_plan_versions", "version", 2),
        ("delivery_plan_versions", "expected_delivery_at", "2026-07-01T09:59:59Z"),
        ("delivery_plan_versions", "known_at", "2026-07-01T09:59:59Z"),
        ("delivery_plan_versions", "available_at", "2026-07-01T10:00:00Z"),
    ],
)
def test_semantic_fk_time_quantity_and_period_failures(payload, table, field, value):
    payload[table][0][field] = value
    with pytest.raises(ValueError):
        ReplenishmentBook.from_payload(payload)


@pytest.mark.parametrize(
    "table",
    [
        "products",
        "stock_locations",
        "suppliers",
        "product_suppliers",
        "replenishment_orders",
        "delivery_plan_versions",
        "replenishment_receipts",
    ],
)
def test_duplicate_primary_keys_fail(payload, table):
    payload[table].append(copy.deepcopy(payload[table][0]))
    with pytest.raises(ValueError, match="Duplicate"):
        ReplenishmentBook.from_payload(payload)


@pytest.mark.parametrize(
    "table,field", [("suppliers", "supplier_code"), ("stock_locations", "location_code")]
)
def test_duplicate_codes_fail(payload, table, field):
    payload[table][1][field] = payload[table][0][field]
    with pytest.raises(ValueError, match="Duplicate"):
        ReplenishmentBook.from_payload(payload)


def test_overlapping_quote_periods_fail_but_adjacent_periods_are_valid(payload):
    quote = copy.deepcopy(payload["product_suppliers"][0])
    quote["product_supplier_id"] = UNKNOWN
    payload["product_suppliers"].append(quote)
    with pytest.raises(ValueError, match="overlapping"):
        ReplenishmentBook.from_payload(payload)
    quote["effective_from"], quote["effective_to"] = "2026-08-01", "2026-09-01"
    ReplenishmentBook.from_payload(payload)


@pytest.mark.parametrize(
    "change",
    ["missing_initial", "gap", "backdated", "availability_backwards", "initial_promise_changed"],
)
def test_delivery_version_history_is_append_only(payload, change):
    first, second = payload["delivery_plan_versions"]
    if change == "missing_initial":
        payload["delivery_plan_versions"] = [second]
    elif change == "gap":
        second["version"] = 3
    elif change == "backdated":
        second["known_at"] = "2026-07-01T09:00:00Z"
    elif change == "availability_backwards":
        first["ingested_at"] = "2026-07-05T00:00:00Z"
        first["available_at"] = "2026-07-05T00:00:00Z"
        payload["replenishment_orders"][0]["ingested_at"] = first["ingested_at"]
        payload["replenishment_orders"][0]["available_at"] = first["available_at"]
    else:
        first["expected_delivery_at"] = "2026-07-03T11:00:00Z"
    with pytest.raises(ValueError):
        ReplenishmentBook.from_payload(payload)


def test_receipt_cannot_be_known_before_the_order(payload):
    order = payload["replenishment_orders"][0]
    order["ingested_at"] = order["available_at"] = "2026-07-05T00:00:00Z"
    payload["delivery_plan_versions"][0]["ingested_at"] = order["ingested_at"]
    payload["delivery_plan_versions"][0]["available_at"] = order["available_at"]
    payload["delivery_plan_versions"] = payload["delivery_plan_versions"][:1]
    with pytest.raises(ValueError, match="known before its order"):
        ReplenishmentBook.from_payload(payload)


def test_duplicate_receipt_ordering_key_is_canonical_utc(payload):
    first, second = payload["replenishment_receipts"]
    second["received_at"] = first["received_at"].replace("Z", "+00:00")
    second["sequence"] = first["sequence"]
    with pytest.raises(ValueError, match="timestamp/sequence"):
        ReplenishmentBook.from_payload(payload)


@pytest.mark.parametrize(
    "table,field,value",
    [
        ("suppliers", "minimum_order_quantity", True),
        ("suppliers", "minimum_order_quantity", 0),
        ("suppliers", "country_code", "XX"),
        ("suppliers", "supplier_code", " "),
        ("product_suppliers", "unit_cost", 5.0),
        ("product_suppliers", "unit_cost", "5.001"),
        ("product_suppliers", "priority", False),
        ("product_suppliers", "quoted_lead_time_days", -1),
        ("product_suppliers", "lead_time_basis", "simulation_truth"),
        ("product_suppliers", "quote_reference", " "),
        ("replenishment_orders", "ordered_quantity", "12"),
        ("replenishment_orders", "status", "received"),
        ("replenishment_receipts", "received_quantity", 0),
        ("replenishment_receipts", "sequence", 1.0),
        ("delivery_plan_versions", "version", 0),
    ],
)
def test_strict_contract_rejects_coercions_and_invalid_values(payload, table, field, value):
    payload[table][0][field] = value
    with pytest.raises(ValueError, match="contract violation"):
        ReplenishmentBook.from_payload(payload)


@pytest.mark.parametrize(
    "table,field",
    [
        ("suppliers", "available_at"),
        ("product_suppliers", "known_at"),
        ("replenishment_orders", "ordered_at"),
        ("delivery_plan_versions", "expected_delivery_at"),
        ("replenishment_receipts", "received_at"),
    ],
)
@pytest.mark.parametrize(
    "value",
    [
        "2026-07-01T10:00:00",
        "2026-07-01T12:00:00+02:00",
        "2026-02-30T10:00:00Z",
        "2026-07-01T10:00:00.0000001Z",
    ],
)
def test_every_supply_timestamp_requires_valid_precise_utc(payload, table, field, value):
    payload[table][0][field] = value
    with pytest.raises(ValueError):
        ReplenishmentBook.from_payload(payload)


@pytest.mark.parametrize(
    "table",
    [
        "suppliers",
        "product_suppliers",
        "replenishment_orders",
        "replenishment_receipts",
        "delivery_plan_versions",
    ],
)
@pytest.mark.parametrize("field", ["reliability", "lead_time_mean_days", "lead_time_std_days"])
def test_simulator_truth_is_rejected_in_every_operational_record(payload, table, field):
    payload[table][0][field] = "0.9"
    with pytest.raises(ValueError, match="Extra inputs"):
        ReplenishmentBook.from_payload(payload)


def test_truth_is_separate_and_cannot_change_operational_views(payload):
    book = ReplenishmentBook.from_payload(payload)
    truth = json.loads(TRUTH.read_text())
    ids = {s.supplier_id for s in book.suppliers}
    rows = validate_supplier_truth(truth, ids)
    assert len(rows) == 2
    initial = (book.orders_at(END), book.receipt_movements())
    for row in truth["suppliers"]:
        row.update(reliability="0", lead_time_mean_days="100", lead_time_std_days="50")
    validate_supplier_truth(truth, ids)
    assert (book.orders_at(END), book.receipt_movements()) == initial
    payload["supplier_truth"] = truth
    with pytest.raises(ValueError, match="Extra inputs"):
        ReplenishmentBook.from_payload(payload)


@pytest.mark.parametrize(
    "field,value",
    [
        ("reliability", "1.01"),
        ("reliability", "-0.1"),
        ("reliability", "NaN"),
        ("reliability", 0.9),
        ("lead_time_mean_days", "-1"),
        ("lead_time_std_days", "Infinity"),
    ],
)
def test_invalid_supplier_truth_fails(payload, field, value):
    truth = json.loads(TRUTH.read_text())
    truth["suppliers"][0][field] = value
    with pytest.raises(ValueError):
        validate_supplier_truth(truth, {s["supplier_id"] for s in payload["suppliers"]})


@pytest.mark.parametrize("change", ["duplicate", "missing", "unknown"])
def test_truth_supplier_ids_cover_the_operational_catalog_exactly(payload, change):
    truth = json.loads(TRUTH.read_text())
    if change == "duplicate":
        truth["suppliers"].append(truth["suppliers"][0])
    elif change == "missing":
        truth["suppliers"].pop()
    else:
        truth["suppliers"][0]["supplier_id"] = UNKNOWN
    with pytest.raises(ValueError):
        validate_supplier_truth(truth, {s["supplier_id"] for s in payload["suppliers"]})


@pytest.mark.parametrize(
    "field,value",
    [
        ("quantity_delta", 12),
        ("source_reference", "unlinked-receipt"),
        ("order_id", UNKNOWN),
        ("supplier_id", UNKNOWN),
        ("stock_location_id", "7db7acb8-6e46-5a3e-b39a-faaa449238a3"),
        ("occurred_at", "2026-07-03T10:00:01Z"),
        ("ingested_at", "2026-07-03T10:02:01Z"),
        ("available_at", "2026-07-03T10:03:01Z"),
        ("sequence", 99),
        ("inventory_event_id", UNKNOWN),
    ],
)
def test_ledger_receipt_reconciliation_rejects_any_changed_fact(
    payload, ledger_payload, field, value
):
    ledger_payload["movements"][2][field] = value
    ledger = InventoryLedger.from_payload(ledger_payload)
    with pytest.raises(ValueError, match="exactly once"):
        ReplenishmentBook.from_payload(payload).reconcile_ledger(ledger)


@pytest.mark.parametrize("change", ["missing", "orphan", "duplicate"])
def test_receipt_ledger_bijection_rejects_missing_extra_and_duplicate_movements(
    payload, ledger_payload, change
):
    if change == "missing":
        ledger_payload["movements"].pop()
    else:
        row = copy.deepcopy(ledger_payload["movements"][2])
        row["inventory_event_id"] = deterministic_uuid("inventory_event", change)
        row["sequence"] = 100
        if change == "orphan":
            row["source_reference"] = "unknown-receipt"
        ledger_payload["movements"].append(row)
    ledger = InventoryLedger.from_payload(ledger_payload)
    with pytest.raises(ValueError, match="exactly once"):
        ReplenishmentBook.from_payload(payload).reconcile_ledger(ledger)


@pytest.mark.parametrize("change", ["location_code", "outside_scope", "unit"])
def test_pending_orders_require_correct_ledger_destination_and_unit(
    payload, ledger_payload, change
):
    payload["replenishment_receipts"] = []
    ledger_payload["movements"] = ledger_payload["movements"][:2]
    if change == "location_code":
        ledger_payload["stock_locations"][0]["location_code"] = "WRONG"
    elif change == "outside_scope":
        ledger_payload["inventory_scope"] = ledger_payload["inventory_scope"][1:]
        ledger_payload["movements"] = ledger_payload["movements"][1:]
    else:
        ledger_payload["products"][0]["unit_of_measure"] = "kg"
        for row in ledger_payload["movements"]:
            row["unit_of_measure"] = "kg"
    with pytest.raises(ValueError):
        ReplenishmentBook.from_payload(payload).reconcile_ledger(
            InventoryLedger.from_payload(ledger_payload)
        )


def test_published_schemas_match_runtime_contracts():
    assert (
        json.loads((ROOT / "data/contracts/replenishment.v1.schema.json").read_text())
        == replenishment_schema()
    )
    assert (
        json.loads((ROOT / "data/contracts/supplier_simulation_truth.v1.schema.json").read_text())
        == supplier_truth_schema()
    )


def test_verifier_reports_receipts_and_known_state_without_loading_truth(monkeypatch):
    original = Path.read_text

    def guarded_read(path, *args, **kwargs):
        if path == TRUTH:
            raise AssertionError("Operational verifier tried to load simulation truth")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read)
    result = verify(SUPPLY, LEDGER, "2026-07-03T10:03:00Z")
    assert result["status"] == "passed"
    assert result["inventory_ready"] is False
    assert result["known_orders"][0]["received_quantity"] == 5
    assert sum(row["on_hand"] for row in result["positions"]) == 5
    assert result["reconciliation"]["receipts"] == 2
    assert "reliability" not in json.dumps(result)


@pytest.mark.parametrize(
    "change,exit_code", [(None, 0), ("over_receipt", 1), ("wrong_ledger", 1), ("invalid_json", 1)]
)
def test_cli_returns_auditable_passed_or_failed_report(payload, tmp_path, change, exit_code):
    source, output = tmp_path / "supply.json", tmp_path / "report.json"
    if change == "over_receipt":
        payload["replenishment_receipts"][0]["received_quantity"] = 13
    source.write_text("[]" if change == "invalid_json" else json.dumps(payload))
    ledger = FIXTURES / "inventory-ledger-v1.json" if change == "wrong_ledger" else LEDGER
    command = [
        sys.executable,
        "-m",
        "data.inventory.verify_replenishment",
        "--input",
        str(source),
        "--ledger",
        str(ledger),
        "--known-at",
        END,
        "--output",
        str(output),
    ]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == exit_code, result.stderr
    report = json.loads(output.read_text())
    assert report["status"] == ("passed" if exit_code == 0 else "failed")
    if exit_code:
        assert report["error"]
