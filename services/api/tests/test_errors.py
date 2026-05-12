from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_unknown_route() -> None:
    response = client.get("/does-not-exist")
    assert response.status_code == 404

    body = response.json()
    assert "error" in body
    assert body["error"]["code"] == "not_found"
    assert body["error"]["message"] == "Resource not found"


def test_forbidden_response_uses_controlled_error_contract() -> None:
    response = client.post("/notifications/stockout-beauty-cream/read?user_id=read-only-viewer")
    assert response.status_code == 403

    body = response.json()
    assert body == {
        "error": {
            "code": "permission_denied",
            "message": "Permission 'notifications:write' is required for this action.",
        },
    }


def test_validation_response_uses_controlled_error_contract() -> None:
    response = client.get("/products?limit=0")
    assert response.status_code == 422

    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["message"] == "Request validation failed"
    assert body["error"]["details"]
    assert body["error"]["details"][0]["loc"] == ["query", "limit"]
