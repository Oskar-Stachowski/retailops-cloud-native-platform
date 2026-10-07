"""Trust boundaries, complete grain, policy reload and safe private preparation."""

import copy
import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock

import pytest
from app.auth.intelligence import IntelligencePrincipal, verified_principal
from app.main import app
from app.services.intelligence_contract import content_hash
from app.services.intelligence_head import verify_head_rows
from app.services.intelligence_head_policy import (
    DEVELOPMENT_ACCEPTANCE_SHA256,
    ForecastHeadPolicy,
    head_policy,
    private_document,
)
from fastapi import HTTPException
from fastapi.testclient import TestClient
from intelligence_head_fixture import (
    publication_events,
    rehash_policy,
    selected_policy,
    store_policy,
)
from pydantic import ValidationError
from scripts.prepare_intelligence_head import write_new_policy


@pytest.fixture
def events():
    return publication_events()


@pytest.fixture
def policy(events):
    return selected_policy(events)


def test_exact_development_owner_receipt_allows_separate_namespace(policy, events):
    """Invented policy mechanics only; this test never qualifies the original model."""
    raw = policy.model_dump(mode="json")
    head = raw["heads"][0]
    head["model_name"] = "retailops-demand-forecast-v12-development"
    review = head["owner_review_receipt"]
    review["model_name"] = head["model_name"]
    review["development_acceptance_sha256"] = DEVELOPMENT_ACCEPTANCE_SHA256
    head["owner_review_receipt_sha256"] = content_hash(review)
    selected = ForecastHeadPolicy.model_validate_json(rehash_policy(raw))
    for event in events:
        event["payload"]["model_name"] = head["model_name"]
    records = {
        event["payload"]["prediction_id"]: {
            "payload": event["payload"],
            "payload_sha256": content_hash(event["payload"]),
        }
        for event in events
    }
    changed = selected.model_dump(mode="json")
    for row in changed["heads"][0]["rows"]:
        row["payload_sha256"] = records[row["prediction_id"]]["payload_sha256"]
    selected = ForecastHeadPolicy.model_validate_json(rehash_policy(changed))
    verify_head_rows(selected.heads[0], records)


@pytest.mark.parametrize("acceptance", [None, "f" * 64])
def test_development_name_alone_or_substituted_owner_decision_is_refused(
    policy, acceptance
):
    raw = policy.model_dump(mode="json")
    head = raw["heads"][0]
    head["model_name"] = "retailops-demand-forecast-v12-development"
    review = head["owner_review_receipt"]
    review["model_name"] = head["model_name"]
    if acceptance is not None:
        review["development_acceptance_sha256"] = acceptance
    head["owner_review_receipt_sha256"] = content_hash(review)
    with pytest.raises(ValidationError, match="development_acceptance_required"):
        ForecastHeadPolicy.model_validate_json(rehash_policy(raw))


def test_standard_owner_review_preserves_original_field_inventory(policy):
    raw = policy.model_dump(mode="json")
    assert (
        "development_acceptance_sha256" not in raw["heads"][0]["owner_review_receipt"]
    )
    assert ForecastHeadPolicy.model_validate_json(json.dumps(raw)) == policy


@pytest.mark.parametrize(
    "mutation",
    [
        "digest",
        "duplicate_id",
        "scope",
        "long_review",
        "past_approval",
        "non_utc",
        "mechanics",
        "development",
        "overlap",
        "duplicate_artifact",
        "run_id",
        "extra_field",
        "rejected",
        "pending",
        "wrong_alias",
        "wrong_owner_approval",
        "wrong_owner_release",
        "review_hash",
    ],
)
def test_policy_refuses_invalid_or_ambiguous_selections(policy, mutation):
    raw = policy.model_dump(mode="json")
    head = raw["heads"][0]
    if mutation == "digest":
        head["reviewed_by"] = "changed"
    elif mutation == "duplicate_id":
        head["rows"][1] = copy.deepcopy(head["rows"][0])
    elif mutation == "scope":
        head["product_ids"].append("foreign")
    elif mutation == "long_review":
        head["valid_until"] = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    elif mutation == "past_approval":
        head["approval_valid_until"] = head["reviewed_at"]
    elif mutation == "non_utc":
        head["reviewed_at"] = "2026-10-04T12:00:00+02:00"
    elif mutation in {"mechanics", "development"}:
        head["model_name"] += "-" + mutation
    elif mutation == "overlap":
        raw["heads"].append(copy.deepcopy(head))
    elif mutation == "duplicate_artifact":
        other = copy.deepcopy(head)
        other["product_ids"] = ["foreign"]
        for index, row in enumerate(other["rows"]):
            row["prediction_id"] = "prediction-sha256-" + f"{index:064x}"
        raw["heads"].append(other)
    elif mutation == "run_id":
        head["inference_run_id"] = "run-not-owner-format"
    elif mutation == "rejected":
        head["owner_review_receipt"]["rejected"] = True
    elif mutation == "pending":
        head["owner_review_receipt"]["pending_decisions"] = ["unfinished"]
    elif mutation == "wrong_alias":
        head["owner_review_receipt"]["aliases"]["champion"] = "2"
    elif mutation == "wrong_owner_approval":
        head["owner_review_receipt"]["approval_sha256"] = "f" * 64
    elif mutation == "wrong_owner_release":
        head["owner_review_receipt"]["release_id"] = (
            "v12-model-release-sha256-" + "f" * 64
        )
    elif mutation == "review_hash":
        head["owner_review_receipt_sha256"] = "0" * 64
    else:
        head["grant_implies_approval"] = True
    if mutation.startswith("wrong_"):
        head["owner_review_receipt_sha256"] = content_hash(head["owner_review_receipt"])
    text = json.dumps(raw) if mutation == "digest" else rehash_policy(raw)
    with pytest.raises(ValidationError):
        ForecastHeadPolicy.model_validate_json(text)


