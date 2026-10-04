"""Real PostgreSQL/API and broker mechanics; invented owner review does not qualify ML."""

import copy
import json
import os
from datetime import UTC, datetime, timedelta

import psycopg
import pytest
from fastapi.testclient import TestClient
from intelligence_head_fixture import (
    publication_events,
    rehash_policy,
    selected_policy,
    store_policy,
)
from psycopg.types.json import Jsonb
from test_intelligence_checkpoint_durability import run as checkpoint_run
from test_intelligence_durability import (
    READ_PATH,
    context as context,
    intelligence_runtime as intelligence_runtime,
    produce,
    rows,
    runtime as runtime,
)

from app.main import app
from app.repositories.intelligence_repository import IntelligenceRepository

pytestmark = pytest.mark.integration_broker
ACTIVE_PATH = READ_PATH + "/active"


@pytest.fixture
def selected(context, monkeypatch, tmp_path):
    events = publication_events()
    policy = selected_policy(events)
    path = tmp_path / "head-policy.json"
    store_policy(path, policy)
    monkeypatch.setenv("RETAILOPS_INTELLIGENCE_HEAD_POLICY", str(path))
    return events, policy, path


def test_read_budget_counts_real_payload_bytes_before_fetch(context, selected, monkeypatch):
    events, _, _ = selected
    project(events)
    monkeypatch.setattr("app.services.intelligence_head.MAX_PUBLICATION_BYTES", 1)
    response = get(context)
    assert response.status_code == 429
    assert response.json() == {"detail": "intelligence_head_read_budget"}


def project(events):
    repository = IntelligenceRepository()
    for event in events:
        repository.project(event)


def get(context, **params):
    with TestClient(app) as client:
        return client.get(ACTIVE_PATH, params=params, headers=context.headers)


