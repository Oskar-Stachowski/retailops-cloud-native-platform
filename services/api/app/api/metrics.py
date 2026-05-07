from fastapi import APIRouter, status
from fastapi.responses import PlainTextResponse

from app.services.stream_observability import StreamObservabilityService


router = APIRouter(tags=["observability"])
stream_observability_service = StreamObservabilityService()


@router.get(
    "/metrics",
    response_class=PlainTextResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Prometheus metrics",
    description=(
        "Returns application metrics in Prometheus text exposition format. "
        "Sprint 9 includes real-time stream processing metrics derived from "
        "the persisted event log and consumer state tables."
    ),
)
def get_metrics() -> PlainTextResponse:
    return PlainTextResponse(
        stream_observability_service.render_prometheus_metrics(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
