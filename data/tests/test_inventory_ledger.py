from __future__ import annotations

import copy
import json
import random
import subprocess
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from data.generator.common import deterministic_uuid
from data.generator.csv_writer import TABLE_COLUMNS
from data.inventory.contract import LEDGER_VERSION, ledger_contract_schema
from data.inventory.ledger import InventoryLedger, build_opening_movements
from data.inventory.legacy import legacy_stock_movements
from data.inventory.verify import verify

FIXTURE = Path(__file__).parent / "fixtures/inventory-ledger-v1.json"
ROOT = Path(__file__).resolve().parents[2]
END = "2026-07-03T23:59:59Z"


@pytest.fixture
def payload():
    return json.loads(FIXTURE.read_text())


def movement(payload, kind):
    return next(m for m in payload["movements"] if m["movement_type"] == kind)


def by_code(ledger, balances):
    codes = dict(ledger.stock_location_codes)
    return {codes[row["stock_location_id"]]: row for row in balances}


def test_all_movement_types_reconcile_without_second_opening(payload):
    ledger = InventoryLedger.from_payload(payload)
    balances = by_code(ledger, ledger.balances_at(END))
    assert {code: row["on_hand"] for code, row in balances.items()} == {"WH-0001": 8, "WH-0002": 3}
    for row in balances.values():
        assert row["reserved_qty"] == 0
        assert row["available_qty"] == row["on_hand"]
        assert row["status"] == "known"
    assert ledger.transit_at(END) == []
    assert len(ledger.movements) == 9
    assert len({m.movement_type for m in ledger.movements}) == 8
    assert sum(row["on_hand"] for row in balances.values()) == sum(
        m.quantity_delta for m in ledger.movements
    )


def test_same_timestamp_uses_sequence_and_rejects_overspend(payload):
    receipt, sale = movement(payload, "replenishment_received"), movement(payload, "sale")
    sale["quantity_delta"] = -12
    ledger = InventoryLedger.from_payload(payload)
    assert by_code(ledger, ledger.balances_at(END))["WH-0001"]["on_hand"] == 0
    receipt["sequence"], sale["sequence"] = sale["sequence"], receipt["sequence"]
    with pytest.raises(ValueError, match="negative balance"):
        InventoryLedger.from_payload(payload)


def test_input_order_does_not_change_ledger_or_legacy_projection(payload):
    reference = InventoryLedger.from_payload(payload)
    for seed in range(10):
        shuffled = copy.deepcopy(payload)
        random.Random(seed).shuffle(shuffled["movements"])
        shuffled["inventory_scope"].reverse()
        shuffled["stock_locations"].reverse()
        candidate = InventoryLedger.from_payload(shuffled)
        assert candidate == reference
        assert candidate.balances_at(END) == reference.balances_at(END)
        assert legacy_stock_movements(candidate) == legacy_stock_movements(reference)


def test_zero_opening_is_known_zero_before_transfer(payload):
    ledger = InventoryLedger.from_payload(payload)
    rows = by_code(
        ledger, ledger.balances_at(payload["opening_at"], known_at=payload["opening_at"])
    )
    assert rows["WH-0002"]["on_hand"] == 0
    assert rows["WH-0002"]["status"] == "known"


def test_before_opening_is_missing_not_invented_zero(payload):
    ledger = InventoryLedger.from_payload(payload)
    for row in ledger.balances_at("2026-06-30T23:59:59.999999Z"):
        assert row["status"] == "not_available"
        assert row["on_hand"] is row["reserved_qty"] is row["available_qty"] is None


def test_late_receipt_does_not_change_earlier_knowledge(payload):
    baseline = copy.deepcopy(payload)
    baseline["movements"].remove(movement(baseline, "replenishment_received"))
    before = InventoryLedger.from_payload(baseline)
    receipt = movement(payload, "replenishment_received")
    receipt["ingested_at"] = "2026-07-04T00:00:00Z"
    receipt["available_at"] = "2026-07-04T00:00:00.000001Z"
    revised = InventoryLedger.from_payload(payload)
    cutoff = END
    assert before.balances_at(END, known_at=cutoff) == revised.balances_at(END, known_at=cutoff)
    excluded = by_code(revised, revised.balances_at(END, known_at="2026-07-04T00:00:00Z"))
    included = by_code(revised, revised.balances_at(END, known_at=receipt["available_at"]))
    assert excluded["WH-0001"]["on_hand"] == 3
    assert included["WH-0001"]["on_hand"] == 8
    assert by_code(before, before.balances_at(END))["WH-0001"]["on_hand"] == 3
    assert by_code(revised, revised.balances_at(END))["WH-0001"]["on_hand"] == 8


