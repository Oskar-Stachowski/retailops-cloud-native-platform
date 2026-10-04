"""Real private PostgreSQL/broker/API suggestion mechanics; no assistant quality claim."""

import copy
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta

import psycopg
import pytest
from fastapi.testclient import TestClient
from intelligence_suggestion_fixture import (
    access_document,
    enable_suggestions as enable_suggestions,
    suggestion_event,
)
from test_intelligence_checkpoint_durability import checkpoint, receipts, run
from test_intelligence_durability import (
    context as context,
    fixture_event,
    intelligence_runtime as intelligence_runtime,
    positions,
    produce,
    rows,
    runtime as runtime,
)

from app.main import app
from app.repositories.intelligence_repository import IntelligenceRepository
from app.services.intelligence_checkpoint import IntelligenceCheckpointStore
from app.services.intelligence_contract import content_hash
from app.services.realtime_quarantine import replay_quarantined_message

pytestmark = pytest.mark.integration_broker
READ = "/intelligence/v2/recommendations"


@pytest.fixture
def authorized(context, monkeypatch, tmp_path):
    token = "fixture-personal-suggestion-key-" + "s" * 32
    document = access_document(hashlib.sha256(token.encode()).hexdigest())
    path = tmp_path / "suggestion-access.json"
    path.write_text(json.dumps(document))
    path.chmod(0o600)
    monkeypatch.setenv("RETAILOPS_INTELLIGENCE_SUGGESTION_ACCESS_POLICY", str(path))
    return {"Authorization": "Bearer " + token}, path, document


def count(context, event):
    return rows(
        context,
        "SELECT count(*) FROM ai_recommendation_results WHERE recommendation_id=%s",
        (event["payload"]["recommendation_id"],),
    )[0][0]


def get(authorized, suffix="", **params):
    with TestClient(app) as client:
        return client.get(READ + suffix, headers=authorized[0], params=params)


def test_two_resource_delivery_preserves_exact_payload_and_atomic_receipt(context, authorized):
    event, forecast = suggestion_event(), fixture_event()
    start = produce(context, event, partition=0)
    produce(context, event, partition=0)
    produce(context, forecast, partition=0)
    run(context, count=3)
    assert positions(context)[0] == checkpoint(context)[1] == start + 3
    assert [row[2] for row in receipts(context)] == ["projected", "duplicate", "projected"]
    assert count(context, event) == 1
    assert rows(
        context,
        "SELECT count(*) FROM ai_recommendation_inbox WHERE event_id=%s",
        (event["event_id"],),
    ) == [(1,)]
    links = rows(
        context,
        "SELECT prediction_id,recommendation_id,quarantine_id FROM ai_intelligence_transport WHERE consumer_group=%s ORDER BY offset_number",
        (context.group,),
    )
    assert [str(row[1]) if row[1] else None for row in links] == [
        event["payload"]["recommendation_id"]
    ] * 2 + [None]
    assert links[2][0] == forecast["payload"]["prediction_id"] and all(
        row[2] is None for row in links
    )
    response = get(authorized, "/" + event["payload"]["recommendation_id"])
    assert response.status_code == 200
    assert response.json()["suggestion"] == event["payload"]
    assert response.json()["freshness"]["status"] == "current"
    assert response.json()["execution_authorized"] is False
    assert response.headers["cache-control"] == "no-store"


def test_sigkill_after_commit_before_ack_replays_without_second_effect(context, authorized):
    event = suggestion_event()
    offset = produce(context, event)
    code = """
import os,signal
from app.services.intelligence_checkpoint_runner import CheckpointBrokerConfig,IntelligenceCheckpointRunner,build_checkpoint_client
config=CheckpointBrokerConfig(bootstrap_servers=os.environ['AI10_BROKER'],security_protocol='PLAINTEXT',allow_plaintext_loopback=True)
client,topology=build_checkpoint_client(config,os.environ['AI10_GROUP'])
class Kill:
 def __getattr__(self,name): return getattr(client,name)
 def commit(self,**kwargs): os.kill(os.getpid(),signal.SIGKILL)
IntelligenceCheckpointRunner(kafka_consumer=Kill(),topology=topology,group=os.environ['AI10_GROUP'],bootstrap=True).run(max_messages=1)
"""
    process = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        timeout=45,
        env={**os.environ, "AI10_BROKER": context.bootstrap, "AI10_GROUP": context.group},
    )
    assert process.returncode == -9, process.stderr.decode()
    assert positions(context)[0] == offset and checkpoint(context)[1] == offset + 1
    before = receipts(context)
    run(context, bootstrap=False)
    assert receipts(context) == before and count(context, event) == 1
    assert (
        get(authorized, "/" + event["payload"]["recommendation_id"]).json()["suggestion"]
        == event["payload"]
    )


