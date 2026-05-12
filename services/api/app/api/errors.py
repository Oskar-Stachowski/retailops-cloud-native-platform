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


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request,  # noqa: ARG001 - FastAPI exception handler signature
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        if isinstance(exc.detail, dict):
            code = str(exc.detail.get("code") or _http_error_code(exc.status_code))
            message = str(exc.detail.get("message") or _http_error_message(exc.status_code))

            return JSONResponse(
                status_code=exc.status_code,
                content=error_response(code=code, message=message),
            )

        return JSONResponse(
            status_code=exc.status_code,
            content=error_response(
                code=_http_error_code(exc.status_code),
                message=_http_error_message(exc.status_code),
            ),
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
