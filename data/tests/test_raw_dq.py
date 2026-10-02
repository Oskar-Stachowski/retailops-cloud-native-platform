from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from data.dq.contract import TOPIC, FaultPlan, capture_schema, parse_record, plan_schema, seal_record
from data.dq.package import MANIFEST, PATHS, read_fixture, write_fixture
from data.dq.replay import OfflineReplay
from data.dq.sales import PAYLOAD_FIELDS, fact_totals, sale_fact
from data.dq.scenarios import KINDS, capture, evaluate, example_plan
from data.dq.source import load_source, sales_events
from data.generator.configuration import DatasetGenerationConfig
from data.generator.identity import canonical_json, file_sha256, json_sha256
from data.inventory.contract import utc_timestamp
from data.inventory.run_source_dataset import build_source_dataset, default_inventory_config
from data.inventory.source_dataset_io import artifact, write_source_dataset
from services.api.app.services.realtime_contract import event_contract, validate_event


@pytest.fixture(scope="module")
def source(tmp_path_factory):
    root = tmp_path_factory.mktemp("dq-parent")
    generation = DatasetGenerationConfig(profile="ai-smoke", days=14, products=8, stores=3, warehouses=2)
    config = default_inventory_config(generation)
    tables, context = build_source_dataset(generation, config)
    directory = write_source_dataset(tables, context, generation, config, root)
    tables, manifest = load_source(directory)
    events = sales_events(tables, manifest, 256)
    plan = example_plan(events, manifest["dataset_id"])
    return directory, tables, manifest, events, plan


@pytest.fixture(scope="module")
def scenario(source):
    _, _, manifest, events, plan = source
    records, truth = capture(events, plan, manifest["dataset_id"])
    replay, evaluation = evaluate(events, records, truth)
    return records, truth, replay, evaluation


def delivery(event, offset=0, received=None):
    return seal_record({"kind": "event", "topic": TOPIC, "partition": 0, "offset": offset,
                        "received_at": received or event["ingested_at"],
                        "body_utf8": canonical_json(event).decode()})


def reseal(record, **changes):
    return seal_record({**{k: v for k, v in record.items() if k != "record_id"}, **changes})


def test_checked_in_schemas_and_legacy_contract_unchanged():
    assert json.loads(Path("data/contracts/raw_dq_plan.v1.schema.json").read_text()) == plan_schema()
    assert json.loads(Path("data/contracts/raw_dq_capture.v1.schema.json").read_text()) == capture_schema()
    contract = event_contract()
    assert contract["supported_schema_versions"] == ["1.0"]
    assert len(contract["event_type_topics"]) == 13


def test_all_faults_reconciled_against_actual_source(source, scenario):
    directory, tables, manifest, events, plan = source
    records, truth, replay, evaluation = scenario
    assert manifest["facts_ready"] is True and len(tables) == 58
    assert len(events) == 256 and len(truth) == 8
    assert {i["issue_type"] for i in truth} == set(KINDS)
    report = replay["report"]
    assert {k: report[k] for k in ("raw_events", "accepted", "duplicate_event", "duplicate_business", "quarantined", "late", "out_of_order")} == dict(raw_events=258, accepted=253, duplicate_event=1, duplicate_business=1, quarantined=3, late=1, out_of_order=1)
    assert report["dlq_fixture"] == 3 and report["progress_declarations"] == 14
    assert all(evaluation["checks"].values()) and all(i["passed"] for i in evaluation["injections"])
    assert evaluation["prevalence_status"] == "within_recommended_range"
    assert report["curated_completeness"] == "not_qualified"
    assert report["transport_durability_proven"] is False
    assert all(row["status"] == "offline_only" for row in replay["dlq_fixture"])
    source_before = {p.relative_to(directory).as_posix(): file_sha256(p) for p in directory.rglob("*") if p.is_file()}
    original = deepcopy(events)
    assert capture(events, plan, manifest["dataset_id"]) == (records, truth)
    assert events == original
    assert source_before == {p.relative_to(directory).as_posix(): file_sha256(p) for p in directory.rglob("*") if p.is_file()}


