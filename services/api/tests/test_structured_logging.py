import json
import logging

from app.core.logging import (
    CorrelationIdFilter,
    JsonLogFormatter,
    correlation_id_context,
)


def test_json_log_formatter_emits_structured_payload() -> None:
    token = correlation_id_context.set("request-123")
    try:
        record = logging.LogRecord(
            name="app.test",
            level=logging.INFO,
            pathname=__file__,
            lineno=12,
            msg="request completed",
            args=(),
            exc_info=None,
        )
        record.http_method = "GET"
        record.http_path = "/health"
        record.http_status_code = 200

        CorrelationIdFilter().filter(record)
        output = JsonLogFormatter().format(record)
        payload = json.loads(output)

        assert payload["level"] == "INFO"
        assert payload["logger"] == "app.test"
        assert payload["message"] == "request completed"
        assert payload["correlation_id"] == "request-123"
        assert payload["http_method"] == "GET"
        assert payload["http_path"] == "/health"
        assert payload["http_status_code"] == 200
        assert "timestamp" in payload
    finally:
        correlation_id_context.reset(token)


def test_json_log_formatter_redacts_sensitive_fields() -> None:
    record = logging.LogRecord(
        name="app.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=40,
        msg="request completed",
        args=(),
        exc_info=None,
    )
    record.authorization = "Bearer secret-token"
    record.metadata = {
        "password": "super-secret",
        "nested": {
            "api_token": "abc123",
        },
    }

    output = JsonLogFormatter().format(record)
    payload = json.loads(output)

    assert payload["authorization"] == "[REDACTED]"
    assert payload["metadata"]["password"] == "[REDACTED]"
    assert payload["metadata"]["nested"]["api_token"] == "[REDACTED]"
