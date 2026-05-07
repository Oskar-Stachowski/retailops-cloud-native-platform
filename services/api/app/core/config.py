import os
from functools import lru_cache

from pydantic import BaseModel


DEFAULT_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]


def parse_cors_origins(value: str | None) -> list[str]:
    if not value:
        return DEFAULT_CORS_ORIGINS

    return [origin.strip() for origin in value.split(",") if origin.strip()]


class Settings(BaseModel):
    app_env: str = "local"
    database_url: str | None = None
    cors_origins: list[str] = DEFAULT_CORS_ORIGINS
    broker_bootstrap_servers: str | None = None
    broker_group_id: str = "retailops-api-consumer"
    broker_client_id: str = "retailops-api"


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
    )


settings = get_settings()
