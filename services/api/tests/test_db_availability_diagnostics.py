"""Keep database connection secrets out of pytest output and JUnit reports."""

import os
import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree

import psycopg
import pytest

import conftest

API_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = API_ROOT.parents[1]
TESTS_ROOT = Path(__file__).resolve().parent


def test_database_exception_text_is_not_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    password = "ops05-exception-password"

    def reject_connection(*_args: object, **_kwargs: object) -> None:
        raise psycopg.OperationalError(f"connection failed with password={password}")

    monkeypatch.setattr(conftest.psycopg, "connect", reject_connection)
    reason = conftest._db_unavailable_reason(
        f"postgresql://ops05:{password}@127.0.0.1:1/ops05_probe"
    )
    if reason is not None and password in reason:
        pytest.fail("Database exception text appeared in diagnostics", pytrace=False)
    assert reason == "database connection or readiness query failed"


@pytest.mark.parametrize("require_db_tests", [False, True])
def test_unavailable_database_never_reports_credentials(
    tmp_path: Path, require_db_tests: bool
) -> None:
    probe = tmp_path / "test_db_probe.py"
    probe.write_text(
        "\n".join(
            (
                "import pytest",
                "",
                "@pytest.mark.integration_db",
                "def test_probe():",
                "    assert True",
                "",
            )
        ),
        encoding="utf-8",
    )
    report = tmp_path / "pytest-report.xml"
    password = "ops05-password-must-not-appear"
    database_url = f"postgresql://ops05:{password}@127.0.0.1:1/ops05_probe"
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    env["REQUIRE_DB_TESTS"] = "1" if require_db_tests else "0"
    env["PYTHONPATH"] = os.pathsep.join(
        str(path) for path in (TESTS_ROOT, API_ROOT, REPO_ROOT, env.get("PYTHONPATH")) if path
    )
    env.pop("PYTEST_ADDOPTS", None)

    result = subprocess.run(  # noqa: S603 - fixed interpreter and pytest arguments
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "conftest",
            "-c",
            str(REPO_ROOT / "pytest.ini"),
            str(probe),
            "-q",
            "-rs",
            f"--junitxml={report}",
        ],
        cwd=REPO_ROOT,
        env=env,
        check=False,
        text=True,
        capture_output=True,
    )

    output = result.stdout + result.stderr
    report_text = report.read_text(encoding="utf-8")
    for artifact in (output, report_text):
        if password in artifact or database_url in artifact:
            pytest.fail("Database credentials appeared in pytest diagnostics", pytrace=False)

    expected_exit_code = 1 if require_db_tests else 0
    assert result.returncode == expected_exit_code
    assert "database connection or readiness query failed" in output
    root = ElementTree.fromstring(report_text)
    assert root.find(".//error" if require_db_tests else ".//skipped") is not None
