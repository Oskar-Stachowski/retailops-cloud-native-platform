"""Full canonical coverage, native return semantics and immutable arrival knowledge."""

from __future__ import annotations

import json
import shutil
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from data.anomalies.example import example_plan as anomaly_example
from data.anomalies.physical_scenarios import physical_example_plan
from data.anomalies.source_process import build_tables
from data.dq.contract import KINDS, parse_record as parse_v1, seal_record
from data.dq.full_contract import CAPTURE_VERSION, MAX_EVENTS, SCOPE, FullFaultPlan, binding_schema, capture_schema, parse_record, plan_schema
from data.dq.full_package import read_fixture, write_fixture
from data.dq.full_replay import FullOfflineReplay, totals
from data.dq.full_run import main
from data.dq.full_scenarios import capture, evaluate, example_plan
from data.dq.full_source import PROJECTION_TABLES, business_id, full_events, parent_facts, source_binding
from data.dq.package import MANIFEST, PATHS
from data.dq.source import load_source, sales_events
from data.generator.configuration import DatasetGenerationConfig
from data.generator.identity import canonical_json, file_sha256, json_sha256
from data.inventory.contract import utc_timestamp
from data.inventory.run_source_dataset import default_inventory_config
from data.inventory.source_dataset_io import artifact, write_source_dataset


@pytest.fixture(scope="module", params=["demand", "physical"])
def source(request, tmp_path_factory):
    root = tmp_path_factory.mktemp("full-dq-" + request.param)
    generation = DatasetGenerationConfig(profile="ai-smoke", days=30, products=8, stores=3, warehouses=2)
    config = default_inventory_config(generation)
    plan = (anomaly_example if request.param == "demand" else physical_example_plan)(generation)
    tables, context = build_tables(generation, plan, config)
    directory = write_source_dataset(tables, context, generation, config, root / "sources", scenario_plan=plan)
    tables, manifest = load_source(directory)
    events = full_events(tables, manifest)
    fault_plan = example_plan(events, manifest["dataset_id"])
    records, truth = capture(events, fault_plan, manifest["dataset_id"])
    replay, evaluation = evaluate(tables, manifest, events, records, truth)
    return directory, tables, manifest, events, fault_plan, records, truth, replay, evaluation


def delivery(event, offset=0, received=None):
    return seal_record({"contract_version": CAPTURE_VERSION, "kind": "event", "topic": "retailops.sales.v1",
                        "partition": 0, "offset": offset, "received_at": received or event["ingested_at"],
                        "body_utf8": canonical_json(event).decode()})


def reseal(record, **changes):
    return seal_record({**{k: v for k, v in record.items() if k != "record_id"}, **changes})


def hashes(root):
    return {p.relative_to(root).as_posix(): file_sha256(p) for p in root.rglob("*") if p.is_file()}


def test_contracts_are_separate_and_topic_types_stay_legacy():
    assert json.loads(Path("data/contracts/raw_dq_capture.v2.schema.json").read_text()) == capture_schema()
    assert json.loads(Path("data/contracts/raw_dq_plan.v2.schema.json").read_text()) == plan_schema()
    assert json.loads(Path("data/contracts/raw_dq_binding.v2.schema.json").read_text()) == binding_schema()
    from services.api.app.services.realtime_contract import event_contract
    contract = event_contract()
    assert contract["supported_schema_versions"] == ["1.0"] and len(contract["event_type_topics"]) == 13


def test_all_canonical_facts_including_native_return_tail_and_rejected_claims(source):
    _, tables, manifest, events, *_ = source
    sales = [e for e in events if e["event_type"] == "sale_completed"]
    returns = [e for e in events if e["event_type"] == "return_completed"]
    assert {business_id(e) for e in sales} == {r["id"] for r in tables["sales"]}
    assert {business_id(e) for e in returns} == {r["id"] for r in tables["return_events"]}
    assert len(sales) > 1024 and len(returns) > 200
    assert max(e["occurred_at"] for e in returns) > max(e["occurred_at"] for e in sales)
    assert set(sales_events(tables, manifest, 256)[i]["event_id"] for i in range(256)) <= {e["event_id"] for e in sales}
    binding = source_binding(manifest, events)
    assert binding["source_event_count"] == binding["source_sales_count"] + binding["source_return_count"]
    assert binding["missing_grain_policy"] == "unknown_not_zero"
    assert binding["business_event_day_completeness"] == "not_qualified"
    assert binding["projection_tables"] == {n: manifest["descriptor"]["tables"][n] for n in PROJECTION_TABLES}


def test_six_missing_facts_are_localized_and_every_fault_of_each_type_is_reconciled(source):
    _, _, _, events, _, records, truth, replay, evaluation = source
    assert {(i["event_type"], i["issue_type"]) for i in truth} == {(t, k) for t in ("sale_completed", "return_completed") for k in KINDS}
    report = replay["report"]
    assert report["raw_events"] == len(events) + 4 and report["accepted"] == len(events) - 6
    assert report["duplicate_event"] == report["duplicate_business"] == report["late"] == report["out_of_order"] == 2
    assert report["quarantined"] == report["missing_parent_facts"] == 6
    assert sum(len(r["missing_business_ids"]) for r in replay["parent_fact_coverage"]) == 6
    assert all(i["passed"] for i in evaluation["injections"]) and all(evaluation["checks"].values())
    assert report["input_records"] == len(records)
    assert report["curated_completeness"] == "not_qualified" and report["transport_durability_proven"] is False


