from __future__ import annotations

import copy
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from data.generator.common import deterministic_uuid
from data.generator.identity import json_sha256
from data.inventory.ledger import InventoryLedger, InventoryMovement
from data.inventory.projection import project_inventory, reconcile_projection
from data.inventory.projection_contract import (
    ProjectionConfig,
    projection_config_schema,
    projection_schema,
)
from data.inventory.run_inventory_projection import run
from data.inventory.snapshots import daily_snapshots, snapshot_at
from data.inventory.stockout import diagnose_windows, stockout_episodes
from data.inventory.simulator import ChronologicalSimulator
from data.inventory.run_simulation import run as run_simulation

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
EVALUATION = "2026-07-11T00:00:00Z"


@pytest.fixture
def inputs():
    return {k: json.loads((FIXTURES / v).read_text()) for k, v in NAMES.items()}


@pytest.fixture
def config():
    return json.loads((FIXTURES / "inventory-projection-config-v1.json").read_text())


def simulate(inputs):
    return ChronologicalSimulator(
        inputs["ledger"],
        inputs["supply"],
        inputs["scenario"],
        inputs["policy"],
        inputs["fulfillment"],
        inputs["truth"],
    ).execute()


def project(inputs, config, evaluated_at=EVALUATION):
    parent = simulate(inputs)
    result = project_inventory(
        parent["operational"],
        parent["simulation_truth"],
        ProjectionConfig.from_payload(config),
        evaluated_at=evaluated_at,
    )
    return result, parent


def test_snapshot_and_window_indexes_avoid_scope_times_ledger_scans(inputs, config, monkeypatch):
    parent = simulate(inputs)
    ledger = InventoryLedger.from_payload(parent["operational"]["ledger"])
    position = InventoryMovement.position.fget
    calls = []

    def counted(movement):
        calls.append(movement.inventory_event_id)
        return position(movement)

    monkeypatch.setattr(InventoryMovement, "position", property(counted))
    cutoff = "2026-07-08T23:59:59.999999Z"
    snapshot_at(ledger, snapshot_time=cutoff, as_of_time=cutoff)
    assert len(calls) <= 2 * len(ledger.movements)
    calls.clear()
    diagnose_windows(
        ledger,
        ProjectionConfig.from_payload(config),
        [],
        origin=cutoff,
        evaluated_at=EVALUATION,
    )
    assert len(calls) <= 2 * len(ledger.movements)


def test_daily_snapshots_and_physical_balances_reconcile_every_grain(inputs, config):
    result, parent = project(inputs, config)
    assert reconcile_projection(result, parent["operational"], parent["simulation_truth"]) == {
        "snapshots": 18,
        "physical_daily_balances": 18,
        "stockout_episodes": 3,
        "right_censored_episodes": 0,
        "lost_sales_impacts": 1,
        "lost_sales_quantity": 4,
        "window_diagnostics": 18,
    }
    assert [r["on_hand"] for r in result["operational"][:4]] == [0, 0, 1, 0]
    assert [
        r["closing_quantity"] for r in result["simulation_truth"]["physical_daily_balances"][-2:]
    ] == [24, 6]
    for row in result["operational"]:
        assert row["reserved_qty"] == 0 and row["available_qty"] == row["on_hand"]
        assert row["snapshot_at"].endswith("23:59:59.999999+00:00")
        assert row["snapshot_at"] == row["as_of_time"]
        assert row["source_available_at"] <= row["as_of_time"]
    for row in result["simulation_truth"]["physical_daily_balances"]:
        assert (
            row["closing_quantity"]
            == row["balance_before_period"] + row["opening_quantity"] + row["movement_delta"]
        )
    assert (
        sum(r["opening_quantity"] for r in result["simulation_truth"]["physical_daily_balances"])
        == 8
    )
    assert result["operational"][-2:][0]["on_hand"] == 24