def test_equivalent_utc_encodings_have_same_canonical_movements(payload):
    first = InventoryLedger.from_payload(payload)
    for row in payload["movements"]:
        for field in ("occurred_at", "ingested_at", "available_at"):
            row[field] = row[field].replace("+00:00", "Z")
    second = InventoryLedger.from_payload(payload)
    assert first == second
    assert [m.record() for m in first.movements] == [m.record() for m in second.movements]


@pytest.mark.parametrize(
    "value",
    [
        "2026-07-01T00:00:00.0000001Z",
        "2026-07-01T00:00:00",
        "2026-07-01T02:00:00+02:00",
        "2026-07-01 00:00:00+00:00",
        "2026-02-30T00:00:00Z",
    ],
)
def test_query_and_opening_builder_reject_invalid_timestamp(payload, value):
    ledger = InventoryLedger.from_payload(payload)
    with pytest.raises(ValueError):
        ledger.balances_at(value)
    with pytest.raises(ValueError):
        ledger.balances_at(END, known_at=value)
    row = payload["inventory_scope"][0]
    with pytest.raises(ValueError):
        build_opening_movements(
            {(row["product_id"], row["stock_location_id"]): 0},
            {row["product_id"]: "pcs"},
            occurred_at=value,
            ingested_at=payload["opening_at"],
            available_at=payload["opening_at"],
        )


def test_incomplete_knowledge_fails_when_known_sale_has_no_known_opening(payload):
    opening = next(
        m
        for m in payload["movements"]
        if m["movement_type"] == "opening_stock" and m["quantity_delta"] > 0
    )
    opening["ingested_at"] = opening["available_at"] = "2026-07-02T00:00:00Z"
    ledger = InventoryLedger.from_payload(payload)
    with pytest.raises(ValueError, match="known preceding opening"):
        ledger.balances_at("2026-07-01T01:00:00Z", known_at="2026-07-01T01:00:00Z")


def test_transfer_has_explicit_transit_and_preserves_inventory(payload):
    ledger = InventoryLedger.from_payload(payload)
    rows = ledger.balances_at("2026-07-02T04:00:00Z")
    transit = ledger.transit_at("2026-07-02T04:00:00Z")
    assert len(transit) == 1 and transit[0]["quantity"] == 3
    assert sum(row["on_hand"] for row in rows) + transit[0]["quantity"] == 12
    assert ledger.transit_at("2026-07-03T03:00:00Z") == []
    assert sum(row["on_hand"] for row in ledger.balances_at("2026-07-03T03:00:00Z")) == 12


def test_known_transfer_receipt_is_not_a_future_fallback(payload):
    inbound = movement(payload, "transfer_in")
    inbound["ingested_at"] = inbound["available_at"] = "2026-07-05T00:00:00Z"
    ledger = InventoryLedger.from_payload(payload)
    transit = ledger.transit_at(END, known_at="2026-07-04T00:00:00Z")
    assert len(transit) == 1 and transit[0]["quantity"] == 3
    balances = by_code(ledger, ledger.balances_at(END, known_at="2026-07-04T00:00:00Z"))
    assert balances["WH-0002"]["on_hand"] == 0


@pytest.mark.parametrize(
    "kind,quantity",
    [
        ("opening_stock", -1),
        ("replenishment_received", -1),
        ("replenishment_received", 0),
        ("sale", 1),
        ("sale", 0),
        ("return_to_stock", -1),
        ("return_to_stock", 0),
        ("write_off", 1),
        ("write_off", 0),
        ("transfer_in", -1),
        ("transfer_in", 0),
        ("transfer_out", 1),
        ("transfer_out", 0),
        ("inventory_adjustment", 0),
    ],
)
def test_illegal_signs_fail(payload, kind, quantity):
    movement(payload, kind)["quantity_delta"] = quantity
    with pytest.raises(ValueError):
        InventoryLedger.from_payload(payload)


