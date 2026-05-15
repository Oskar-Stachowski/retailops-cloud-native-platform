from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
    SpanProcessor,
)
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

from app.core.config import settings as default_settings

if TYPE_CHECKING:
    from fastapi import FastAPI

    from app.core.config import Settings

logger = logging.getLogger("app.tracing")
_PROVIDER_CONFIGURED = False


def _normalized_sample_rate(value: float) -> float:
    if value < 0:
        return 0.0
    if value > 1:
        return 1.0
    return value


def _normalize_exporter(value: str) -> str:
    exporter = value.strip().lower()
    if exporter not in {"console", "otlp"}:
        message = (
            "Unsupported RETAILOPS_OTEL_EXPORTER value. "
            "Use 'console' for local smoke tests or 'otlp' for an OTLP collector.",
        )
        raise ValueError(message)

    return exporter


def _build_span_processor(app_settings: Settings) -> SpanProcessor:
    exporter = _normalize_exporter(app_settings.otel_exporter)

    if exporter == "console":
        return SimpleSpanProcessor(ConsoleSpanExporter())

    if exporter == "otlp":
        if app_settings.otel_otlp_endpoint:
            return BatchSpanProcessor(
                OTLPSpanExporter(endpoint=app_settings.otel_otlp_endpoint),
            )

        return BatchSpanProcessor(OTLPSpanExporter())

    raise AssertionError


def _configure_provider(app_settings: Settings) -> TracerProvider:
    # OpenTelemetry tracer provider is process-global, so this guard is intentional.
    global _PROVIDER_CONFIGURED  # noqa: PLW0603

    _normalize_exporter(app_settings.otel_exporter)

    if _PROVIDER_CONFIGURED:
        provider = trace.get_tracer_provider()
        if isinstance(provider, TracerProvider):
            return provider

    provider = TracerProvider(
        resource=Resource.create(
            {
                "service.name": app_settings.otel_service_name,
                "deployment.environment": app_settings.app_env,
            },
        ),
        sampler=TraceIdRatioBased(
            _normalized_sample_rate(app_settings.otel_trace_sample_rate),
        ),
    )
    provider.add_span_processor(_build_span_processor(app_settings))
    trace.set_tracer_provider(provider)
    _PROVIDER_CONFIGURED = True

    return provider


def configure_tracing(
    app: FastAPI,
    app_settings: Settings | None = None,
) -> bool:
    """Configure optional OpenTelemetry tracing for the FastAPI app.

    Tracing is disabled by default to keep the local developer experience light.
    Enable it with RETAILOPS_OTEL_ENABLED=true and choose either console or
    OTLP export with RETAILOPS_OTEL_EXPORTER.
    """
    resolved_settings = app_settings or default_settings

    if not resolved_settings.otel_enabled:
        app.state.otel_instrumented = False
        return False

    if getattr(app.state, "otel_instrumented", False):
        return True

    provider = _configure_provider(resolved_settings)
    FastAPIInstrumentor.instrument_app(
        app,
        tracer_provider=provider,
        excluded_urls=resolved_settings.otel_excluded_urls,
    )
    app.state.otel_instrumented = True

    logger.info(
        "OpenTelemetry tracing enabled",
        extra={
            "otel_service_name": resolved_settings.otel_service_name,
            "otel_exporter": resolved_settings.otel_exporter,
            "otel_trace_sample_rate": _normalized_sample_rate(
                resolved_settings.otel_trace_sample_rate,
            ),
            "otel_excluded_urls": resolved_settings.otel_excluded_urls,
        },
    )
    return True
