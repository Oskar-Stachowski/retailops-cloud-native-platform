from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_ready_endpoint_returns_200_when_database_is_available(monkeypatch):
    monkeypatch.setattr(
        "app.api.health.check_database_connection",
        lambda: True,
    )

    response = client.get("/ready")

    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "retailops-api"
    assert body["environment"] == "local"
    assert body["database"] == "ok"


def test_ready_endpoint_returns_503_when_database_is_unavailable(monkeypatch):
    monkeypatch.setattr(
        "app.api.health.check_database_connection",
        lambda: False,
    )

    response = client.get("/ready")

    assert response.status_code == 503

    body = response.json()
    assert body["error"]["code"] == "database_unavailable"
    assert body["error"]["message"] == "Database is not available."
