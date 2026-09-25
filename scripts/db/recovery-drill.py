# ruff: noqa: INP001, S603, S607
# Executables and argv are controlled here; no commands come from data or shell evaluation.
"""Run a real logical backup/restore drill in a uniquely named Compose project.

Only the standard library is needed on the host. All PostgreSQL and application
operations run in disposable containers, without publishing host ports.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "scripts/db/recovery-compose.yml"


def require(condition: object, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def progress(message: str) -> None:
    sys.stdout.write(message + "\n")
    sys.stdout.flush()


def main() -> int:  # noqa: PLR0915 -- sequential drill and its cleanup share one audit log
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-dir", default="ci-cd/reports/db/recovery")
    args = parser.parse_args()
    project = "retailops-recovery-" + uuid4().hex[:12]
    report_dir = Path(args.report_dir).resolve() / project
    report_dir.mkdir(parents=True, exist_ok=False)
    env = {key: value for key, value in os.environ.items() if not key.startswith("COMPOSE_")}
    env.update(
        {
            "COMPOSE_PROJECT_NAME": project,
            "COMPOSE_FILE": str(CONFIG),
            "COMPOSE": "docker compose --env-file /dev/null",
            "DB_SERVICE": "db",
            "POSTGRES_USER": "recovery",
            "POSTGRES_DB": "source",
            "RETAILOPS_DB_DUMP_MODE": "compose",
        }
    )
    compose = ["docker", "compose", "--env-file", "/dev/null", "-f", str(CONFIG), "-p", project]
    report = {
        "status": "failed",
        "project": project,
        "started_at": datetime.now(UTC).isoformat(),
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "working_tree_dirty": bool(
            subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT)
        ),
        "timings_seconds": {},
        "negative_checks": {},
    }
    started = time.monotonic()

    with (report_dir / "commands.log").open("w") as log:

        def run(
            command: list[str],
            *,
            extra_env: dict | None = None,
            input_text: str | None = None,
            expect_failure: bool = False,
            stream: bool = False,
            log_stdout: bool = True,
        ) -> str:
            log.write("$ " + " ".join(map(str, command)) + "\n")
            log.flush()
            result = subprocess.run(
                command,
                cwd=ROOT,
                env={**env, **(extra_env or {})},
                input=input_text,
                text=True,
                stdout=log if stream else subprocess.PIPE,
                stderr=log if stream else subprocess.PIPE,
                timeout=600,
                check=False,
            )
            if not stream:
                log.write((result.stdout if log_stdout else "") + result.stderr)
            log.flush()
            if expect_failure:
                require(result.returncode != 0, "Invalid backup was accepted")
            else:
                require(
                    result.returncode == 0,
                    f"Command failed ({result.returncode}); see {report_dir / 'commands.log'}",
                )
            return result.stdout or ""

        def phase(label: str, command: list[str], **kwargs: str | dict | bool | None) -> str:
            progress(label)
            tick = time.monotonic()
            result = run(command, stream=True, **kwargs)
            report["timings_seconds"][label] = round(time.monotonic() - tick, 3)
            return result

        def app(database: str, *command: str, **kwargs: str | dict | bool | None) -> str:
            return run(
                [
                    *compose,
                    "run",
                    "--rm",
                    "--no-deps",
                    "-T",
                    "-e",
                    f"DATABASE_URL=postgresql://recovery:recovery_disposable_only@db:5432/{database}",
                    "api",
                    *command,
                ],
                **kwargs,
            )

        def check(database: str, mode: str, expected: dict | None = None) -> dict:
            return json.loads(
                app(
                    database,
                    "python",
                    "/recovery/checks.py",
                    mode,
                    input_text=None if expected is None else json.dumps(expected),
                    log_stdout=False,
                )
            )

        try:
            phase("build", [*compose, "build", "api"])
            phase("database_start", [*compose, "up", "-d", "--wait", "--wait-timeout", "90", "db"])
            report["postgres_version"] = run(
                [*compose, "exec", "-T", "db", "postgres", "--version"]
            ).strip()
            app("source", "alembic", "upgrade", "head")
            app("source", "python", "scripts/seed_demo_data.py")
            progress("Record workflow decisions before backup")
            expected = check("source", "prepare")
            report["before"] = expected["snapshot"]
            (report_dir / "expected.json").write_text(json.dumps(expected, indent=2) + "\n")
            dump = report_dir / "source.dump"
            phase("backup", ["bash", "scripts/db/backup.sh"], extra_env={"BACKUP_FILE": str(dump)})
            # Relocate the pair and remove the original to exercise portable checksum validation.
            moved = report_dir / "relocated"
            moved.mkdir()
            relocated = moved / "source.dump"
            dump.rename(relocated)
            Path(str(dump) + ".sha256").rename(Path(str(relocated) + ".sha256"))
            report["backup_bytes"] = relocated.stat().st_size
            report["backup_sha256"] = hashlib.sha256(relocated.read_bytes()).hexdigest()
            run([*compose, "exec", "-T", "db", "createdb", "-U", "recovery", "restored"])
            empty = check("restored", "snapshot")
            require(not empty["tables"], "Restore target is not empty")

            progress("Reject missing, corrupt and invalid backups before recovery")
            for case in ("missing_dump", "missing_checksum", "corrupted_dump", "invalid_archive"):
                candidate = report_dir / (case + ".dump")
                if case != "missing_dump":
                    shutil.copyfile(relocated, candidate)
                if case == "corrupted_dump":
                    with candidate.open("ab") as output:
                        output.write(b"corruption")
                    shutil.copyfile(str(relocated) + ".sha256", str(candidate) + ".sha256")
                elif case == "invalid_archive":
                    candidate.write_bytes(b"not a PostgreSQL archive\n")
                    Path(str(candidate) + ".sha256").write_text(
                        hashlib.sha256(candidate.read_bytes()).hexdigest()
                        + "  invalid_archive.dump\n"
                    )
                run(
                    ["bash", "scripts/db/restore.sh", str(candidate)],
                    extra_env={"POSTGRES_DB": "restored"},
                    expect_failure=True,
                )
                require(
                    check("restored", "snapshot") == empty, f"{case} changed the restore target"
                )
                report["negative_checks"][case] = "rejected_target_unchanged"

            recovery_started = time.monotonic()
            phase(
                "restore",
                ["bash", "scripts/db/restore.sh", str(relocated)],
                extra_env={"POSTGRES_DB": "restored"},
            )
            restored = check("restored", "snapshot")
            report["restored"] = restored
            require(restored == expected["snapshot"], "Full row/schema/sequence comparison failed")
            report["application_checks"] = check("restored", "verify", expected)
            report["timings_seconds"]["restore_and_verification"] = round(
                time.monotonic() - recovery_started, 3
            )
            require(
                check("source", "snapshot") == expected["snapshot"], "Recovery changed the source"
            )
            report["source_unchanged"] = True
            report["status"] = "passed"
        except Exception as error:
            report["error"] = str(error)
            raise
        finally:
            # Cleanup is scoped to the generated name and dedicated config, never the default stack.
            try:
                run([*compose, "logs", "--no-color"])
                run([*compose, "down", "--volumes", "--remove-orphans", "--timeout", "10"])
                run(["docker", "image", "rm", f"{project}-api"])
                report["cleanup"] = "passed"
            except Exception as error:  # noqa: BLE001 -- persist cleanup failure and return nonzero
                report["cleanup"] = "failed"
                report["status"] = "failed"
                report["cleanup_error"] = str(error)
            report["timings_seconds"]["total"] = round(time.monotonic() - started, 3)
            report["finished_at"] = datetime.now(UTC).isoformat()
            (report_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n")
            progress(f"Recovery {report['status']}: {report_dir / 'report.json'}")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