def test_native_routes_currency_and_status_are_not_inferred_from_wire_store_or_amount(source):
    _, tables, _, events, *_ = source
    native = {r["sale_id"]: r for r in tables["inventory_sales"]}
    returns = {r["id"]: r for r in tables["return_events"]}
    facts = parent_facts(tables, events)
    for (kind, identifier), fact in facts.items():
        original = native[identifier] if kind == "sale_completed" else native[returns[identifier]["sale_id"]]
        assert fact["selling_location_id"] == original["selling_location_id"]
        assert fact["stock_location_id"] == original["stock_location_id"]
        assert fact["currency"] == original["currency"]
        if kind == "return_completed":
            assert fact["status"] == returns[identifier]["status"]
    rejected = [f for f in facts.values() if f["status"] == "rejected"]
    assert rejected and all(f["amount"] == "0.00" for f in rejected)
    assert all(r["units"] == 0 and r["amount"] == "0.00" and r["rejected_units"] > 0 for r in totals(rejected))
    assert any(e["payload"]["store_id"] != facts[e["event_type"], business_id(e)]["selling_location_id"] for e in events)


def test_reader_needs_only_operational_allowlist_and_truth_does_not_enter_outputs(source):
    _, tables, manifest, events, _, records, _, expected, _ = source
    operational = {n: tables[n] for n in PROJECTION_TABLES}
    reader = FullOfflineReplay(operational, manifest)
    for record in records:
        reader.consume(record)
    assert reader.snapshot() == expected
    forbidden = {"injection_id", "seed", "issue_type", "expected_action", "latent_demand", "anomaly_label", "magnitude"}
    def keys(value):
        if isinstance(value, dict):
            return set(value) | set().union(*(keys(v) for v in value.values()))
        if isinstance(value, list):
            return set().union(*(keys(v) for v in value))
        return set()
    assert not forbidden & keys(expected)
    assert not forbidden & keys(source_binding(manifest, events))
    for record in records:
        assert not forbidden & keys(record)
        if record["kind"] == "event":
            assert not forbidden & keys(json.loads(record["body_utf8"]))


def test_arrivals_preserve_previous_asof_and_replay_twice_is_identical(source):
    _, tables, manifest, _, _, records, truth, expected, _ = source
    reader = FullOfflineReplay(tables, manifest)
    timing = {i["raw_ref"] for i in truth if i["issue_type"] in {"late_event", "out_of_order"}}
    for record in records:
        if record["record_id"] in timing:
            cutoff = (utc_timestamp(record["received_at"]) - timedelta(microseconds=1)).isoformat()
            before, old_revisions = reader.aggregates_as_of(cutoff), deepcopy(reader.revisions)
        reader.consume(record)
        if record["record_id"] in timing:
            assert reader.aggregates_as_of(cutoff) == before
            assert reader.revisions[:-1] == old_revisions
            assert reader.revisions[-1]["known_at"] == record["received_at"]
            assert reader.aggregates_as_of(record["received_at"]) != before
    assert reader.snapshot() == expected
    for record in records:
        reader.consume(record)
    assert reader.snapshot() == expected
    reader.snapshot()["accepted_facts"].clear()
    assert reader.snapshot() == expected


@pytest.mark.parametrize("change", ["money", "quantity", "private_field", "route", "clock", "event_id_collision"])
def test_valid_wire_but_wrong_parent_fact_is_quarantined(source, change):
    _, tables, manifest, events, *_ = source
    event = deepcopy(next(e for e in events if e["event_type"] == "return_completed"))
    if change == "money":
        event["payload"]["refund_amount"] = "0.01"
    elif change == "quantity":
        event["payload"]["quantity"] = "999"
    elif change == "private_field":
        event["payload"]["status"] = "refunded"
    elif change == "route":
        event["payload"]["store_id"] = str(uuid4())
    elif change == "clock":
        event["ingested_at"] = (utc_timestamp(event["ingested_at"]) + timedelta(seconds=1)).isoformat()
    else:
        event["event_id"] = events[0]["event_id"]
    reader = FullOfflineReplay(tables, manifest)
    assert reader.consume(delivery(event))["action"] == "quarantined"
    assert not reader.facts and reader.snapshot()["report"]["missing_parent_facts"] == len(events)


@pytest.mark.parametrize("body", ['[]', '{"a":NaN}', '{"a":1e999}', '{"a":"\\ud800"}', '{"a":1,"a":2}', '{"event_id":[],"schema_version":"1.0"}', '{broken'])
def test_malformed_event_is_safe_quarantine_without_body_leak(source, body):
    reader = FullOfflineReplay(source[1], source[2])
    record = reseal(delivery(source[3][0]), body_utf8=body)
    assert reader.consume(record)["action"] == "quarantined"
    assert all("body_utf8" not in r for r in reader.quarantine)