def test_raw_and_curated_payloads_do_not_contain_private_truth(source, scenario):
    _, _, _, events, _ = source
    records, truth, replay, _ = scenario
    assert all(set(e["payload"]) <= PAYLOAD_FIELDS for e in events)
    forbidden = {"issue_type", "expected_action", "injection_id", "seed", "latent_demand", "stockout_flag", "anomaly_label"}
    def keys(value):
        if isinstance(value, dict):
            return set(value) | set().union(*(keys(v) for v in value.values()))
        if isinstance(value, list):
            return set().union(*(keys(v) for v in value))
        return set()
    assert not forbidden & keys(replay)
    for record in records:
        assert not forbidden & keys(record)
        if record["kind"] == "event":
            assert not forbidden & keys(json.loads(record["body_utf8"]))
    assert len(truth) == 8


def test_duplicates_and_missing_context_preserve_business_semantics(source, scenario):
    events = {e["event_id"]: e for e in source[3]}
    records = {r["record_id"]: r for r in scenario[0]}
    for injection in scenario[1]:
        raw = records[injection["raw_ref"]]
        event = json.loads(raw["body_utf8"])
        original = events[injection["target_event_id"]]
        if injection["issue_type"] == "exact_duplicate":
            assert raw["body_utf8"] == canonical_json(original).decode()
        elif injection["issue_type"] == "business_duplicate":
            assert event["event_id"] != original["event_id"]
            assert sale_fact(event, TOPIC) == sale_fact(original, TOPIC)
        elif injection["issue_type"] == "missing_optional_context":
            assert "sku" not in event["payload"]
            validate_event(event, transport_topic=TOPIC)
            assert sale_fact(event, TOPIC) == sale_fact(original, TOPIC)


def test_replay_twice_has_no_additional_revisions_counts_or_actions(scenario):
    records, _, expected, _ = scenario
    reader = OfflineReplay()
    for record in records:
        reader.consume(record)
    for record in records:
        reader.consume(record)
    assert reader.snapshot() == expected
    reader.snapshot()["accepted_facts"].clear()
    assert reader.snapshot() == expected


def test_late_and_out_of_order_preserve_historical_knowledge(scenario):
    records, truth, _, _ = scenario
    reader = OfflineReplay()
    refs = {i["raw_ref"] for i in truth if i["issue_type"] in {"late_event", "out_of_order"}}
    for record in records:
        before = deepcopy(reader.revisions)
        cutoff = (utc_timestamp(record["received_at"]) - timedelta(microseconds=1)).isoformat()
        historical = reader.aggregates_as_of(cutoff)
        reader.consume(record)
        if record["record_id"] in refs:
            assert reader.revisions[:-1] == before
            assert reader.aggregates_as_of(cutoff) == historical
            assert reader.revisions[-1]["known_at"] == record["received_at"]
            assert reader.revisions[-1]["source_raw_ref"] == record["record_id"]
            assert reader.aggregates_as_of(record["received_at"]) != historical
    assert len(reader.revisions) == len(reader.facts)


def test_watermark_is_explicit_progress_not_max_event_time(source):
    event = source[3][0]
    reader = OfflineReplay()
    reader.consume(delivery(event))
    assert reader.snapshot()["report"]["declared_source_watermark"] is None
    assert reader.snapshot()["report"]["max_accepted_event_time"] == utc_timestamp(event["occurred_at"]).isoformat()
    stamp = (utc_timestamp(event["ingested_at"]) + timedelta(days=1)).isoformat()
    marker = seal_record({"kind": "progress", "scope": "selected_sales_fixture", "after_offset": 0, "received_at": stamp, "complete_through": event["occurred_at"]})
    reader.consume(marker)
    assert reader.snapshot()["report"]["declared_source_watermark"] == utc_timestamp(event["occurred_at"]).isoformat()
    before = reader.snapshot()
    with pytest.raises(ValueError, match="did not advance"):
        reader.consume(reseal(marker, received_at=(utc_timestamp(stamp)+timedelta(seconds=1)).isoformat()))
    assert reader.snapshot() == before


