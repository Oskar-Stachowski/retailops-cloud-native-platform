import os
from functools import lru_cache

from pydantic import BaseModel

DEFAULT_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]

DEFAULT_BROKER_TOPICS = [
    "retailops.sales.v1",
    "retailops.inventory.v1",
    "retailops.pricing.v1",
    "retailops.intelligence.v1",
    "retailops.operations.v1",
]


def parse_csv_values(value: str | None, default: list[str]) -> list[str]:
    if not value:
        return list(default)

    return [item.strip() for item in value.split(",") if item.strip()]


def parse_cors_origins(value: str | None) -> list[str]:
    return parse_csv_values(value, DEFAULT_CORS_ORIGINS)


def parse_bool(value: str | None, *, default: bool = False) -> bool:
    if value is None or value.strip() == "":
        return default

    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False

    return default


def parse_float(value: str | None, default: float) -> float:
    if value is None or value.strip() == "":
        return default

    try:
        return float(value)
    except ValueError:
        return default


class Settings(BaseModel):
    app_env: str = "local"
    database_url: str | None = None
    cors_origins: list[str] = DEFAULT_CORS_ORIGINS
    broker_bootstrap_servers: str | None = None
    broker_group_id: str = "retailops-api-consumer"
    broker_client_id: str = "retailops-api"
    broker_topics: list[str] = DEFAULT_BROKER_TOPICS
    otel_enabled: bool = False
    otel_service_name: str = "retailops-api"
    otel_exporter: str = "console"
    otel_otlp_endpoint: str | None = None
    otel_trace_sample_rate: float = 1.0
    otel_excluded_urls: str = "/health,/ready,/metrics"


@lru_cache
def get_settings() -> Settings:
    return Settings(
        app_env=os.getenv("APP_ENV", "local"),
        database_url=os.getenv("DATABASE_URL"),
        cors_origins=parse_cors_origins(os.getenv("CORS_ORIGINS")),
        broker_bootstrap_servers=os.getenv("RETAILOPS_BROKER_BOOTSTRAP_SERVERS"),
        broker_group_id=os.getenv(
            "RETAILOPS_BROKER_GROUP_ID",
            "retailops-api-consumer",
        ),
        broker_client_id=os.getenv(
            "RETAILOPS_BROKER_CLIENT_ID",
            "retailops-api",
        ),
        broker_topics=parse_csv_values(
            os.getenv("RETAILOPS_BROKER_TOPICS"),
            DEFAULT_BROKER_TOPICS,
        ),
        otel_enabled=parse_bool(os.getenv("RETAILOPS_OTEL_ENABLED")),
        otel_service_name=os.getenv("RETAILOPS_OTEL_SERVICE_NAME", "retailops-api"),
        otel_exporter=os.getenv("RETAILOPS_OTEL_EXPORTER", "console"),
        otel_otlp_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"),
        otel_trace_sample_rate=parse_float(
            os.getenv("RETAILOPS_OTEL_TRACE_SAMPLE_RATE"),
            1.0,
        ),
        otel_excluded_urls=os.getenv(
            "RETAILOPS_OTEL_EXCLUDED_URLS",
            "/health,/ready,/metrics",
        ),
    )


settings = get_settings()