def test_daily_projection_verification_does_not_rescan_ledger_per_snapshot(inputs, config):
    from data.inventory.projection import _reconcile_daily

    output, parent = project(inputs, config)
    ledger = InventoryLedger.from_payload(parent["operational"]["ledger"])

    class CountedTuple(tuple):
        def __iter__(self):
            self.scans += 1
            return super().__iter__()

    counted = CountedTuple(ledger.movements)
    counted.scans = 0
    assert len(output["operational"]) > 1
    _reconcile_daily(
        output, replace(ledger, movements=counted), ProjectionConfig.from_payload(config)
    )
    assert counted.scans == 1


def test_episode_boundaries_duration_and_lost_sales_are_physical(inputs, config):
    result, _ = project(inputs, config)
    episodes = result["simulation_truth"]["stockout_episodes"]
    assert [r["duration_microseconds"] for r in episodes] == [302400000000, 82800000000, 3600000000]
    assert [r["lost_sales_quantity"] for r in episodes] == [0, 4, 0]
    assert episodes[0]["left_censored"] is True and episodes[0]["onset_kind"] == "opening_zero"
    assert not any(r["right_censored"] for r in episodes)
    impact = result["simulation_truth"]["lost_sales_impacts"][0]
    assert impact["demand_id"] == inputs["scenario"]["demand_arrivals"][1]["demand_id"]
    assert impact["channel"] == "online" and impact["lost_sales_quantity"] == 4
    assert episodes[1]["affected_demand_count"] == 1


def test_poor_supply_has_more_episodes_and_exact_loss_attribution(inputs, config):
    for row in inputs["truth"]["suppliers"]:
        row["reliability"] = "0"
    result, _ = project(inputs, config)
    assert len(result["simulation_truth"]["stockout_episodes"]) == 5
    assert len(result["simulation_truth"]["lost_sales_impacts"]) == 4
    assert (
        sum(r["lost_sales_quantity"] for r in result["simulation_truth"]["stockout_episodes"]) == 19
    )


def test_zero_duration_episode_preserves_sequence_and_depleting_arrival_loss(inputs, config):
    event = inputs["scenario"]["return_events"][0]
    event.update(
        returned_at="2026-07-01T10:00:00Z",
        ingested_at="2026-07-01T10:00:00Z",
        available_at="2026-07-01T10:00:00Z",
        sequence=12,
    )
    inputs["scenario"]["return_events"] = [event]
    inputs["scenario"]["inventory_actions"] = []
    result, _ = project(inputs, config)
    instant = next(
        r
        for r in result["simulation_truth"]["stockout_episodes"]
        if r["duration_microseconds"] == 0
    )
    assert instant["start_at"] == instant["end_at"]
    assert (instant["start_sequence"], instant["end_sequence"]) == (11, 12)
    assert instant["lost_sales_quantity"] == 4


def test_no_sales_is_not_stockout_when_inventory_is_positive(inputs, config):
    inputs["scenario"]["return_events"] = []
    inputs["scenario"]["inventory_actions"] = []
    for demand in inputs["scenario"]["demand_arrivals"]:
        demand["latent_quantity"] = 0
    for rule in inputs["policy"]["rules"]:
        rule.update(reorder_point=0, safety_stock=0)
    result, _ = project(inputs, config)
    episodes = result["simulation_truth"]["stockout_episodes"]
    assert (
        len(episodes) == 1
        and episodes[0]["stock_location_id"] == inputs["ledger"]["stock_locations"][1]["id"]
    )
    assert episodes[0]["right_censored"] is True and episodes[0]["end_at"] is None
    assert episodes[0]["duration_microseconds"] == 9 * 86400 * 1000000
    assert (
        episodes[0]["lost_sales_quantity"] == 0
        and result["simulation_truth"]["lost_sales_impacts"] == []
    )