def test_late_fact_appends_revision_for_existing_grain_without_rewriting_asof(source):
    original = deepcopy(source[3][0])
    late = deepcopy(original)
    late["event_id"] = str(uuid4())
    late["payload"]["sale_id"] = str(uuid4())
    late["occurred_at"] = (utc_timestamp(original["occurred_at"])-timedelta(minutes=1)).isoformat()
    cutoff = (utc_timestamp(original["ingested_at"])+timedelta(days=1)).isoformat()
    received = (utc_timestamp(cutoff)+timedelta(seconds=1)).isoformat()
    reader = OfflineReplay()
    reader.consume(delivery(original))
    reader.consume(seal_record({"kind": "progress", "scope": "selected_sales_fixture", "after_offset": 0, "received_at": cutoff, "complete_through": cutoff}))
    historical = reader.aggregates_as_of(cutoff)
    assert reader.consume(delivery(late, offset=1, received=received))["reason"] == "late"
    assert reader.aggregates_as_of(cutoff) == historical
    assert len(reader.revisions) == 2
    assert reader.revisions[1]["previous_revision_id"] == reader.revisions[0]["revision_id"]
    assert reader.revisions[1]["quantity"] == 2*reader.revisions[0]["quantity"]
    assert reader.aggregates_as_of(received) == [reader.revisions[1]]


@pytest.mark.parametrize("body", ['{"schema_version":"1.0","schema_version":"2.0"}', '{bad', 'NaN', 'null', '[]', '{"schema_version":"1.0","payload":null}'])
def test_invalid_raw_is_quarantined_without_advancing_event_time(source, body):
    record = reseal(delivery(source[3][0]), body_utf8=body)
    reader = OfflineReplay()
    assert reader.consume(record)["action"] == "quarantined"
    assert reader.snapshot()["report"]["max_accepted_event_time"] is None
    assert reader.watermark is None and not reader.revisions
    assert reader.quarantine[0]["body_sha256"] == hashlib.sha256(body.encode()).hexdigest()


@pytest.mark.parametrize("field,value", [("latent_demand", "100"), ("optional_context_v2", "future"), ("quantity", "1.5"), ("total_amount", "1.001"), ("total_amount", "1000000000001"), ("currency", "USD"), ("sale_id", ""), ("unit_price", "0.00")])
def test_unqualified_payload_cannot_enter_aggregate(source, field, value):
    event = deepcopy(source[3][0])
    event["payload"][field] = value
    reader = OfflineReplay()
    assert reader.consume(delivery(event))["action"] == "quarantined"
    assert reader.snapshot()["final_aggregates"] == []


def test_future_ingestion_and_other_event_source_are_quarantined(source):
    event = deepcopy(source[3][0])
    reader = OfflineReplay()
    assert reader.consume(delivery(event, received=event["occurred_at"]))["reason"] == "fact_unavailable_at_delivery"
    event["source"] = "unqualified-producer"
    assert reader.consume(delivery(event, offset=1))["action"] == "quarantined"


@pytest.mark.parametrize("same_event_id", [True, False])
def test_conflicting_fact_is_not_guessed_as_a_revision(source, same_event_id):
    event = deepcopy(source[3][0])
    reader = OfflineReplay()
    reader.consume(delivery(event))
    original = reader.snapshot()["final_aggregates"]
    if not same_event_id:
        event["event_id"] = str(uuid4())
    event["payload"]["promotion_applied"] = not event["payload"]["promotion_applied"]
    receipt = reader.consume(delivery(event, offset=1))
    assert receipt["action"] == "quarantined"
    assert receipt["reason"] == ("event_id_content_conflict" if same_event_id else "business_revision_requires_explicit_version")
    assert reader.snapshot()["final_aggregates"] == original
    assert len(reader.revisions) == 1


def test_offset_rewrites_and_bad_progress_fail_without_state_change(source):
    record = delivery(source[3][0])
    reader = OfflineReplay()
    reader.consume(record)
    before = reader.snapshot()
    with pytest.raises(ValueError, match="offsets"):
        reader.consume(reseal(record, received_at=(utc_timestamp(record["received_at"])+timedelta(seconds=1)).isoformat()))
    with pytest.raises(ValueError, match="position"):
        reader.consume(seal_record({"kind": "progress", "scope": "selected_sales_fixture", "after_offset": 1, "received_at": record["received_at"], "complete_through": source[3][0]["occurred_at"]}))
    assert reader.snapshot() == before


@pytest.mark.parametrize("changes", [{"partition": False}, {"offset": True}, {"topic": "new.topic.v1"}, {"body_utf8": "x"*65537}, {"received_at": "2026-01-01T01:00:00+01:00"}, {"injection_id": "secret"}])
def test_invalid_capture_metadata_is_rejected(source, changes):
    with pytest.raises(ValueError):
        parse_record(reseal(delivery(source[3][0]), **changes))


