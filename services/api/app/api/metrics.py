from fastapi import APIRouter, status
from fastapi.responses import PlainTextResponse
from prometheus_client import CollectorRegistry, Gauge, generate_latest

from app.core.config import settings
from app.db.instrumentation import render_database_metrics
from app.services.stream_observability import StreamObservabilityService

router = APIRouter(tags=["observability"])
stream_observability_service = StreamObservabilityService()


def render_api_info_metric() -> str:
    registry = CollectorRegistry()
    metric = Gauge(
        "retailops_api_info",
        "RetailOps API service information.",
        labelnames=("service", "environment"),
        registry=registry,
    )
    metric.labels(service="retailops-api", environment=settings.app_env).set(1)
    return generate_latest(registry).decode("utf-8").rstrip()


@router.get(
    "/metrics",
    response_class=PlainTextResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Prometheus metrics",
    description=(
        "Returns application metrics in Prometheus text exposition format. "
        "Sprint 11 exposes API service metadata and Sprint 9 real-time stream "
        "processing metrics derived from the persisted event log and consumer "
        "state tables."
    ),
)
def get_metrics() -> PlainTextResponse:
    payload = "\n".join(
        [
            render_api_info_metric(),
            render_database_metrics(),
            stream_observability_service.render_prometheus_metrics().rstrip(),
            "",
        ],
    )

    return PlainTextResponse(
        payload,
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
