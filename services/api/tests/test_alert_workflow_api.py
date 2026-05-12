from datetime import UTC, datetime
from typing import Never
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def workflow_response(alert_id, action="acknowledge", status="acknowledged"):
    return {
        "workflow_action": {
            "id": str(uuid4()),
            "entity_type": "alert",
            "entity_id": str(alert_id),
            "action": action,
            "previous_status": "open",
            "new_status": status,
            "performed_by_user_id": str(uuid4()),
            "assigned_to_user_id": None,
            "comment": None,
            "performed_at": datetime.now(UTC).isoformat(),
            "idempotency_key": None,
        },
        "status": status,
        "message": "Alert workflow action recorded.",
    }


def test_acknowledge_alert_endpoint_returns_workflow_mutation(monkeypatch) -> None:
    alert_id = uuid4()

    def fake_apply_alert_action(**kwargs):
        assert kwargs["alert_id"] == alert_id
        assert kwargs["action"].value == "acknowledge"
        assert kwargs["actor"].id == "platform-admin"
        return workflow_response(alert_id)

    monkeypatch.setattr(
        "app.api.alerts.workflow_service.apply_alert_action",
        fake_apply_alert_action,
    )

    response = client.post(f"/alerts/{alert_id}/acknowledge?user_id=platform-admin")

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow_action"]["entity_type"] == "alert"
    assert payload["workflow_action"]["action"] == "acknowledge"
    assert payload["status"] == "acknowledged"


def test_ops_manager_can_perform_alert_workflow_action(monkeypatch) -> None:
    alert_id = uuid4()

    def fake_apply_alert_action(**kwargs):
        assert kwargs["actor"].id == "ops-manager"
        return workflow_response(alert_id)

    monkeypatch.setattr(
        "app.api.alerts.workflow_service.apply_alert_action",
        fake_apply_alert_action,
    )

    response = client.post(f"/alerts/{alert_id}/acknowledge?user_id=ops-manager")

    assert response.status_code == 200


def test_assign_alert_endpoint_requires_assignee() -> None:
    response = client.post(f"/alerts/{uuid4()}/assign", json={})

    assert response.status_code == 422


def test_alert_workflow_endpoint_rejects_viewer_without_write_permission(monkeypatch) -> None:
    def fail_if_called(**kwargs) -> Never:  # noqa: ARG001 - callback accepts endpoint kwargs
        msg = "workflow service should not be called"
        raise AssertionError(msg)

    monkeypatch.setattr(
        "app.api.alerts.workflow_service.apply_alert_action",
        fail_if_called,
    )

    response = client.post(f"/alerts/{uuid4()}/acknowledge?user_id=read-only-viewer")

    assert response.status_code == 403


def test_alert_workflow_endpoint_rejects_analyst_without_write_permission(monkeypatch) -> None:
    def fail_if_called(**kwargs) -> Never:  # noqa: ARG001 - callback accepts endpoint kwargs
        msg = "workflow service should not be called"
        raise AssertionError(msg)

    monkeypatch.setattr(
        "app.api.alerts.workflow_service.apply_alert_action",
        fail_if_called,
    )

    response = client.post(f"/alerts/{uuid4()}/acknowledge?user_id=commercial-analyst")

    assert response.status_code == 403


def test_assign_alert_endpoint_passes_assignee_to_service(monkeypatch) -> None:
    alert_id = uuid4()
    assignee_id = uuid4()

    def fake_apply_alert_action(**kwargs):
        assert kwargs["assigned_to_user_id"] == assignee_id
        response_payload = workflow_response(
            alert_id,
            action="assign",
            status="in_progress",
        )
        response_payload["workflow_action"]["assigned_to_user_id"] = str(assignee_id)
        return response_payload

    monkeypatch.setattr(
        "app.api.alerts.workflow_service.apply_alert_action",
        fake_apply_alert_action,
    )

    response = client.post(
        f"/alerts/{alert_id}/assign",
        json={
            "assigned_to_user_id": str(assignee_id),
            "comment": "Assigning to inventory planning.",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "in_progress"
    assert payload["workflow_action"]["assigned_to_user_id"] == str(assignee_id)


def test_dismiss_alert_endpoint_maps_invalid_transition_to_conflict(monkeypatch) -> None:
    from app.domain.workflow import WorkflowTransitionError

    def fake_apply_alert_action(**kwargs) -> Never:  # noqa: ARG001 - callback accepts endpoint kwargs
        msg = "Comment is required for dismiss actions."
        raise WorkflowTransitionError(msg)

    monkeypatch.setattr(
        "app.api.alerts.workflow_service.apply_alert_action",
        fake_apply_alert_action,
    )

    response = client.post(
        f"/alerts/{uuid4()}/dismiss",
        json={"comment": "This signal is a duplicate."},
    )

    assert response.status_code == 409


def test_comment_alert_endpoint_keeps_status(monkeypatch) -> None:
    alert_id = uuid4()

    def fake_apply_alert_action(**kwargs):
        assert kwargs["comment"] == "Checking supplier lead time."
        return workflow_response(alert_id, action="comment", status="in_progress")

    monkeypatch.setattr(
        "app.api.alerts.workflow_service.apply_alert_action",
        fake_apply_alert_action,
    )

    response = client.post(
        f"/alerts/{alert_id}/comment",
        json={"comment": "Checking supplier lead time."},
    )

    assert response.status_code == 200
    assert response.json()["workflow_action"]["action"] == "comment"