def test_unknown_opening_is_null_instead_of_zero(inputs, config):
    for row in inputs["ledger"]["movements"]:
        row["available_at"] = "2026-07-11T00:00:00Z"
    result, _ = project(inputs, config)
    assert all(
        r["status"] == "not_available" and r["on_hand"] is None and r["reserved_qty"] is None
        for r in result["operational"]
    )
    assert all(
        r["status"] == "not_evaluable"
        and r["reason"] == "inventory_unknown"
        and r["incident_stockout"] is None
        for r in result["simulation_truth"]["window_diagnostics"]
    )


def test_late_receipt_does_not_change_historical_snapshot(inputs):
    parent = simulate(inputs)
    ledger = InventoryLedger.from_payload(parent["operational"]["ledger"])
    cutoff = "2026-07-05T00:02:00Z"
    before = snapshot_at(ledger, snapshot_time=cutoff, as_of_time=cutoff)
    assert [r["on_hand"] for r in before] == [1, 1]
    later = snapshot_at(ledger, snapshot_time=cutoff, as_of_time="2026-07-05T00:03:00Z")
    assert [r["on_hand"] for r in later] == [11, 9]
    assert before == snapshot_at(ledger, snapshot_time=cutoff, as_of_time=cutoff)
    assert [r["snapshot_id"] for r in before] != [r["snapshot_id"] for r in later]


def test_future_and_late_business_events_do_not_rewrite_previous_origin(inputs):
    parent = simulate(inputs)
    payload = copy.deepcopy(parent["operational"]["ledger"])
    ledger = InventoryLedger.from_payload(payload)
    cutoff = "2026-07-02T23:59:59.999999Z"
    before = snapshot_at(ledger, snapshot_time=cutoff, as_of_time=cutoff)
    action = copy.deepcopy(inputs["scenario"]["inventory_actions"][0])
    action.update(
        inventory_event_id=deterministic_uuid("movement", "late-snapshot"),
        occurred_at="2026-07-02T15:00:00Z",
        ingested_at="2026-07-09T00:00:00Z",
        available_at="2026-07-09T00:00:00Z",
        sequence=50,
    )
    payload["movements"].append(action)
    assert before == snapshot_at(
        InventoryLedger.from_payload(payload), snapshot_time=cutoff, as_of_time=cutoff
    )
    action.update(occurred_at="2026-07-09T00:00:00Z")
    assert before == snapshot_at(
        InventoryLedger.from_payload(payload), snapshot_time=cutoff, as_of_time=cutoff
    )


def test_midnight_receipt_belongs_to_new_day(inputs, config):
    result, _ = project(inputs, config)
    fourth = [r for r in result["operational"] if r["business_date"] == "2026-07-04"]
    fifth = [r for r in result["operational"] if r["business_date"] == "2026-07-05"]
    assert [r["on_hand"] for r in fourth] == [1, 1]
    assert [r["on_hand"] for r in fifth] == [1, 9]


def test_partial_days_are_explicit_and_do_not_repeat_opening(inputs, config):
    parent = simulate(inputs)
    payload = parent["operational"]["ledger"]
    payload["opening_at"] = "2026-07-01T06:00:00Z"
    for row in payload["movements"]:
        if row["movement_type"] == "opening_stock":
            row.update(
                occurred_at="2026-07-01T06:00:00Z",
                ingested_at="2026-07-01T06:00:00Z",
                available_at="2026-07-01T06:00:00Z",
            )
    config.update(start_at="2026-07-01T06:00:00Z", end_at="2026-07-09T18:00:00Z")
    rows = daily_snapshots(
        InventoryLedger.from_payload(payload), ProjectionConfig.from_payload(config)
    )
    assert len(rows) == 18
    assert not rows[0]["is_full_business_day"] and not rows[-1]["is_full_business_day"]
    assert rows[0]["period_from_at"] == "2026-07-01T06:00:00+00:00"
    assert rows[-1]["snapshot_at"] == "2026-07-09T17:59:59.999999+00:00"


