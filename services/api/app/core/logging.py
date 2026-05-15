from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from logging.config import dictConfig
from typing import Any

correlation_id_context: ContextVar[str | None] = ContextVar(
    "correlation_id",
    default=None,
)


_STANDARD_LOG_RECORD_FIELDS = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "message",
    "module",
    "msecs",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
}

_REDACTED_VALUE = "[REDACTED]"
_SENSITIVE_FIELD_TOKENS = (
    "authorization",
    "password",
    "secret",
    "token",
)


def _is_sensitive_field(key: str) -> bool:
    normalized = key.strip().lower().replace("-", "_")
    return any(token in normalized for token in _SENSITIVE_FIELD_TOKENS)


def _redact_log_value(key: str, value: object) -> object:
    if _is_sensitive_field(key):
        return _REDACTED_VALUE

    if isinstance(value, dict):
        return {
            nested_key: _redact_log_value(nested_key, nested_value)
            for nested_key, nested_value in value.items()
        }

    if isinstance(value, list):
        return [_redact_log_value(key, item) for item in value]

    if isinstance(value, tuple):
        return tuple(_redact_log_value(key, item) for item in value)

    return value


class CorrelationIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = correlation_id_context.get()
        return True


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created,
                tz=UTC,
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": getattr(record, "correlation_id", None),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        for key, value in record.__dict__.items():
            if key in _STANDARD_LOG_RECORD_FIELDS or key == "correlation_id":
                continue
            payload[key] = _redact_log_value(key, value)

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str, separators=(",", ":"))


def configure_logging() -> None:
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {
                "correlation_id": {
                    "()": CorrelationIdFilter,
                },
            },
            "formatters": {
                "json": {
                    "()": JsonLogFormatter,
                },
            },
            "handlers": {
                "default": {
                    "class": "logging.StreamHandler",
                    "stream": sys.stdout,
                    "formatter": "json",
                    "filters": ["correlation_id"],
                },
            },
            "root": {
                "level": "INFO",
                "handlers": ["default"],
            },
            "loggers": {
                "uvicorn": {
                    "level": "INFO",
                    "handlers": ["default"],
                    "propagate": False,
                },
                "uvicorn.error": {
                    "level": "INFO",
                    "handlers": ["default"],
                    "propagate": False,
                },
                "uvicorn.access": {
                    "level": "INFO",
                    "handlers": ["default"],
                    "propagate": False,
                },
            },
        },
    )