def test_capture_versions_offset_budget_delivery_and_frontier_guards(source):
    event = source[3][0]
    record = delivery(event)
    with pytest.raises(ValueError):
        parse_v1(record)
    with pytest.raises(ValueError):
        parse_record({k: v for k, v in record.items() if k != "contract_version"})
    with pytest.raises(ValueError):
        parse_record(reseal(record, offset=MAX_EVENTS))
    reader = FullOfflineReplay(source[1], source[2])
    with pytest.raises(ValueError, match="contiguous"):
        reader.consume(reseal(record, offset=1))
    before = (utc_timestamp(event["ingested_at"]) - timedelta(seconds=1)).isoformat()
    assert reader.consume(reseal(record, received_at=before))["reason"] == "fact_unavailable_at_delivery"
    marker = seal_record({"contract_version": CAPTURE_VERSION, "kind": "progress", "scope": SCOPE,
                          "after_offset": 0, "received_at": event["ingested_at"], "complete_through": event["occurred_at"]})
    reader.consume(marker)
    with pytest.raises(ValueError, match="did not advance"):
        reader.consume(reseal(marker, received_at=(utc_timestamp(event["ingested_at"])+timedelta(seconds=1)).isoformat()))
    assert reader.snapshot()["report"]["curated_completeness"] == "not_qualified"


def test_plan_cannot_select_a_partial_stream_or_overlap_targets(source):
    events, plan = source[3], source[4]
    payload = plan.model_dump()
    payload["event_limit"] -= 1
    with pytest.raises(ValueError, match="every canonical"):
        capture(events, FullFaultPlan.from_payload(payload), source[2]["dataset_id"])
    payload = plan.model_dump()
    payload["injections"][1]["target_event_id"] = payload["injections"][0]["target_event_id"]
    with pytest.raises(ValueError, match="Overlapping"):
        FullFaultPlan.from_payload(payload)


def test_clean_full_capture_has_parent_coverage_but_no_business_zero_or_inferred_watermark(source):
    reader = FullOfflineReplay(source[1], source[2])
    previous = utc_timestamp(source[3][0]["ingested_at"])
    for offset, event in enumerate(source[3]):
        previous = max(previous + timedelta(microseconds=1), utc_timestamp(event["ingested_at"]))
        reader.consume(delivery(event, offset=offset, received=previous.isoformat()))
    report = reader.snapshot()["report"]
    assert report["accepted"] == len(source[3]) and report["missing_parent_facts"] == 0
    assert report["declared_source_watermark"] is None
    assert report["curated_completeness"] == "not_qualified"
    assert all(r["status"] == "complete_parent_fact_coverage" for r in reader.coverage())
    assert all(r["business_event_day_completeness"] == "not_qualified" for r in reader.coverage())


def test_immutable_fixture_reuse_and_resealed_false_aggregate_rejected(source, tmp_path):
    parent, _, _, _, plan, *_ = source
    before = hashes(parent)
    directory = write_fixture(parent, plan, tmp_path / "full")
    published = hashes(directory)
    assert write_fixture(parent, plan, tmp_path / "full") == directory
    assert hashes(directory) == published and hashes(parent) == before
    copied = Path(shutil.copytree(directory, tmp_path / "tampered"))
    path = copied / "curated/replay.json"
    replay = json.loads(path.read_text())
    replay["final_aggregates"][0]["units"] += 1
    path.write_bytes(canonical_json(replay) + b"\n")
    manifest = json.loads((copied / MANIFEST).read_text())
    manifest["descriptor"]["artifacts"]["curated/replay.json"] = artifact(path, copied)
    manifest["fixture_id"] = "raw-dq-sha256-" + json_sha256(manifest["descriptor"])
    (copied / MANIFEST).write_bytes(canonical_json(manifest) + b"\n")
    with pytest.raises(ValueError, match="independent source/plan replay"):
        read_fixture(copied, parent)
    assert {p.relative_to(directory).as_posix() for p in directory.rglob("*") if p.is_file()} == {*PATHS, MANIFEST}


@pytest.mark.parametrize("mode", ["source", "fixture", "plan"])
def test_cli_receipt_cannot_overwrite_protected_inputs(tmp_path, monkeypatch, mode):
    source, fixture = tmp_path / "source", tmp_path / "fixture"
    source.mkdir(); fixture.mkdir()
    protected = (source if mode == "source" else fixture) / "receipt.json"
    protected.write_bytes(b"sentinel\n")
    arguments = ["--source-dir", str(source), "--output", str(protected)]
    arguments += ["--plan", str(protected), "--output-root", str(fixture)] if mode == "plan" else ["--verify", str(fixture)]
    monkeypatch.setattr("sys.argv", ["full_run", *arguments])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2 and protected.read_bytes() == b"sentinel\n"
