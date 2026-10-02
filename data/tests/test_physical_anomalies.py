from __future__ import annotations

import json
from collections import Counter
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from data.anomalies.candidate_io import PATHS, read_candidate, write_candidate
from data.anomalies.physical_contract import PhysicalAnomalyPlan, physical_plan_schema
from data.anomalies.physical_scenarios import build_physical_scenario, physical_example_plan
from data.generator.configuration import DatasetGenerationConfig, resolve_generation_config
from data.generator.identity import canonical_json, json_sha256
from data.generator.main import build_dataset
from data.generator.return_events import generate_return_events
from data.generator.simulation import simulation_entities
from data.inventory.contract import utc_timestamp
from data.inventory.source_dataset_io import artifact


@pytest.fixture(scope="module")
def generation():
    return DatasetGenerationConfig(profile="ai-smoke", days=30, products=8, stores=3, warehouses=2)


@pytest.fixture(scope="module")
def plan(generation):
    return physical_example_plan(generation)


@pytest.fixture(scope="module")
def sample(generation, plan):
    return build_physical_scenario(generation, plan)


def test_physical_schema_is_versioned_and_demand_v1_stays_separate(plan):
    schema = physical_plan_schema()
    assert (
        json.loads(Path("data/contracts/business_physical_anomaly_plan.v1.schema.json").read_text())
        == schema
    )
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(plan)
    from data.anomalies.contract import AnomalyPlan

    with pytest.raises(ValueError):
        AnomalyPlan.from_payload(plan)


@pytest.mark.parametrize(
    "fault",
    [
        "wrong_seed",
        "overlap",
        "negative_cap",
        "fractional_cap",
        "false_return_field",
        "neutral_multiplier",
        "wrong_stock",
        "future_window",
        "unknown_type",
        "wrong_version",
        "same_product",
        "later_control",
        "oversized_window",
        "nonclean_control",
    ],
)
def test_ambiguous_physical_intervention_is_rejected(plan, generation, fault):
    value = deepcopy(plan)
    returns = next(i for i in value["injections"] if i["injection_type"] == "return_spike")
    cap = next(
        i for i in value["injections"] if i["injection_type"] == "inventory_censored_episode"
    )
    control = next(c for c in value["controls"] if c["product_id"] == cap["product_id"])
    if fault == "wrong_seed":
        cap["seed"] += 1
    elif fault == "overlap":
        control.update(start_date=cap["start_date"], end_date=cap["end_date"])
    elif fault == "negative_cap":
        cap["magnitude"] = -1
    elif fault == "fractional_cap":
        cap["magnitude"] = 0.5
    elif fault == "false_return_field":
        returns["affected_fields"] = []
    elif fault == "neutral_multiplier":
        returns["magnitude"] = "1"
    elif fault == "wrong_stock":
        cap["stock_location_id"] = "00000000-0000-4000-8000-000000000001"
    elif fault == "future_window":
        cap.update(start_date="2027-01-01", end_date="2027-01-01")
    elif fault == "unknown_type":
        cap["injection_type"] = "label_only"
    elif fault == "wrong_version":
        value["contract_version"] = "business-physical-anomaly-plan-2.0.0"
    elif fault == "same_product":
        cap["product_id"] = returns["product_id"]
        control["product_id"] = returns["product_id"]
    elif fault == "later_control":
        control.update(start_date="2026-07-29", end_date="2026-07-30")
    elif fault == "oversized_window":
        cap.update(start_date="2020-01-01", end_date="2026-07-31")
    else:
        control["control_type"] = "promotion"
    with pytest.raises(ValueError):
        if fault in {"wrong_stock", "future_window"}:
            build_physical_scenario(generation, value)
        else:
            PhysicalAnomalyPlan.from_payload(value)


def test_return_spike_changes_real_returns_without_exceeding_purchase(sample):
    episode = next(
        e for e in sample["effects"]["episodes"] if e["injection_type"] == "return_spike"
    )
    assert (
        episode["injected_returns"]["returned_units"] > episode["normal_returns"]["returned_units"]
    )
    sales = {r["id"]: r for r in sample["commerce"]["sales"]}
    quantity = Counter()
    for event in sample["commerce"]["return_events"]:
        sale = sales[event["sale_id"]]
        quantity[event["sale_id"]] += int(event["quantity"])
        assert utc_timestamp(sale["sold_at"]) < utc_timestamp(event["returned_at"])
        assert (
            utc_timestamp(event["returned_at"])
            <= utc_timestamp(event["ingested_at"])
            <= utc_timestamp(event["available_at"])
        )
        assert quantity[event["sale_id"]] <= int(sale["quantity"])


def test_return_probability_selection_is_scoped_and_preserves_default_events(generation, plan):
    tables = build_dataset(generation)
    tables["products"] = simulation_entities(tables, "products")
    effective = resolve_generation_config(generation)
    baseline = generate_return_events(tables, effective)
    assert baseline == generate_return_events(tables, effective, return_factors={})
    assert baseline == generate_return_events(
        tables,
        effective,
        return_factors={("1900-01-01", "unknown", "unknown", "store"): "20"},
    )
    factors = PhysicalAnomalyPlan.from_payload(plan).return_factors()
    boosted = generate_return_events(tables, effective, return_factors=factors)
    normal_ids = {e["id"]: e for e in baseline}
    boosted_ids = {e["id"]: e for e in boosted}
    assert all(boosted_ids.get(event_id) == event for event_id, event in normal_ids.items())
    additions = [e for e in boosted if e["id"] not in normal_ids]
    assert additions
    for event in additions:
        key = (
            event["returned_at"][:10],
            event["product_id"],
            event["selling_location_id"],
            event["channel"],
        )
        assert key in factors
    purchased = {s["id"]: int(s["quantity"]) for s in tables["sales"]}
    returned = Counter()
    for event in boosted:
        returned[event["sale_id"]] += int(event["quantity"])
        assert returned[event["sale_id"]] <= purchased[event["sale_id"]]