def test_checkpoint_failure_rolls_back_suggestion_inbox_and_receipt_without_ack(context):
    event = suggestion_event()
    offset = produce(context, event)

    class Failure(IntelligenceCheckpointStore):
        @staticmethod
        def advance(connection, lease, next_offset):
            connection.execute("SELECT 1/0")

    with pytest.raises(psycopg.errors.DivisionByZero):
        run(context, store=Failure())
    assert positions(context)[0] == checkpoint(context)[1] == offset
    assert count(context, event) == 0 and receipts(context) == []
    assert rows(
        context,
        "SELECT count(*) FROM ai_recommendation_inbox WHERE event_id=%s",
        (event["event_id"],),
    ) == [(0,)]
    run(context, bootstrap=False)
    assert count(context, event) == 1


def test_collision_and_poison_quarantine_preserve_original_then_continue(context, authorized):
    first = suggestion_event()
    collision = copy.deepcopy(first)
    collision["payload"]["summary"] = "Changed summary under the same immutable identity."
    poison = suggestion_event()
    poison["payload"]["requires_human_review"] = False
    last = suggestion_event()
    for event in (first, collision, poison, last):
        produce(context, event)
    run(context, count=4)
    assert [row[2] for row in receipts(context)] == [
        "projected",
        "quarantined",
        "quarantined",
        "projected",
    ]
    assert count(context, first) == count(context, last) == 1 and count(context, poison) == 0
    assert (
        get(authorized, "/" + first["payload"]["recommendation_id"]).json()["suggestion"]
        == first["payload"]
    )
    assert rows(
        context,
        "SELECT count(*) FROM ai_intelligence_transport WHERE consumer_group=%s AND quarantine_id IS NOT NULL AND recommendation_id IS NULL AND prediction_id IS NULL",
        (context.group,),
    ) == [(2,)]


def test_current_excludes_expired_future_and_late_replay_preserves_history(context, authorized):
    now = datetime.now(UTC)
    current = suggestion_event()
    expired = suggestion_event(source=now - timedelta(minutes=10))
    future = suggestion_event(source=now + timedelta(minutes=5))
    for event in (current, expired, future, expired):
        produce(context, event)
    run(context, count=4)
    body = get(authorized).json()
    own = {
        current["payload"]["recommendation_id"],
        expired["payload"]["recommendation_id"],
        future["payload"]["recommendation_id"],
    }
    assert {row["suggestion"]["recommendation_id"] for row in body["items"]} & own == {
        current["payload"]["recommendation_id"]
    }
    history = get(authorized, selection="immutable_history").json()
    items = {row["suggestion"]["recommendation_id"]: row for row in history["items"]}
    assert own <= set(items)
    assert (
        items[expired["payload"]["recommendation_id"]]["freshness"]["reason"]
        == "suggestion_expired"
    )
    assert (
        items[future["payload"]["recommendation_id"]]["freshness"]["reason"]
        == "publication_in_future"
    )
    assert count(context, expired) == 1


def test_scope_every_model_policy_and_config_are_filtered_before_counts(context, authorized):
    own = suggestion_event(model_release_refs=["fixture:approved-model-release"])
    hidden = [
        suggestion_event(product_id="foreign"),
        suggestion_event(
            selling_location_id="32345678-1234-4234-8234-123456789012",
            store_id="32345678-1234-4234-8234-123456789012",
        ),
        suggestion_event(channel="online"),
        suggestion_event(policy_sha256="c" * 64),
        suggestion_event(agent_config_version="foreign-agent"),
        suggestion_event(
            model_release_refs=["fixture:approved-model-release", "fixture:foreign-model-release"]
        ),
    ]
    repository = IntelligenceRepository()
    for event in [own, *hidden]:
        repository.project(event)
    body = get(authorized, trace_id=own["payload"]["trace_id"]).json()
    assert body["pagination"]["total"] == 1 and body["items"][0]["suggestion"] == own["payload"]
    all_ids = {
        row["suggestion"]["recommendation_id"]
        for row in get(authorized, selection="immutable_history").json()["items"]
    }
    assert not all_ids & {event["payload"]["recommendation_id"] for event in hidden}
    assert get(authorized, product_id="foreign").status_code == 403
    for event in hidden:
        assert get(authorized, "/" + event["payload"]["recommendation_id"]).status_code == 404