def boundary_ledger(inputs, config, onset="2026-07-08T00:00:00Z"):
    payload = copy.deepcopy(inputs["ledger"])
    payload["movements"][0]["quantity_delta"] = 10
    payload["movements"][1]["quantity_delta"] = 5
    movement = copy.deepcopy(inputs["scenario"]["inventory_actions"][0])
    movement.update(
        inventory_event_id=deterministic_uuid("boundary", "onset"),
        occurred_at=onset,
        ingested_at=onset,
        available_at=onset,
        quantity_delta=-10,
    )
    payload["movements"].append(movement)
    recovery = copy.deepcopy(inputs["scenario"]["inventory_actions"][-1])
    recovery.update(
        inventory_event_id=deterministic_uuid("boundary", "recovery"),
        occurred_at="2026-07-09T00:00:00Z",
        ingested_at="2026-07-09T00:00:00Z",
        available_at="2026-07-09T00:00:00Z",
        quantity_delta=2,
    )
    payload["movements"].append(recovery)
    config["end_at"] = "2026-07-12T00:00:00Z"
    parsed = ProjectionConfig.from_payload(config)
    ledger = InventoryLedger.from_payload(payload)
    episodes, _ = stockout_episodes(ledger, parsed, [])
    return ledger, parsed, episodes


@pytest.mark.parametrize(
    "onset,expected",
    [
        ("2026-07-08T00:00:00Z", 1),
        ("2026-07-08T00:00:00.000001Z", 0),
        ("2026-07-07T23:59:59.999999Z", 1),
    ],
)
def test_incident_window_right_boundary_is_inclusive(inputs, config, onset, expected):
    ledger, parsed, episodes = boundary_ledger(inputs, config, onset)
    rows = diagnose_windows(
        ledger, parsed, episodes, origin="2026-07-01T00:00:00Z", evaluated_at=EVALUATION
    )
    assert rows[0]["status"] == "evaluable" and rows[0]["incident_stockout"] == expected
    assert rows[1]["incident_stockout"] == 0


def test_zero_at_origin_is_already_stockout_and_has_no_incident_label(inputs, config):
    ledger, parsed, episodes = boundary_ledger(inputs, config)
    row = diagnose_windows(
        ledger, parsed, episodes, origin="2026-07-08T00:00:00Z", evaluated_at=EVALUATION
    )[0]
    assert row["status"] == "already_stockout" and row["incident_stockout"] is None
    assert row["label_available_at"] is None


@pytest.mark.parametrize(
    "evaluation,status",
    [
        ("2026-07-08T00:02:59.999999Z", "not_evaluable"),
        ("2026-07-08T00:03:00Z", "evaluable"),
    ],
)
def test_full_window_must_mature_before_evaluation(inputs, config, evaluation, status):
    ledger, parsed, episodes = boundary_ledger(inputs, config)
    row = diagnose_windows(
        ledger, parsed, episodes, origin="2026-07-01T00:00:00Z", evaluated_at=evaluation
    )[0]
    assert row["status"] == status
    assert row["label_available_at"] == "2026-07-08T00:03:00+00:00"
    assert row["incident_stockout"] == (1 if status == "evaluable" else None)


def test_exclusive_observation_end_does_not_make_a_negative_label(inputs, config):
    ledger, parsed, episodes = boundary_ledger(inputs, config)
    rows = diagnose_windows(
        ledger, parsed, episodes, origin="2026-07-05T00:00:00Z", evaluated_at="2026-07-20T00:00:00Z"
    )
    assert all(
        r["status"] == "not_evaluable"
        and r["reason"] == "incomplete_window"
        and r["incident_stockout"] is None
        for r in rows
    )


