"""Regression tests for seed database selection, without any real DB connection."""

from unittest.mock import MagicMock
from urllib.parse import urlsplit

import pytest
import test_seed_data as seed_tests
from psycopg.conninfo import conninfo_to_dict
from sqlalchemy.dialects.postgresql.psycopg import PGDialect_psycopg
from sqlalchemy.engine import make_url


@pytest.mark.parametrize(
    "query",
    [
        "",
        "?dbname=source",
        "?dbname=first&dbname=source",
        "?%64bname=source",
        "?db%6eame=first&dbname=source",
        "?dbname=source&%64bname=last",
        "?dbname=",
        "?sslmode=disable&application_name=seed%20probe&connect_timeout=3&dbname=source",
    ],
)
@pytest.mark.parametrize("name", ["postgres", "retailops_seed_test_probe"])
def test_both_drivers_select_requested_database(query: str, name: str) -> None:
    source_url = f"postgresql://demo:placeholder@127.0.0.1:5432/source{query}"
    isolated_url = seed_tests.database_url_for_name(source_url, name)
    libpq = conninfo_to_dict(isolated_url)
    _, sqlalchemy = PGDialect_psycopg().create_connect_args(make_url(isolated_url))

    assert urlsplit(isolated_url).path == f"/{name}"
    assert libpq["dbname"] == sqlalchemy["dbname"] == name
    for parameters in (libpq, sqlalchemy):
        assert parameters["user"] == "demo"
        assert parameters["password"] == "placeholder"
        assert parameters["host"] == "127.0.0.1"
        if "sslmode" in query:
            assert parameters["sslmode"] == "disable"
            assert parameters["application_name"] == "seed probe"
            assert str(parameters["connect_timeout"]) == "3"


def mock_connections(monkeypatch: pytest.MonkeyPatch, *, wrong_database: str | None = None):
    statements: list[tuple[str, str]] = []

    def connect(url, **_kwargs):
        selected = conninfo_to_dict(url)["dbname"]
        connection = MagicMock()
        connection.__enter__.return_value = connection

        def execute(query):
            text = query if isinstance(query, str) else query.as_string()
            statements.append((selected, text))
            result = MagicMock()
            if text == "SELECT current_database()":
                actual = "source" if selected == wrong_database else selected
                result.fetchone.return_value = (actual,)
            return result

        connection.execute.side_effect = execute
        return connection

    monkeypatch.setattr(seed_tests.psycopg, "connect", connect)
    monkeypatch.setattr(seed_tests, "uuid4", lambda: MagicMock(hex="probe"))
    return statements


@pytest.mark.parametrize("fail_body", [False, True])
def test_context_keeps_source_untouched_and_always_cleans_up(
    monkeypatch: pytest.MonkeyPatch, fail_body: bool
) -> None:
    statements = mock_connections(monkeypatch)
    try:
        with seed_tests.isolated_seed_database(
            "postgresql://demo:placeholder@127.0.0.1/source?dbname=source"
        ) as isolated_url:
            assert conninfo_to_dict(isolated_url)["dbname"] == "retailops_seed_test_probe"
            assert statements[-1] == ("retailops_seed_test_probe", "SELECT current_database()")
            if fail_body:
                raise RuntimeError("intentional seed failure")
    except RuntimeError as exc:
        assert fail_body and str(exc) == "intentional seed failure"

    assert {database for database, _ in statements} == {"postgres", "retailops_seed_test_probe"}
    assert statements[-2:] == [
        ("postgres", "SELECT current_database()"),
        ("postgres", 'DROP DATABASE "retailops_seed_test_probe" WITH (FORCE)'),
    ]


@pytest.mark.parametrize("wrong_database", ["postgres", "retailops_seed_test_probe"])
def test_unexpected_database_blocks_test_body(
    monkeypatch: pytest.MonkeyPatch, wrong_database: str
) -> None:
    statements = mock_connections(monkeypatch, wrong_database=wrong_database)
    with pytest.raises(pytest.fail.Exception, match="unexpected database"):
        with seed_tests.isolated_seed_database("postgresql://demo@127.0.0.1/source"):
            pytest.fail("must not reach migrations or seed")

    if wrong_database == "postgres":
        assert statements == [("postgres", "SELECT current_database()")]
    else:
        assert statements[-1] == (
            "postgres",
            'DROP DATABASE "retailops_seed_test_probe" WITH (FORCE)',
        )