@pytest.mark.parametrize(
    "field,value",
    [
        ("quantity_delta", True),
        ("quantity_delta", -1.0),
        ("quantity_delta", "-1"),
        ("sequence", True),
        ("sequence", 1.0),
        ("sequence", -1),
        ("inventory_event_id", "unknown"),
        ("product_id", deterministic_uuid("test", "unknown-product")),
        ("stock_location_id", deterministic_uuid("test", "unknown-location")),
        ("unit_of_measure", "kg"),
        ("source_process", "return"),
        ("source_reference", ""),
        ("source_reference", "  "),
        ("movement_type", "initial_stock"),
        ("occurred_at", "2026-07-01T01:00:00"),
        ("occurred_at", "2026-07-01T03:00:00+02:00"),
        ("occurred_at", "2026-02-30T01:00:00Z"),
        ("occurred_at", "2026-07-01T01:00:00.0000001Z"),
        ("occurred_at", "2026-07-02T01:00:00Z"),
        ("ingested_at", "2026-07-01T00:00:00Z"),
        ("available_at", "2026-07-01T00:00:00Z"),
        ("transfer_id", deterministic_uuid("test", "unexpected-transfer")),
    ],
)
def test_invalid_movement_contract_fails(payload, field, value):
    movement(payload, "sale")[field] = value
    with pytest.raises(ValueError):
        InventoryLedger.from_payload(payload)


@pytest.mark.parametrize(
    "field,value",
    [
        ("contract_version", "inventory-ledger-2.0.0"),
        ("opening_policy", "balance_plus_opening"),
        ("reservation_policy", "reserve_and_fulfill"),
        ("opening_at", "2026-07-02T00:00:00Z"),
        ("products", []),
        ("stock_locations", []),
        ("inventory_scope", []),
        ("movements", []),
    ],
)
def test_invalid_envelope_fails(payload, field, value):
    payload[field] = value
    with pytest.raises(ValueError):
        InventoryLedger.from_payload(payload)


@pytest.mark.parametrize("table", ["products", "stock_locations", "inventory_scope"])
def test_duplicate_master_or_scope_fails(payload, table):
    payload[table].append(copy.deepcopy(payload[table][0]))
    with pytest.raises(ValueError, match="Duplicate"):
        InventoryLedger.from_payload(payload)


def test_duplicate_location_code_fails(payload):
    payload["stock_locations"][1]["location_code"] = payload["stock_locations"][0]["location_code"]
    with pytest.raises(ValueError, match="location code"):
        InventoryLedger.from_payload(payload)


def test_unknown_scope_master_fails(payload):
    payload["inventory_scope"][0]["product_id"] = deterministic_uuid("test", "unknown")
    with pytest.raises(ValueError, match="unknown masters"):
        InventoryLedger.from_payload(payload)


def test_unknown_fields_cannot_smuggle_truth(payload):
    movement(payload, "sale")["latent_demand"] = 100
    with pytest.raises(ValueError, match="contract violation"):
        InventoryLedger.from_payload(payload)


def test_missing_fields_fail(payload):
    del movement(payload, "sale")["available_at"]
    with pytest.raises(ValueError, match="contract violation"):
        InventoryLedger.from_payload(payload)


def test_duplicate_event_id_fails(payload):
    movement(payload, "sale")["inventory_event_id"] = movement(payload, "replenishment_received")[
        "inventory_event_id"
    ]
    with pytest.raises(ValueError, match="event ID"):
        InventoryLedger.from_payload(payload)


def test_duplicate_timestamp_sequence_fails(payload):
    movement(payload, "sale")["sequence"] = movement(payload, "replenishment_received")["sequence"]
    with pytest.raises(ValueError, match="timestamp/sequence"):
        InventoryLedger.from_payload(payload)


@pytest.mark.parametrize("new_timestamp", ["2026-07-01T00:00:00Z", "2026-07-08T00:00:00Z"])
def test_repeated_opening_including_weekly_snapshot_fails(payload, new_timestamp):
    duplicate = copy.deepcopy(movement(payload, "opening_stock"))
    duplicate["inventory_event_id"] = deterministic_uuid("test", "duplicate-opening")
    duplicate["sequence"] = 100
    duplicate["occurred_at"] = duplicate["ingested_at"] = duplicate["available_at"] = new_timestamp
    payload["movements"].append(duplicate)
    with pytest.raises(ValueError, match="exactly one opening"):
        InventoryLedger.from_payload(payload)


def test_missing_opening_fails(payload):
    payload["movements"].remove(movement(payload, "opening_stock"))
    with pytest.raises(ValueError, match="exactly one opening"):
        InventoryLedger.from_payload(payload)


