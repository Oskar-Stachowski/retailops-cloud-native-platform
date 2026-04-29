from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)


def test_unknown_route():
    response = client.get("/does-not-exist")
    assert response.status_code == 404

    body = response.json()
    assert "error" in body
    assert body["error"]["code"] == "not_found"
    assert body["error"]["message"] == "Resource not found"
