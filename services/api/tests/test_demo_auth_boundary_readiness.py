"""Production-readiness checks for explicit demo-auth boundaries."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
ZERO_UUID = "00000000-0000-0000-0000-000000000000"


def test_identity_contract_declares_local_mock_auth_boundary() -> None:
    response = client.get("/me?user_id=platform-admin")

    assert response.status_code == 200
    payload = response.json()

    assert payload["auth_mode"] == "local_mock"
    assert "does not implement real login" in payload["scope_boundary"]
    assert "JWT" in payload["scope_boundary"]
    assert "production RBAC" in payload["scope_boundary"]


def test_read_only_viewer_cannot_mutate_alert_workflow_before_service_call() -> None:
    response = client.post(f"/alerts/{ZERO_UUID}/acknowledge?user_id=read-only-viewer")

    assert response.status_code == 403


def test_read_only_viewer_cannot_mutate_recommendation_workflow_before_service_call() -> None:
    response = client.post(
        f"/recommendations/{ZERO_UUID}/accept?user_id=read-only-viewer",
    )

    assert response.status_code == 403


def test_unknown_demo_user_is_rejected_explicitly() -> None:
    response = client.get("/me?user_id=unknown-user")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "demo_user_not_found"