@pytest.mark.parametrize(
    "mutation", ["partial", "duplicate_grain", "mixed_binding", "mechanics"]
)
def test_preparation_requires_complete_production_publication(events, mutation):
    changed = copy.deepcopy(events)
    if mutation == "partial":
        changed.pop()
    elif mutation == "duplicate_grain":
        changed[-1] = copy.deepcopy(changed[0])
    elif mutation == "mixed_binding":
        changed[-1]["payload"]["model_version"] = "2"
    else:
        for event in changed:
            event["payload"]["model_name"] += "-mechanics"
    with pytest.raises((ValidationError, HTTPException)):
        selected_policy(changed)


def test_full_payload_hash_and_scope_coverage_are_checked_outside_page(events, policy):
    records = {
        event["payload"]["prediction_id"]: {
            "payload": event["payload"],
            "payload_sha256": content_hash(event["payload"]),
        }
        for event in events
    }
    verify_head_rows(policy.heads[0], records)
    records[events[-1]["payload"]["prediction_id"]]["payload"]["prediction"][
        "candidate"
    ]["mean"] += 1
    with pytest.raises(HTTPException) as caught:
        verify_head_rows(policy.heads[0], records)
    assert caught.value.detail == "intelligence_head_binding_invalid"


@pytest.mark.parametrize(
    "kind", ["permissions", "symlink", "fifo", "large", "duplicate_json", "missing"]
)
def test_policy_file_refuses_unsafe_input_without_exposing_paths(
    tmp_path, monkeypatch, policy, kind
):
    path = tmp_path / "private-sensitive-policy.json"
    store_policy(path, policy)
    if kind == "permissions":
        path.chmod(0o644)
    elif kind == "symlink":
        target = tmp_path / "real.json"
        path.rename(target)
        path.symlink_to(target)
    elif kind == "fifo":
        path.unlink()
        os.mkfifo(path, 0o600)
    elif kind == "large":
        path.write_bytes(b" " * (1024 * 1024 + 1))
    elif kind == "duplicate_json":
        path.write_text('{"version":"first","version":"second"}')
    else:
        path.unlink()
    monkeypatch.setenv("RETAILOPS_INTELLIGENCE_HEAD_POLICY", str(path))
    with pytest.raises(HTTPException) as caught:
        head_policy()
    assert caught.value.status_code == 503
    assert caught.value.detail == "intelligence_head_policy_unavailable"


def test_missing_policy_cannot_be_replaced_by_a_reader_grant(monkeypatch):
    monkeypatch.delenv("RETAILOPS_INTELLIGENCE_HEAD_POLICY", raising=False)
    with pytest.raises(HTTPException):
        head_policy()


def test_policy_is_reloaded_and_empty_policy_revokes_all_heads(
    tmp_path, monkeypatch, policy
):
    path = tmp_path / "policy.json"
    store_policy(path, policy)
    monkeypatch.setenv("RETAILOPS_INTELLIGENCE_HEAD_POLICY", str(path))
    assert head_policy() == policy
    empty = json.loads(rehash_policy({"version": policy.version, "heads": []}))
    replacement = tmp_path / "replacement.json"
    replacement.write_text(json.dumps(empty))
    replacement.chmod(0o600)
    os.replace(replacement, path)
    assert head_policy().heads == ()


