from __future__ import annotations

from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


CORRELATION_ID_HEADER = "X-Correlation-ID"


def resolve_correlation_id(request: Request) -> str:
    correlation_id = request.headers.get(CORRELATION_ID_HEADER, "").strip()
    if correlation_id:
        return correlation_id

    return str(uuid4())


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        correlation_id = resolve_correlation_id(request)
        request.state.correlation_id = correlation_id

        response = await call_next(request)
        response.headers[CORRELATION_ID_HEADER] = correlation_id
        return response
