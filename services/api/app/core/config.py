import os
from functools import lru_cache
from pydantic import BaseModel


class Settings(BaseModel):
    app_env: str = "local"
    database_url: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings(
        app_env=os.getenv("APP_ENV", "local"),
        database_url=os.getenv("DATABASE_URL"),
    )