def test_preparation_is_atomic_private_and_never_replaces_policy(tmp_path, policy):
    path = tmp_path / "prepared.json"
    write_new_policy(path, policy.model_dump_json().encode())
    assert path.stat().st_mode & 0o777 == 0o600
    assert (
        ForecastHeadPolicy.model_validate_json(
            private_document(path, max_bytes=1024 * 1024)
        )
        == policy
    )
    original = path.read_bytes()
    with pytest.raises(FileExistsError):
        write_new_policy(path, b"changed")
    assert path.read_bytes() == original
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize(
    "query",
    [
        "?limit=101",
        "?user_id=admin",
        "?limit=2&limit=3",
        "?as_of=2026-10-04T23:59:59",
        "?as_of=2026-10-04T23:59:59%2B02:00",
    ],
)
def test_active_route_rejects_unknown_repeated_unbounded_or_non_utc_query(
    query, monkeypatch
):
    principal = IntelligencePrincipal.model_validate_json(
        json.dumps(
            {
                "principal_id": "reader",
                "credential_sha256": "a" * 64,
                "capabilities": ["forecast:read"],
                "product_ids": ["fixture-product"],
                "selling_location_ids": ["fixture-store"],
                "channels": ["store"],
                "release_ids": ["v12-model-release-sha256-" + "a" * 64],
            }
        )
    )
    app.dependency_overrides[verified_principal] = lambda: principal
    call = Mock()
    monkeypatch.setattr("app.api.intelligence.read_active_forecasts", call)
    try:
        with TestClient(app) as client:
            assert (
                client.get("/intelligence/v2/forecasts/active" + query).status_code
                == 422
            )
        call.assert_not_called()
    finally:
        app.dependency_overrides.clear()


def test_active_openapi_has_the_original_payload_and_requires_credential():
    schema = app.openapi()
    operation = schema["paths"]["/intelligence/v2/forecasts/active"]["get"]
    assert operation["security"] == [{"IntelligenceCredential": []}]
    assert schema["components"]["schemas"]["ForecastProjection"]["properties"][
        "forecast"
    ] == {
        "$ref": "#/components/schemas/AI10_V12ForecastItem",
    }


def test_active_errors_preserve_existing_api_envelope(monkeypatch):
    principal = IntelligencePrincipal.model_validate_json(
        json.dumps(
            {
                "principal_id": "reader",
                "credential_sha256": "a" * 64,
                "capabilities": ["forecast:read"],
                "product_ids": ["fixture-product"],
                "selling_location_ids": ["fixture-store"],
                "channels": ["store"],
                "release_ids": ["v12-model-release-sha256-" + "a" * 64],
            }
        )
    )
    app.dependency_overrides[verified_principal] = lambda: principal
    monkeypatch.setattr(
        "app.api.intelligence.read_active_forecasts",
        Mock(side_effect=HTTPException(503, detail="intelligence_head_incomplete")),
    )
    try:
        with TestClient(app) as client:
            response = client.get("/intelligence/v2/forecasts/active")
        assert response.status_code == 503
        assert response.json() == {
            "error": {"code": "http_error", "message": "intelligence_head_incomplete"},
        }
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize(
    "change", ["success", "old_review", "future_review", "rejected", "wrong_release"]
)
def test_private_cli_requires_fresh_matching_owner_review(
    tmp_path, policy, events, change
):
    events_file = tmp_path / "events.json"
    events_file.write_text(json.dumps(events))
    events_file.chmod(0o600)
    review_file = tmp_path / "owner-review.json"
    receipt = policy.heads[0].owner_review_receipt.model_dump(mode="json")
    if change == "rejected":
        receipt["rejected"] = True
    elif change == "wrong_release":
        receipt["release_id"] = "v12-model-release-sha256-" + "f" * 64
    review_file.write_text(json.dumps(receipt))
    review_file.chmod(0o600)
    now = datetime.now(UTC)
    if change == "old_review":
        now -= timedelta(minutes=6)
    elif change == "future_review":
        now += timedelta(minutes=1)
    output = tmp_path / "next-policy.json"
    result = subprocess.run(
        [
            sys.executable,
            str(
                Path(__file__).resolve().parents[1]
                / "scripts/prepare_intelligence_head.py"
            ),
            "--events-file",
            str(events_file),
            "--owner-review-receipt-file",
            str(review_file),
            "--reviewed-at",
            now.isoformat(),
            "--reviewed-by",
            "fixture-operator",
            "--product",
            "fixture-product",
            "--selling-location",
            "fixture-store",
            "--horizon",
            "7",
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if change == "success":
        assert result.returncode == 0
        assert json.loads(result.stdout)["activated"] is False
        assert output.stat().st_mode & 0o777 == 0o600
    else:
        assert result.returncode == 2
        assert result.stderr == '{"error":"intelligence_head_preparation_failed"}\n'
        assert result.stdout == "" and not output.exists()
