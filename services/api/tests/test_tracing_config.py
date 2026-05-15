"""Unit checks for optional OpenTelemetry tracing configuration."""

from fastapi import FastAPI

from app.core.config import Settings
from app.core.tracing import configure_tracing


def test_tracing_is_disabled_by_default_for_local_development() -> None:
    app = FastAPI()
    settings = Settings(otel_enabled=False)

    assert configure_tracing(app, settings) is False
    assert app.state.otel_instrumented is False


def test_tracing_can_be_enabled_with_console_exporter() -> None:
    app = FastAPI()
    settings = Settings(
        app_env="test",
        otel_enabled=True,
        otel_exporter="console",
        otel_service_name="retailops-api-test",
        otel_trace_sample_rate=0.25,
    )

    assert configure_tracing(app, settings) is True
    assert app.state.otel_instrumented is True


def test_tracing_rejects_unknown_exporter() -> None:
    app = FastAPI()
    settings = Settings(otel_enabled=True, otel_exporter="unknown")

    try:
        configure_tracing(app, settings)
    except ValueError as exc:
        assert "Unsupported RETAILOPS_OTEL_EXPORTER" in str(exc)
    else:
        raise AssertionError("configure_tracing should reject an unsupported exporter")