def test_bounded_pagination_detects_new_rows_and_revoked_grants(context, authorized, monkeypatch):
    first = suggestion_event()
    IntelligenceRepository().project(first)
    response = get(authorized, limit=1)
    assert response.status_code == 200
    old = response.json()["view_sha256"]
    assert get(authorized, limit=1, offset=1).status_code == 409
    assert get(authorized, limit=1, offset=1, view_sha256=old).status_code == 200
    second = suggestion_event()
    IntelligenceRepository().project(second)
    assert get(authorized, limit=1, offset=1, view_sha256=old).status_code == 409
    monkeypatch.setattr("app.services.intelligence_suggestion_reader.MAX_RESULTS", 1)
    assert get(authorized).status_code == 429
    monkeypatch.setattr("app.services.intelligence_suggestion_reader.MAX_RESULTS", 500)
    monkeypatch.setattr("app.services.intelligence_suggestion_reader.MAX_VIEW_BYTES", 1)
    assert get(authorized).status_code == 429
    headers, path, document = authorized
    document["principals"][0]["credential_sha256"] = "0" * 64
    path.write_text(json.dumps(document))
    assert get(authorized).status_code == 401
    with TestClient(app) as client:
        assert client.get(READ, headers=context.headers).status_code == 401


def test_uncommitted_and_corrupted_projection_fails_closed(context, authorized):
    event = suggestion_event()
    with psycopg.connect(context.db, row_factory=psycopg.rows.dict_row) as connection:
        IntelligenceRepository().project_on_connection(connection, event)
        assert get(authorized, "/" + event["payload"]["recommendation_id"]).status_code == 404
    assert get(authorized, "/" + event["payload"]["recommendation_id"]).status_code == 200
    with psycopg.connect(context.db) as connection:
        connection.execute(
            "UPDATE ai_recommendation_results SET payload=jsonb_set(payload,'{summary}','\"corruption\"') WHERE recommendation_id=%s",
            (event["payload"]["recommendation_id"],),
        )
    assert get(authorized, "/" + event["payload"]["recommendation_id"]).status_code == 503


def test_transport_xor_constraint_and_populated_schema_downgrade_guard(context):
    event = suggestion_event()
    produce(context, event)
    run(context)
    with psycopg.connect(context.db) as connection:
        with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
            connection.execute(
                "UPDATE ai_intelligence_transport SET recommendation_id=NULL WHERE consumer_group=%s",
                (context.group,),
            )
    process = subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "a10f0c7e0300"],
        capture_output=True,
        timeout=30,
        env={**os.environ, "DATABASE_URL": context.db, "PYTHONPATH": "."},
    )
    assert process.returncode != 0
    assert b"suggestion_schema_downgrade_requires_empty_projection" in process.stderr
    assert rows(context, "SELECT version_num FROM alembic_version") == [("a10f0c7e0400",)]
    assert count(context, event) == 1


def test_reviewed_quarantine_replay_preserves_identity_and_exact_payload(context, authorized):
    corrected = suggestion_event()
    poison = copy.deepcopy(corrected)
    poison["payload"]["requires_human_review"] = False
    produce(context, poison)
    run(context)
    quarantine = rows(
        context,
        "SELECT quarantine_id FROM ai_intelligence_transport WHERE consumer_group=%s AND outcome='quarantined'",
        (context.group,),
    )[0][0]
    before = copy.deepcopy(corrected)
    result = replay_quarantined_message(
        str(quarantine),
        event=corrected,
        operator="fixture-review-operator",
        bootstrap_servers=context.bootstrap,
    )
    assert result["status"] == "replayed"
    run(context, bootstrap=False)
    assert count(context, corrected) == 1
    assert (
        get(authorized, "/" + corrected["payload"]["recommendation_id"]).json()["suggestion"]
        == corrected["payload"]
    )
    assert corrected == before
    repeated = replay_quarantined_message(
        str(quarantine),
        event=corrected,
        operator="fixture-review-operator",
        bootstrap_servers=context.bootstrap,
    )
    assert repeated["status"] == "already_replayed"


def test_current_page_expiry_invalidates_view_and_keeps_exact_history(context, authorized):
    event = suggestion_event(source=datetime.now(UTC) - timedelta(seconds=295))
    IntelligenceRepository().project(event)
    trace = event["payload"]["trace_id"]
    first = get(authorized, trace_id=trace, limit=1)
    assert first.status_code == 200 and first.json()["pagination"]["total"] == 1
    view = first.json()["view_sha256"]
    expires = datetime.fromisoformat(event["payload"]["expires_at"])
    deadline = time.monotonic() + 7
    while datetime.now(UTC) <= expires:
        assert time.monotonic() < deadline
        time.sleep(0.05)
    assert get(authorized, trace_id=trace, offset=1, view_sha256=view).status_code == 409
    assert get(authorized, trace_id=trace).json()["items"] == []
    history = get(authorized, trace_id=trace, selection="immutable_history").json()["items"]
    assert history[0]["suggestion"] == event["payload"]
    assert history[0]["freshness"]["status"] == "stale"
