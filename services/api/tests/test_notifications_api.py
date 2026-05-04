from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_notifications_are_filtered_by_selected_demo_user():
    response = client.get("/notifications?user_id=inventory-planner")

    assert response.status_code == 200
    payload = response.json()

    assert payload["user"]["id"] == "inventory-planner"
    assert payload["total_count"] >= 1
    assert all(
        item["target_role"] in {"inventory_planner"}
        for item in payload["items"]
    )


def test_platform_admin_can_see_cross_role_notifications():
    response = client.get("/notifications?user_id=platform-admin")

    assert response.status_code == 200
    payload = response.json()

    target_roles = {item["target_role"] for item in payload["items"]}
    assert "inventory_planner" in target_roles
    assert "operations_manager" in target_roles
    assert "platform_admin" in target_roles


def test_read_only_user_cannot_use_notification_write_api():
    response = client.post(
        "/notifications/stockout-beauty-cream/read?user_id=read-only-viewer"
    )

    assert response.status_code == 403


def test_platform_admin_can_mark_notification_read():
    before_response = client.get("/notifications?user_id=platform-admin")
    before_payload = before_response.json()
    notification_id = before_payload["items"][0]["id"]

    response = client.post(
        f"/notifications/{notification_id}/read?user_id=platform-admin"
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["notification"]["id"] == notification_id
    assert payload["notification"]["status"] == "read"
    assert payload["notification"]["read_at"] is not None
    assert payload["unread_count"] == before_payload["unread_count"] - 1
