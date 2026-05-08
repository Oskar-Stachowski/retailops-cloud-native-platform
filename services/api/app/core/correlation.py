from __future__ import annotations

import logging
import time
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import correlation_id_context


CORRELATION_ID_HEADER = "X-Correlation-ID"
logger = logging.getLogger("app.request")


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
        token = correlation_id_context.set(correlation_id)
        started_at = time.perf_counter()

        try:
            response = await call_next(request)
            response.headers[CORRELATION_ID_HEADER] = correlation_id
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            logger.info(
                "HTTP request completed",
                extra={
                    "http_method": request.method,
                    "http_path": request.url.path,
                    "http_status_code": response.status_code,
                    "duration_ms": duration_ms,
                },
            )
            return response
        finally:
            correlation_id_context.reset(token)
