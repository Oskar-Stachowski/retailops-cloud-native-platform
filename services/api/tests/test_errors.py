from fastapi import FastAPI, HTTPException, Query
from fastapi.testclient import TestClient

from app.api.errors import register_exception_handlers
from app.main import app

client = TestClient(app)


def build_error_test_client() -> TestClient:
    test_app = FastAPI()
    register_exception_handlers(test_app)

    @test_app.get("/string-400")
    def string_400() -> None:
        raise HTTPException(status_code=400, detail="Limit must be positive.")

    @test_app.get("/dict-403")
    def dict_403() -> None:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "permission_denied",
                "message": "Workflow write permission is required.",
            },
        )

    @test_app.get("/dict-404")
    def dict_404(user_id: str = Query()) -> None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "demo_user_not_found",
                "message": f"Demo user '{user_id}' does not exist.",
            },
        )

    @test_app.get("/query-limit")
    def query_limit(limit: int = Query(ge=1)) -> dict[str, int]:
        return {"limit": limit}

    return TestClient(test_app)


def test_unknown_route() -> None:
    response = client.get("/does-not-exist")
    assert response.status_code == 404

    body = response.json()
    assert "error" in body
    assert body["error"]["code"] == "not_found"
    assert body["error"]["message"] == "Not Found"


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


def test_string_http_exception_maps_to_controlled_error_contract() -> None:
    response = build_error_test_client().get("/string-400")

    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": "bad_request",
            "message": "Limit must be positive.",
        },
    }


def test_structured_http_exception_preserves_code_and_message_for_404() -> None:
    response = build_error_test_client().get("/dict-404?user_id=unknown-user")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "demo_user_not_found",
            "message": "Demo user 'unknown-user' does not exist.",
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


def test_validation_response_uses_controlled_error_contract_on_test_app() -> None:
    response = build_error_test_client().get("/query-limit?limit=0")

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["message"] == "Request validation failed"
    assert body["error"]["details"][0]["loc"] == ["query", "limit"]