def test_two_return_windows_on_shared_product_are_rejected(plan):
    value = deepcopy(plan)
    spike = next(i for i in value["injections"] if i["injection_type"] == "return_spike")
    value["injections"] = [
        spike,
        {
            **spike,
            "id": "00000000-0000-4000-8000-000000000002",
            "channel": "store" if spike["channel"] != "store" else "online",
        },
    ]
    control = next(c for c in value["controls"] if c["product_id"] == spike["product_id"])
    value["controls"] = [
        control,
        {
            **control,
            "id": "00000000-0000-4000-8000-000000000003",
            "channel": value["injections"][1]["channel"],
        },
    ]
    with pytest.raises(ValueError, match="shared-stock spillover"):
        PhysicalAnomalyPlan.from_payload(value)


def test_stock_cap_is_physical_shared_stock_and_keeps_latent_demand(sample):
    episode = next(
        e
        for e in sample["effects"]["episodes"]
        if e["injection_type"] == "inventory_censored_episode"
    )
    before, after = episode["normal_inventory_outcome"], episode["injected_inventory_outcome"]
    assert before["latent_quantity"] == after["latent_quantity"] > 0
    assert after["observed_quantity"] == 0 < before["observed_quantity"]
    assert after["lost_sales_quantity"] > before["lost_sales_quantity"]
    assert episode["removed_quantity"] > 0
    movements = {r["inventory_event_id"]: r for r in sample["inventory"]["ledger"]["movements"]}
    for event_id in episode["write_off_event_ids"]:
        event = movements[event_id]
        assert event["movement_type"] == event["source_process"] == "write_off"
        assert event["quantity_delta"] < 0
        assert event["source_reference"] != episode["id"]
    outcomes = sample["simulation_truth"]["process"]["demand_outcomes"]
    scoped = [
        r
        for r in outcomes
        if r["product_id"] == episode["product_id"]
        and r["stock_location_id"] == episode["stock_location_id"]
        and episode["start_date"] <= r["occurred_at"][:10] <= episode["end_date"]
    ]
    assert scoped
    assert all(r["stock_before"] == r["observed_quantity"] == 0 for r in scoped)
    reconciliation = sample["reconciliation"]
    assert (
        reconciliation["latent_quantity"]
        == reconciliation["observed_quantity"] + reconciliation["lost_sales_quantity"]
    )


def test_clean_controls_remain_unchanged_and_spillovers_are_reported(sample):
    assert all(
        c["normal_inventory_outcome"] == c["injected_inventory_outcome"]
        and c["normal_returns"] == c["injected_returns"]
        for c in sample["effects"]["controls"]
    )
    assert sample["effects"]["observed_sales_changes"]
    assert sample["source_ready"] is sample["model_ready"] is sample["anomaly_ready"] is False


def test_physical_repeat_and_permutation_preserve_candidate(generation, plan, sample):
    changed = deepcopy(plan)
    changed["injections"].reverse()
    changed["controls"].reverse()
    assert build_physical_scenario(generation, changed) == sample


def test_ineffective_cap_is_not_accepted_as_an_episode(generation, plan):
    value = deepcopy(plan)
    next(i for i in value["injections"] if i["injection_type"] == "inventory_censored_episode")[
        "magnitude"
    ] = 1000000
    with pytest.raises(ValueError, match="no actual censoring effect"):
        build_physical_scenario(generation, value)


def test_no_private_parameters_in_physical_facts(sample):
    forbidden = {
        "injection_id",
        "injection_type",
        "magnitude",
        "seed",
        "return_selection_probability",
        "latent_units",
        "anomaly_factor",
    }
    for rows in sample["commerce"].values():
        assert all(not forbidden.intersection(row) for row in rows)
    assert all(
        not forbidden.intersection(row) for row in sample["inventory"]["ledger"]["movements"]
    )


def test_independent_replay_rejects_resealed_physical_labels(tmp_path, sample):
    directory = write_candidate(sample, tmp_path / "candidate")
    manifest = read_candidate(directory)
    assert write_candidate(sample, tmp_path / "candidate") == directory
    injection_path = directory / PATHS[2]
    payload = json.loads(injection_path.read_text())
    payload["episodes"][0]["affected_daily_grains"] += 1
    injection_path.write_bytes(canonical_json(payload) + b"\n")
    manifest["artifacts"][PATHS[2]] = artifact(directory / PATHS[2], directory)
    manifest["descriptor"]["artifacts"] = manifest["artifacts"]
    manifest["candidate_id"] = "anomaly-candidate-sha256-" + json_sha256(manifest["descriptor"])
    (directory / "scenario_manifest.json").write_bytes(canonical_json(manifest) + b"\n")
    with pytest.raises(ValueError, match="independent process replay"):
        read_candidate(directory)
