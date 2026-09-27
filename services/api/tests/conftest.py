import os

import psycopg
import pytest

from data.generator.main import DatasetGenerationConfig
from ml.models.random_forest_forecast import (
    RandomForestForecastConfig,
    train_random_forest_forecast_model,
)


def _requires_db(item: pytest.Item) -> bool:
    return item.get_closest_marker("integration_db") is not None


def _db_unavailable_reason(database_url: str | None) -> str | None:
    if not database_url:
        return "DATABASE_URL is not set"

    try:
        with (
            psycopg.connect(database_url, connect_timeout=3) as connection,
            connection.cursor() as cursor,
        ):
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except psycopg.Error as exc:
        return f"database is unavailable for DATABASE_URL={database_url!r}: {exc}"

    return None


def pytest_runtest_setup(item: pytest.Item) -> None:
    if not _requires_db(item):
        return

    reason = _db_unavailable_reason(os.getenv("DATABASE_URL"))

    if reason is None:
        return

    message = f"integration DB test cannot run: {reason}"

    if os.getenv("REQUIRE_DB_TESTS") == "1":
        pytest.fail(
            f"{message}; REQUIRE_DB_TESTS=1 is set, so DB tests must fail instead of skip",
            pytrace=False,
        )

    pytest.skip(message)


@pytest.fixture(scope="session")
def database_url() -> str:
    value = os.getenv("DATABASE_URL")

    if not value:
        pytest.fail("DATABASE_URL is required for this integration DB test", pytrace=False)

    return value


@pytest.fixture
def assessed_rf_run_dir(tmp_path):
    directory = tmp_path / "assessed_rf"
    train_random_forest_forecast_model(
        RandomForestForecastConfig(
            dataset=DatasetGenerationConfig(
                profile="small", days=42, products=8, stores=2, warehouses=2, seed=42,
            ),
            window_days=7,
            horizon_days=7,
            n_estimators=8,
            output_dir=directory,
        ),
    )
    return directory