def test_unavailable_origin_state_is_separate_from_current_zero(inputs, config):
    ledger, parsed, _ = boundary_ledger(inputs, config)
    payload = copy.deepcopy(inputs["ledger"])
    payload["movements"][0]["quantity_delta"] = 10
    payload["movements"][1]["quantity_delta"] = 5
    movement = next(m for m in ledger.movements if m.movement_type == "write_off").record()
    movement["available_at"] = "2026-07-10T00:00:00Z"
    payload["movements"].append(movement)
    late = InventoryLedger.from_payload(payload)
    episodes, _ = stockout_episodes(late, parsed, [])
    row = diagnose_windows(
        late, parsed, episodes, origin="2026-07-08T00:00:00Z", evaluated_at=EVALUATION
    )[0]
    assert row["status"] == "not_evaluable" and row["reason"] == "origin_state_unavailable"
    assert row["incident_stockout"] is None


def test_projection_is_deterministic_and_truth_delay_cannot_change_operational_snapshot(
    inputs, config
):
    baseline, _ = project(inputs, config)
    repeated, _ = project(inputs, config)
    assert json_sha256(baseline) == json_sha256(repeated)
    config["truth_delay_seconds"] = 86400
    delayed, _ = project(inputs, config)
    assert delayed["operational"] == baseline["operational"]
    assert delayed["simulation_truth"] != baseline["simulation_truth"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("truth_delay_seconds", True),
        ("truth_delay_seconds", -1),
        ("truth_delay_seconds", "180"),
        ("diagnostic_horizon_days", 8),
        ("stock_measure", "on_hand"),
        ("reservation_policy", "reserve"),
        ("business_timezone", "Europe/Warsaw"),
        ("start_at", "2026-02-30T00:00:00Z"),
        ("end_at", "2026-07-01T00:00:00Z"),
        ("episode_policy", "positive_duration_only"),
    ],
)
def test_invalid_configuration_is_rejected(config, field, value):
    config[field] = value
    with pytest.raises(ValueError):
        ProjectionConfig.from_payload(config)


@pytest.mark.parametrize(
    "field", ["truth_delay_seconds", "snapshot_policy", "stock_measure", "episode_policy"]
)
def test_configuration_has_no_implicit_required_policy(config, field):
    del config[field]
    with pytest.raises(ValueError):
        ProjectionConfig.from_payload(config)


@pytest.mark.parametrize(
    "mutation",
    [
        "wrong_snapshot",
        "missing_snapshot",
        "duplicate_snapshot",
        "unknown_as_zero",
        "wrong_cutoff",
        "wrong_lineage",
        "wrong_snapshot_id",
        "wrong_unit",
        "physical_balance",
        "repeated_opening",
        "missing_episode",
        "duplicate_episode",
        "wrong_episode_onset",
        "wrong_recovery",
        "wrong_duration",
        "wrong_censoring",
        "wrong_maturity",
        "missing_impact",
        "duplicate_impact",
        "wrong_impact_episode",
        "wrong_episode_loss",
        "missing_diagnostic",
        "false_negative_tail",
        "fake_bool_label",
    ],
)
def test_corrupted_projections_fail_independent_reconciliation(inputs, config, mutation):
    result, parent = project(inputs, config)
    snapshots = result["operational"]
    truth = result["simulation_truth"]
    episodes = truth["stockout_episodes"]
    if mutation == "wrong_snapshot":
        snapshots[0]["on_hand"] = 99
    elif mutation == "missing_snapshot":
        snapshots.pop()
    elif mutation == "duplicate_snapshot":
        snapshots.append(copy.deepcopy(snapshots[0]))
    elif mutation == "unknown_as_zero":
        snapshots[0].update(status="not_available", on_hand=0)
    elif mutation == "wrong_cutoff":
        snapshots[0]["snapshot_at"] = "2026-07-02T00:00:00Z"
    elif mutation == "wrong_lineage":
        snapshots[0]["source_available_at"] = "2026-07-02T00:00:00Z"
    elif mutation == "wrong_snapshot_id":
        snapshots[0]["snapshot_id"] = deterministic_uuid("wrong", "snapshot")
    elif mutation == "wrong_unit":
        snapshots[0]["unit_of_measure"] = "kg"
    elif mutation == "physical_balance":
        truth["physical_daily_balances"][0]["closing_quantity"] = 99
    elif mutation == "repeated_opening":
        truth["physical_daily_balances"][2]["opening_quantity"] = 8
    elif mutation == "missing_episode":
        episodes.pop()
    elif mutation == "duplicate_episode":
        episodes.append(copy.deepcopy(episodes[0]))
    elif mutation == "wrong_episode_onset":
        episodes[0]["start_at"] = "2026-07-01T10:00:00Z"
    elif mutation == "wrong_recovery":
        episodes[0]["end_at"] = "2026-07-05T00:00:00Z"
    elif mutation == "wrong_duration":
        episodes[0]["duration_microseconds"] = 0
    elif mutation == "wrong_censoring":
        episodes[0]["right_censored"] = True
    elif mutation == "wrong_maturity":
        episodes[0]["diagnostic_available_at"] = episodes[0]["start_at"]
    elif mutation == "missing_impact":
        truth["lost_sales_impacts"] = []
    elif mutation == "duplicate_impact":
        truth["lost_sales_impacts"].append(copy.deepcopy(truth["lost_sales_impacts"][0]))
    elif mutation == "wrong_impact_episode":
        truth["lost_sales_impacts"][0]["episode_id"] = episodes[0]["episode_id"]
    elif mutation == "wrong_episode_loss":
        episodes[1]["lost_sales_quantity"] = 99
    elif mutation == "missing_diagnostic":
        truth["window_diagnostics"].pop()
    elif mutation == "false_negative_tail":
        truth["window_diagnostics"][-1].update(status="evaluable", incident_stockout=0, reason=None)
    else:
        truth["window_diagnostics"][-1]["incident_stockout"] = False
    with pytest.raises(ValueError):
        reconcile_projection(result, parent["operational"], parent["simulation_truth"])