def test_nonopening_before_opening_fails(payload):
    sale = movement(payload, "sale")
    sale["occurred_at"] = sale["ingested_at"] = sale["available_at"] = "2026-06-30T23:00:00Z"
    with pytest.raises(ValueError, match="known preceding opening"):
        InventoryLedger.from_payload(payload)


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_pair",
        "wrong_quantity",
        "wrong_product",
        "same_location",
        "inbound_first",
        "inbound_known_first",
        "missing_transfer_id",
    ],
)
def test_invalid_transfer_fails(payload, mutation):
    outbound, inbound = movement(payload, "transfer_out"), movement(payload, "transfer_in")
    if mutation == "missing_pair":
        payload["movements"].remove(inbound)
    elif mutation == "wrong_quantity":
        inbound["quantity_delta"] += 1
    elif mutation == "wrong_product":
        inbound["product_id"] = deterministic_uuid("test", "other-product")
    elif mutation == "same_location":
        inbound["stock_location_id"] = outbound["stock_location_id"]
    elif mutation == "inbound_first":
        inbound["occurred_at"] = inbound["ingested_at"] = inbound["available_at"] = (
            "2026-07-01T23:00:00Z"
        )
    elif mutation == "inbound_known_first":
        outbound["ingested_at"] = outbound["available_at"] = "2026-07-04T00:00:00Z"
    else:
        outbound["transfer_id"] = None
    with pytest.raises(ValueError):
        InventoryLedger.from_payload(payload)


def test_ledger_is_immutable_and_does_not_modify_input(payload):
    original = copy.deepcopy(payload)
    ledger = InventoryLedger.from_payload(payload)
    assert payload == original
    with pytest.raises(FrozenInstanceError):
        ledger.movements[0].quantity_delta = 100
    payload["movements"].clear()
    assert len(ledger.movements) == 9


def test_opening_builder_is_deterministic(payload):
    units = {row["id"]: row["unit_of_measure"] for row in payload["products"]}
    quantities = {
        (m["product_id"], m["stock_location_id"]): m["quantity_delta"]
        for m in payload["movements"]
        if m["movement_type"] == "opening_stock"
    }
    options = dict(
        occurred_at=payload["opening_at"],
        ingested_at=payload["opening_at"],
        available_at=payload["opening_at"],
    )
    first = build_opening_movements(quantities, units, **options)
    assert first == build_opening_movements(
        dict(reversed(list(quantities.items()))), units, **options
    )
    assert first == [m for m in payload["movements"] if m["movement_type"] == "opening_stock"]


@pytest.mark.parametrize("quantity", [-1, True, 1.0])
def test_invalid_opening_builder_quantity_fails(payload, quantity):
    row = payload["inventory_scope"][0]
    with pytest.raises(ValueError, match="nonnegative integer"):
        build_opening_movements(
            {(row["product_id"], row["stock_location_id"]): quantity},
            {row["product_id"]: "pcs"},
            occurred_at=payload["opening_at"],
            ingested_at=payload["opening_at"],
            available_at=payload["opening_at"],
        )


def test_legacy_adapter_has_exact_existing_columns_and_is_not_reimportable(payload):
    ledger = InventoryLedger.from_payload(payload)
    rows = legacy_stock_movements(ledger)
    assert all(list(row) == TABLE_COLUMNS["stock_movements"] for row in rows)
    assert len([r for r in rows if r["movement_type"] == "initial_stock"]) == 2
    assert len([r for r in rows if r["movement_type"] == "replenishment"]) == 1
    assert all(r["warehouse_id"] in dict(ledger.stock_location_codes) for r in rows)
    with pytest.raises(ValueError, match="contract violation"):
        InventoryLedger.from_payload({"stock_movements": rows})


def test_json_schema_matches_runtime_model():
    assert (
        json.loads((ROOT / "data/contracts/inventory_ledger.v1.schema.json").read_text())
        == ledger_contract_schema()
    )


def test_verification_records_contract_scope_not_source_readiness():
    report = verify(FIXTURE, END)
    assert report["status"] == "passed"
    assert report["contract_version"] == LEDGER_VERSION
    assert report["inventory_ready"] is False
    assert report["movement_count"] == 9 and report["opening_count"] == 2
    for path in (
        "data/inventory/contract.py",
        "data/inventory/ledger.py",
        "data/inventory/legacy.py",
        "data/inventory/verify.py",
        "data/contracts/inventory_ledger.v1.schema.json",
    ):
        assert path in report["code_provenance"]["code_files"]


@pytest.mark.parametrize("invalid", [False, True])
def test_real_cli_exit_and_report(tmp_path, payload, invalid):
    if invalid:
        movement(payload, "sale")["quantity_delta"] = 100
    input_path, output = tmp_path / "input.json", tmp_path / "report.json"
    input_path.write_text(json.dumps(payload))
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "data.inventory.verify",
            "--input",
            str(input_path),
            "--occurred-through",
            END,
            "--output",
            str(output),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == (1 if invalid else 0), result.stderr
    report = json.loads(output.read_text())
    assert report["status"] == ("failed" if invalid else "passed")
