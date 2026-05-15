from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


def error_response(code: str, message: str, details: list[dict] | None = None) -> dict:
    payload = {
        "error": {
            "code": code,
            "message": message,
        },
    }

    if details is not None:
        payload["error"]["details"] = details

    return payload


def _http_error_code(status_code: int) -> str:
    return {
        status.HTTP_400_BAD_REQUEST: "bad_request",
        status.HTTP_401_UNAUTHORIZED: "unauthorized",
        status.HTTP_403_FORBIDDEN: "forbidden",
        status.HTTP_404_NOT_FOUND: "not_found",
        status.HTTP_409_CONFLICT: "conflict",
    }.get(status_code, "http_error")


def _http_error_message(status_code: int) -> str:
    return {
        status.HTTP_400_BAD_REQUEST: "Bad request",
        status.HTTP_401_UNAUTHORIZED: "Unauthorized",
        status.HTTP_403_FORBIDDEN: "Forbidden",
        status.HTTP_404_NOT_FOUND: "Resource not found",
        status.HTTP_409_CONFLICT: "Conflict",
    }.get(status_code, "HTTP error")


def _normalize_http_exception_detail(status_code: int, detail: object) -> dict:
    default_code = _http_error_code(status_code)
    default_message = _http_error_message(status_code)

    if isinstance(detail, dict):
        normalized = error_response(
            code=str(detail.get("code") or default_code),
            message=str(detail.get("message") or default_message),
        )
        details = detail.get("details")
        if isinstance(details, list):
            normalized["error"]["details"] = details
        return normalized

    if isinstance(detail, str) and detail.strip():
        return error_response(code=default_code, message=detail)

    return error_response(code=default_code, message=default_message)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request,  # noqa: ARG001 - FastAPI exception handler signature
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_normalize_http_exception_detail(exc.status_code, exc.detail),
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_exception_handler(
        request: Request,  # noqa: ARG001 - FastAPI exception handler signature
        exc: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=error_response(
                code="validation_error",
                message="Request validation failed",
                details=[
                    {
                        "loc": list(error.get("loc", [])),
                        "msg": str(error.get("msg", "")),
                        "type": str(error.get("type", "")),
                    }
                    for error in exc.errors()
                ],
            ),
        )
