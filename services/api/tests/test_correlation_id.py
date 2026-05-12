from uuid import UUID

from fastapi.testclient import TestClient

from app.core.correlation import CORRELATION_ID_HEADER
from app.main import app

client = TestClient(app)


def test_correlation_id_header_is_generated_for_requests() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert UUID(response.headers[CORRELATION_ID_HEADER])


def test_correlation_id_header_preserves_incoming_value() -> None:
    correlation_id = "checkout-flow-123"

    response = client.get(
        "/health",
        headers={CORRELATION_ID_HEADER: correlation_id},
    )

    assert response.status_code == 200
    assert response.headers[CORRELATION_ID_HEADER] == correlation_id


def test_correlation_id_header_is_returned_for_error_responses() -> None:
    correlation_id = "missing-resource-123"

    response = client.get(
        "/does-not-exist",
        headers={CORRELATION_ID_HEADER: correlation_id},
    )

    assert response.status_code == 404
    assert response.headers[CORRELATION_ID_HEADER] == correlation_id
    assert response.json()["error"]["code"] == "not_found"