def test_complete_delivery_selects_exact_original_payload_and_lineage(context, selected):
    events, policy, _ = selected
    for index, event in enumerate(events):
        produce(context, event, partition=index % 2)
    checkpoint_run(context, count=len(events))
    response = get(
        context,
        release_id=policy.heads[0].release_id,
        inference_run_id=policy.heads[0].inference_run_id,
        as_of=policy.heads[0].forecast_origin.isoformat(),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["selection"] == "approved_release_as_of_run"
    assert body["approval_authority"] == "private_operator_selection"
    assert [item["forecast"] for item in body["items"]] == [event["payload"] for event in events]
    assert body["pagination"]["total"] == 7
    assert all(item["freshness"]["status"] == "unknown" for item in body["items"])
    assert body["heads"][0]["selection_sha256"] == policy.heads[0].selection_sha256
    assert get(context, inference_run_id="run-" + "f" * 32).json()["data_status"] == "no_data"
    assert get(context, as_of="2020-01-01T23:59:59Z").json()["items"] == []
    assert get(context, product_id="foreign").status_code == 403
    with TestClient(app) as client:
        assert client.get(ACTIVE_PATH).status_code == 401


def test_partial_delivery_and_uncommitted_tail_cannot_activate(context, selected):
    events, _, _ = selected
    project(events[:-1])
    response = get(context, limit=1)
    assert response.status_code == 503
    assert response.json() == {"detail": "intelligence_head_incomplete"}
    with psycopg.connect(context.db, row_factory=psycopg.rows.dict_row) as connection:
        IntelligenceRepository().project_on_connection(connection, events[-1])
        assert get(context, limit=1).status_code == 503
    assert get(context).status_code == 200


def test_newer_result_and_late_replay_cannot_replace_operator_head(context, selected):
    original, _, path = selected
    events = publication_events(origin=events_origin(original) - timedelta(days=1))
    policy = selected_policy(events)
    store_policy(path, policy)
    project(events)
    first = get(context).json()
    newer = publication_events(origin=events_origin(events) + timedelta(days=1))
    older = publication_events(origin=events_origin(events) - timedelta(days=1))
    project(newer)
    project(older)
    project(list(reversed(events)))
    after = get(context).json()
    assert after["view_sha256"] == first["view_sha256"]
    assert [item["forecast"] for item in after["items"]] == [event["payload"] for event in events]
    assert after["heads"][0]["inference_run_id"] == policy.heads[0].inference_run_id
    assert rows(
        context,
        "SELECT count(*) FROM ai_forecast_results WHERE prediction_dataset_id=%s",
        (policy.heads[0].prediction_dataset_id,),
    ) == [(7,)]


def events_origin(events):
    return datetime.fromisoformat(events[0]["payload"]["forecast_origin"])


def test_policy_change_invalidates_pagination_and_revocation_is_immediate(
    context, selected, tmp_path
):
    events, policy, path = selected
    project(events)
    first = get(context, limit=2).json()
    view = first["view_sha256"]
    assert get(context, limit=2, offset=2).status_code == 409
    assert get(context, limit=2, offset=2, view_sha256=view).status_code == 200
    other = publication_events(origin=events_origin(events) - timedelta(days=1))
    project(other)
    replacement = tmp_path / "replacement.json"
    store_policy(replacement, selected_policy(other))
    os.replace(replacement, path)
    assert get(context, limit=2, offset=2, view_sha256=view).status_code == 409
    assert get(context).json()["items"][0]["forecast"] == other[0]["payload"]
    replacement.write_text(rehash_policy({"version": policy.version, "heads": []}))
    replacement.chmod(0o600)
    os.replace(replacement, path)
    assert get(context).json()["data_status"] == "no_data"
    with TestClient(app) as client:
        history = client.get(
            READ_PATH,
            params={"inference_run_id": policy.heads[0].inference_run_id},
            headers=context.headers,
        )
    assert history.status_code == 200 and history.json()["pagination"]["total"] == 7


@pytest.mark.parametrize("mutation", ["payload", "missing", "unexpected"])
def test_corruption_or_incomplete_tail_outside_first_page_blocks_all_items(
    context, selected, mutation
):
    events, policy, _ = selected
    project(events)
    with psycopg.connect(context.db) as connection:
        if mutation == "payload":
            changed = copy.deepcopy(events[-1]["payload"])
            changed["prediction"]["candidate"]["mean"] += 1
            connection.execute(
                "UPDATE ai_forecast_results SET payload=%s WHERE prediction_id=%s",
                (Jsonb(changed), events[-1]["payload"]["prediction_id"]),
            )
        elif mutation == "missing":
            connection.execute(
                "DELETE FROM ai_intelligence_inbox WHERE prediction_id=%s",
                (events[-1]["payload"]["prediction_id"],),
            )
            connection.execute(
                "DELETE FROM ai_forecast_results WHERE prediction_id=%s",
                (events[-1]["payload"]["prediction_id"],),
            )
    if mutation == "unexpected":
        extra = publication_events(
            products=("foreign",), artifact=policy.heads[0].prediction_dataset_id[-64:]
        )
        project(extra)
    result = get(context, limit=1)
    assert result.status_code == 503
    assert "items" not in result.json()


@pytest.mark.parametrize("timing", ["expired", "future"])
def test_owner_review_window_is_enforced_without_renewal_from_received_time(
    context, selected, timing
):
    events, _, path = selected
    project(events)
    delta = timedelta(minutes=-6 if timing == "expired" else 1)
    store_policy(path, selected_policy(events, reviewed_at=datetime.now(UTC) + delta))
    response = get(context)
    assert response.status_code == 503
    assert response.json()["detail"] == (
        "intelligence_head_approval_expired"
        if timing == "expired"
        else "intelligence_head_review_in_future"
    )


def test_full_publication_verified_before_returning_reader_subset(context, monkeypatch, tmp_path):
    events = publication_events(products=("fixture-product", "foreign"))
    policy = selected_policy(events, products=("fixture-product", "foreign"))
    path = tmp_path / "policy.json"
    store_policy(path, policy)
    monkeypatch.setenv("RETAILOPS_INTELLIGENCE_HEAD_POLICY", str(path))
    project(events[:-1])
    assert get(context).status_code == 503
    project(events[-1:])
    result = get(context).json()
    assert result["pagination"]["total"] == 7
    assert all(item["forecast"]["product_id"] == "fixture-product" for item in result["items"])
    assert "foreign" not in json.dumps(result)


def test_private_selection_is_required_even_when_reader_can_see_history(
    context, monkeypatch, selected
):
    events, policy, _ = selected
    project(events)
    monkeypatch.delenv("RETAILOPS_INTELLIGENCE_HEAD_POLICY")
    assert get(context).status_code == 503
    with TestClient(app) as client:
        assert (
            client.get(
                READ_PATH,
                params={"inference_run_id": policy.heads[0].inference_run_id},
                headers=context.headers,
            ).status_code
            == 200
        )
