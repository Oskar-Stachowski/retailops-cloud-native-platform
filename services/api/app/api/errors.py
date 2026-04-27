from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


def error_response(code: str, message: str) -> dict:
    return {
        "error": {
            "code": code,
            "message": message,
        }
    }


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        if exc.status_code == 404:
            return JSONResponse(
                status_code=404,
                content=error_response(
                    code="not_found",
                    message="Resource not found",
                ),
            )

        return JSONResponse(
            status_code=exc.status_code,
            content=error_response(
                code="http_error",
                message="HTTP error",
            ),
        )