import psycopg
import logging

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def check_database_connection() -> bool:
    settings = get_settings()

    if not settings.database_url:
        return False

    try:
        with psycopg.connect(settings.database_url, connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                result = cur.fetchone()

        return result == (1,)

    except psycopg.Error as e:
        logger.error(
            "DB connection failed",
            extra={"db_url": settings.database_url},
            exc_info=e
        )
        return False
