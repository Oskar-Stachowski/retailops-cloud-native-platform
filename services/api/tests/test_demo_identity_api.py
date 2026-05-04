from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_me_returns_default_platform_admin_user():
    response = client.get("/me")

    assert response.status_code == 200
    payload = response.json()

    assert payload["auth_mode"] == "local_mock"
    assert payload["user"]["id"] == "platform-admin"
    assert payload["user"]["role"] == "platform_admin"
    assert "platform:admin" in payload["user"]["permissions"]


def test_demo_users_are_available_for_frontend_switcher():
    response = client.get("/users/demo")

    assert response.status_code == 200
    payload = response.json()

    assert payload["default_user_id"] == "platform-admin"
    assert len(payload["items"]) >= 4
    assert {user["id"] for user in payload["items"]} >= {
        "platform-admin",
        "ops-manager",
        "inventory-planner",
    }


def test_non_admin_user_has_no_platform_admin_permission():
    response = client.get("/me/permissions?user_id=inventory-planner")

    assert response.status_code == 200
    payload = response.json()

    assert payload["role"] == "inventory_planner"
    assert "inventory:read" in payload["permissions"]
    assert "platform:admin" not in payload["permissions"]


def test_unknown_demo_user_returns_404():
    response = client.get("/me?user_id=unknown-user")

    assert response.status_code == 404