def test_tampered_record_digest_is_rejected(source):
    record = delivery(source[3][0])
    record["body_utf8"] = "{}"
    with pytest.raises(ValueError, match="identity"):
        parse_record(record)


def test_grain_keeps_currency_separate_and_never_imputes_zero(source):
    fact = sale_fact(source[3][0], TOPIC)
    alternative = {**fact, "currency": "EUR", "quantity": 1, "total_amount": "0.10"}
    other = {**alternative, "total_amount": "0.20"}
    result = fact_totals([fact, alternative, other])
    assert len(result) == 2
    assert next(r for r in result if r["currency"] == "EUR")["total_amount"] == "0.30"
    assert fact_totals([]) == []


def test_plan_order_is_irrelevant_and_seed_changes_identity(source, scenario):
    _, _, manifest, events, plan = source
    payload = plan.model_dump()
    payload["injections"].reverse()
    assert FaultPlan.from_payload(payload) == plan
    assert capture(events, FaultPlan.from_payload(payload), manifest["dataset_id"]) == scenario[:2]
    changed = example_plan(events, manifest["dataset_id"], seed=43)
    assert changed != plan
    assert capture(events, changed, manifest["dataset_id"])[0] != scenario[0]


@pytest.mark.parametrize("kind", ["duplicate_id", "overlapping_target", "overlapping_anchor", "anchor_is_target", "unexpected_anchor", "unknown_issue", "wrong_version"])
def test_plan_rejects_ambiguous_or_unsupported_injections(source, kind):
    payload = source[4].model_dump()
    rows = payload["injections"]
    if kind == "duplicate_id":
        rows[1]["injection_id"] = rows[0]["injection_id"]
    elif kind == "overlapping_target":
        rows[1]["target_event_id"] = rows[0]["target_event_id"]
    elif kind == "overlapping_anchor":
        timed = [r for r in rows if r["deliver_after_event_id"]]
        timed[1]["deliver_after_event_id"] = timed[0]["deliver_after_event_id"]
    elif kind == "anchor_is_target":
        next(r for r in rows if r["issue_type"] == "late_event")["deliver_after_event_id"] = rows[0]["target_event_id"]
    elif kind == "unexpected_anchor":
        next(r for r in rows if r["issue_type"] == "exact_duplicate")["deliver_after_event_id"] = str(uuid4())
    elif kind == "unknown_issue":
        rows[0]["issue_type"] = "guess-and-repair"
    else:
        payload["contract_version"] = "raw-dq-plan-2.0.0"
    with pytest.raises(ValueError):
        FaultPlan.from_payload(payload)


@pytest.mark.parametrize("kind", ["source_id", "source_hash", "missing_target", "missing_anchor", "cross_day_out_of_order"])
def test_plan_must_match_parent_and_declared_timing(source, kind):
    _, _, manifest, events, plan = source
    payload = plan.model_dump()
    if kind == "source_id":
        payload["source_dataset_id"] = "source-sha256-"+"0"*64
    elif kind == "source_hash":
        payload["source_events_sha256"] = "0"*64
    elif kind == "missing_target":
        payload["injections"][0]["target_event_id"] = str(uuid4())
    else:
        row = next(r for r in payload["injections"] if r["issue_type"] == "out_of_order")
        row["deliver_after_event_id"] = str(uuid4()) if kind == "missing_anchor" else events[-1]["event_id"]
    with pytest.raises(ValueError):
        capture(events, FaultPlan.from_payload(payload), manifest["dataset_id"])


def test_wrong_private_label_cannot_make_a_fault_pass(scenario, source):
    records, truth, _, _ = scenario
    changed = deepcopy(truth)
    changed[0]["expected_action"] = "arbitrarily_fixed"
    with pytest.raises(ValueError, match="reconciliation"):
        evaluate(source[3], records, changed)


@pytest.fixture(scope="module")
def package(source, tmp_path_factory):
    return write_fixture(source[0], source[4], tmp_path_factory.mktemp("dq-fixture"))


