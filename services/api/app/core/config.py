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


class Settings(BaseModel):
    app_env: str = "local"
    database_url: str | None = None
    cors_origins: list[str] = DEFAULT_CORS_ORIGINS
    broker_bootstrap_servers: str | None = None
    broker_group_id: str = "retailops-api-consumer"
    broker_client_id: str = "retailops-api"
    broker_topics: list[str] = DEFAULT_BROKER_TOPICS


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
    )


settings = get_settings()