@pytest.mark.parametrize(
    "name,factory",
    [
        ("inventory_projection_config", projection_config_schema),
        ("inventory_projection", projection_schema),
    ],
)
def test_published_schemas_match_strict_runtime(name, factory):
    assert (
        json.loads((ROOT / "data/contracts" / (name + ".v1.schema.json")).read_text()) == factory()
    )


def test_real_cli_parent_hashes_and_model_readiness(inputs, config, tmp_path):
    paths = {}
    for key, payload in inputs.items():
        paths[key] = tmp_path / (key + ".json")
        paths[key].write_text(json.dumps(payload))
    parent = run_simulation(
        paths["scenario"],
        paths["ledger"],
        paths["supply"],
        paths["policy"],
        paths["fulfillment"],
        paths["truth"],
    )
    source = tmp_path / "simulation.json"
    source.write_text(json.dumps(parent))
    config_path = tmp_path / "projection-config.json"
    config_path.write_text(json.dumps(config))
    output = tmp_path / "projection.json"
    command = [
        sys.executable,
        "-m",
        "data.inventory.run_inventory_projection",
        "--simulation",
        str(source),
        "--config",
        str(config_path),
        "--evaluated-at",
        EVALUATION,
        "--output",
        str(output),
    ]
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=30)
    assert completed.returncode == 0, completed.stderr
    report = json.loads(output.read_text())
    assert report["status"] == "passed" and report["inventory_ready"] is False
    assert report["stockout_model_readiness"]["label_diagnostics_status"] == "not_evaluable"
    assert report["stockout_model_readiness"]["model_ready"] is False
    assert report["stockout_model_readiness"]["reason"] == "single_class"
    assert report["reconciliation"]["snapshots"] == 18
    assert report["seconds"] > 0 and report["peak_rss_mib"] > 0
    assert report["code_provenance"]["code_sha256"]
    parent["operational"]["sales"][0]["quantity"] = 99
    source.write_text(json.dumps(parent))
    with pytest.raises(ValueError, match="hash mismatch"):
        run(source, config_path, evaluated_at=EVALUATION)
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=30)
    assert completed.returncode == 1 and json.loads(output.read_text())["status"] == "failed"