def test_independent_roundtrip_and_two_physical_runs_are_byte_identical(source, package, tmp_path):
    first = read_fixture(package, source[0])
    second = write_fixture(source[0], source[4], tmp_path / "second")
    assert read_fixture(second, source[0]) == first
    assert first["descriptor"]["ai03_handoff_ready"] is False
    assert {p: (package/p).read_bytes() for p in (*PATHS, MANIFEST)} == {p: (second/p).read_bytes() for p in (*PATHS, MANIFEST)}
    assert write_fixture(source[0], source[4], package.parent) == package


@pytest.mark.parametrize("name", ["raw/events.jsonl", "curated/replay.json", "simulation_truth/data_quality_injections.json", "simulation_truth/evaluation.json"])
def test_resealed_artifact_tampering_fails_independent_verification(source, package, tmp_path, name):
    import shutil
    copied = tmp_path / "tampered"
    shutil.copytree(package, copied)
    path = copied / name
    if name.endswith("jsonl"):
        lines = [json.loads(x) for x in path.read_text().splitlines()]
        index = next(i for i, r in enumerate(lines) if r["kind"] == "event")
        lines[index] = reseal(lines[index], body_utf8="{}")
        path.write_bytes(b"".join(canonical_json(r)+b"\n" for r in lines))
    else:
        value = json.loads(path.read_text())
        if isinstance(value, list):
            value[0]["expected_action"] = "tampered"
        elif "report" in value:
            value["report"]["accepted"] += 1
        else:
            value["status"] = "failed"
        path.write_bytes(canonical_json(value)+b"\n")
    manifest = json.loads((copied/MANIFEST).read_text())
    manifest["descriptor"]["artifacts"][name] = artifact(path, copied)
    manifest["fixture_id"] = "raw-dq-sha256-" + json_sha256(manifest["descriptor"])
    (copied/MANIFEST).write_bytes(canonical_json(manifest)+b"\n")
    with pytest.raises(ValueError, match="independent source/plan replay"):
        read_fixture(copied, source[0])


def test_source_and_fixture_are_not_writable_output_targets(source, package):
    with pytest.raises(ValueError, match="outside"):
        write_fixture(source[0], source[4], source[0]/"raw-faults")
    for directory in (source[0], package):
        result = subprocess.run([sys.executable, "-m", "data.dq.run", "--source-dir", str(source[0]), "--verify", str(package), "--output", str(directory/"overwrite.json")], capture_output=True, text=True)
        assert result.returncode == 2
        assert not (directory/"overwrite.json").exists()


def test_cli_verify_with_parent_and_missing_parent_failure(source, package, tmp_path):
    output = tmp_path / "receipt.json"
    for parent, code in [(source[0], 0), (tmp_path / "missing", 1)]:
        result = subprocess.run([sys.executable, "-m", "data.dq.run", "--source-dir", str(parent), "--verify", str(package), "--output", str(output)], capture_output=True, text=True)
        assert result.returncode == code, result.stderr
        assert json.loads(output.read_text())["status"] == ("passed" if code == 0 else "failed")


@pytest.mark.parametrize("change", ["extra_file", "symlink", "unsupported_descriptor", "wrong_parent"])
def test_package_rejects_unqualified_files_scope_or_parent(source, package, tmp_path, change):
    import shutil
    copied = tmp_path / "unqualified"
    shutil.copytree(package, copied)
    manifest = json.loads((copied/MANIFEST).read_text())
    if change == "extra_file":
        (copied/"unqualified.json").write_text("{}")
    elif change == "symlink":
        (copied/"source_binding.json").unlink()
        (copied/"source_binding.json").symlink_to(package/"source_binding.json")
    elif change == "wrong_parent":
        plan_file = copied/"simulation_truth/fault_plan.json"
        plan = json.loads(plan_file.read_text())
        plan["source_dataset_id"] = "source-sha256-"+"0"*64
        plan_file.write_bytes(canonical_json(plan)+b"\n")
        manifest["descriptor"]["artifacts"]["simulation_truth/fault_plan.json"] = artifact(plan_file, copied)
    else:
        manifest["descriptor"]["curated_completeness"] = "complete"
    manifest["fixture_id"] = "raw-dq-sha256-"+json_sha256(manifest["descriptor"])
    (copied/MANIFEST).write_bytes(canonical_json(manifest)+b"\n")
    with pytest.raises(ValueError):
        read_fixture(copied, source[0])
