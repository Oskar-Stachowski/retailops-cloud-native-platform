from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def workflow_response(recommendation_id, action="accept", status="accepted"):
    return {
        "workflow_action": {
            "id": str(uuid4()),
            "entity_type": "recommendation",
            "entity_id": str(recommendation_id),
            "action": action,
            "previous_status": "proposed",
            "new_status": status,
            "performed_by_user_id": str(uuid4()),
            "assigned_to_user_id": None,
            "comment": None,
            "performed_at": datetime.now(timezone.utc).isoformat(),
            "idempotency_key": None,
        },
        "status": status,
        "message": "Recommendation workflow action recorded.",
    }


def test_accept_recommendation_endpoint_returns_workflow_mutation(monkeypatch):
    recommendation_id = uuid4()

    def fake_apply_recommendation_action(**kwargs):
        assert kwargs["recommendation_id"] == recommendation_id
        assert kwargs["action"].value == "accept"
        assert kwargs["actor"].id == "platform-admin"
        return workflow_response(recommendation_id)

    monkeypatch.setattr(
        "app.api.recommendations.workflow_service.apply_recommendation_action",
        fake_apply_recommendation_action,
    )

    response = client.post(
        f"/recommendations/{recommendation_id}/accept?user_id=platform-admin"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow_action"]["entity_type"] == "recommendation"
    assert payload["workflow_action"]["action"] == "accept"
    assert payload["status"] == "accepted"


def test_reject_recommendation_endpoint_passes_comment(monkeypatch):
    recommendation_id = uuid4()

    def fake_apply_recommendation_action(**kwargs):
        assert kwargs["comment"] == "Forecast signal is too weak."
        return workflow_response(
            recommendation_id,
            action="reject",
            status="rejected",
        )

    monkeypatch.setattr(
        "app.api.recommendations.workflow_service.apply_recommendation_action",
        fake_apply_recommendation_action,
    )

    response = client.post(
        f"/recommendations/{recommendation_id}/reject",
        json={"comment": "Forecast signal is too weak."},
    )

    assert response.status_code == 200
    assert response.json()["workflow_action"]["action"] == "reject"


def test_assign_recommendation_endpoint_requires_assignee():
    response = client.post(f"/recommendations/{uuid4()}/assign", json={})

    assert response.status_code == 422


def test_recommendation_workflow_endpoint_requires_write_permission(monkeypatch):
    def fail_if_called(**kwargs):
        raise AssertionError("workflow service should not be called")

    monkeypatch.setattr(
        "app.api.recommendations.workflow_service.apply_recommendation_action",
        fail_if_called,
    )

    response = client.post(
        f"/recommendations/{uuid4()}/accept?user_id=read-only-viewer"
    )

    assert response.status_code == 403


def test_resolve_recommendation_maps_invalid_transition_to_conflict(monkeypatch):
    from app.domain.workflow import WorkflowTransitionError

    def fake_apply_recommendation_action(**kwargs):
        raise WorkflowTransitionError(
            "Workflow transition is not allowed: recommendation resolve proposed -> implemented."
        )

    monkeypatch.setattr(
        "app.api.recommendations.workflow_service.apply_recommendation_action",
        fake_apply_recommendation_action,
    )

    response = client.post(f"/recommendations/{uuid4()}/resolve")

    assert response.status_code == 409


def test_dismiss_recommendation_endpoint_returns_rejected_status(monkeypatch):
    recommendation_id = uuid4()

    def fake_apply_recommendation_action(**kwargs):
        assert kwargs["comment"] == "Duplicate recommendation."
        return workflow_response(
            recommendation_id,
            action="dismiss",
            status="rejected",
        )

    monkeypatch.setattr(
        "app.api.recommendations.workflow_service.apply_recommendation_action",
        fake_apply_recommendation_action,
    )

    response = client.post(
        f"/recommendations/{recommendation_id}/dismiss",
        json={"comment": "Duplicate recommendation."},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"
