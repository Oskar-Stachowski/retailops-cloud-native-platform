# ruff: noqa: INP001, S603
# All executables/argv are controlled here; no shell evaluation or external deployment targets.
"""Build release manifests and exercise an isolated update/failure/rollback."""

import argparse
import copy
import json
import os
import re
import subprocess
import sys
import tarfile
import time
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from release import compatible, migration_contract, require, verify_image

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "scripts/release/compose.yml"
BASELINE = "44f7404010b55eba3d9bacd888d2dc7bb9797180"


class Drill:
    def __init__(self, report_dir: Path, log: object) -> None:
        self.project = report_dir.name
        self.report_dir = report_dir
        self.log = log
        self.tags = []
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("COMPOSE_")}
        self.env.update(
            {
                "COMPOSE_PROJECT_NAME": self.project,
                "COMPOSE_FILE": str(CONFIG),
                "COMPOSE": "docker compose --env-file /dev/null",
                "DB_SERVICE": "db",
                "POSTGRES_USER": "recovery",
                "POSTGRES_DB": "source",
                "RETAILOPS_DB_DUMP_MODE": "compose",
            }
        )
        self.compose = [
            "docker",
            "compose",
            "--env-file",
            "/dev/null",
            "-f",
            str(CONFIG),
            "-p",
            self.project,
        ]
        self.report = {
            "status": "failed",
            "project": self.project,
            "started_at": datetime.now(UTC).isoformat(),
            "stages": {},
            "timings_seconds": {},
            "negative_checks": {},
            "ci_run_url": os.getenv("GITHUB_SERVER_URL", "https://github.com")
            + "/"
            + os.getenv("GITHUB_REPOSITORY", "")
            + "/actions/runs/"
            + os.getenv("GITHUB_RUN_ID", "")
            if os.getenv("GITHUB_RUN_ID")
            else None,
        }

    def run(
        self,
        command: list[str],
        *,
        data: dict | None = None,
        stream: bool = False,
        allow_failure: bool = False,
    ) -> str:
        self.log.write("$ " + " ".join(command) + "\n")
        self.log.flush()
        result = subprocess.run(
            command,
            cwd=ROOT,
            env=self.env,
            input=None if data is None else json.dumps(data),
            text=True,
            stdout=self.log if stream else subprocess.PIPE,
            stderr=self.log if stream else subprocess.PIPE,
            timeout=900,
            check=False,
        )
        if not stream:
            self.log.write(result.stderr)
        self.log.flush()
        require(
            allow_failure or result.returncode == 0,
            f"Command failed ({result.returncode}); see {self.report_dir / 'commands.log'}",
        )
        return result.stdout or ""

    def progress(self, message: str) -> None:
        sys.stdout.write(message + "\n")
        sys.stdout.flush()

    def source(self, ref: str, directory: Path) -> dict:
        sha = self.run(["git", "rev-parse", "--verify", ref + "^{commit}"]).strip()
        require(re.fullmatch(r"[a-f0-9]{40}", sha), "Invalid source SHA")
        archive = directory.with_suffix(".tar")
        self.run(
            [
                "git",
                "archive",
                "--format=tar",
                "--output=" + str(archive),
                sha,
                "services/api",
                "frontend",
                "data/demo",
            ]
        )
        directory.mkdir()
        with tarfile.open(archive) as source:
            source.extractall(directory, filter="data")
        version = self.run(["git", "show", sha + ":VERSION"], allow_failure=True).strip() or "0.1.0"
        require(re.fullmatch(r"\d+\.\d+\.\d+", version), "VERSION must contain MAJOR.MINOR.PATCH")
        return {
            "manifest_version": 1,
            "source_commit": sha,
            "version": version + "+git." + sha[:12],
            "migration": migration_contract(directory / "services/api/alembic/versions"),
            "images": {},
            "validation": "not_yet_verified",
        }

    def imported(self, manifest: Path, directory: Path) -> dict:
        release = json.loads(manifest.read_text())
        source = self.source(release["source_commit"], directory)
        for key in ("source_commit", "version", "migration"):
            require(release[key] == source[key], f"Imported manifest differs from source: {key}")
        self.select(release, directory)
        return release

    def build(self, ref: str, directory: Path) -> dict:
        release = self.source(ref, directory)
        sha = release["source_commit"]
        for component, context in (("api", "services/api"), ("frontend", "frontend")):
            tag = f"{self.project}-{component}:sha-{sha}"
            self.tags.append(tag)
            self.progress(f"Build {component} from {sha[:12]}")
            self.run(
                [
                    "docker",
                    "build",
                    "--label",
                    "org.opencontainers.image.revision=" + sha,
                    "--label",
                    "org.opencontainers.image.version=" + release["version"],
                    "--label",
                    "org.opencontainers.image.source=https://github.com/Oskar-Stachowski/retailops-cloud-native-platform",
                    "--label",
                    "io.retailops.component=" + component,
                    "-t",
                    tag,
                    str(directory / context),
                ],
                stream=True,
            )
            image = json.loads(self.run(["docker", "image", "inspect", tag]))[0]
            verify_image(image, release, component, image["Id"])
            release["images"][component] = {
                "tag": tag,
                "image_id": image["Id"],
                "platform": image["Os"] + "/" + image["Architecture"],
            }
        return release

    def select(self, release: dict, source_dir: Path) -> None:
        for component in ("api", "frontend"):
            image_id = release["images"][component]["image_id"]
            image = json.loads(self.run(["docker", "image", "inspect", image_id]))[0]
            verify_image(image, release, component, image_id)
            reference = release["images"][component].get("registry_ref", image_id)
            if reference != image_id:
                require(
                    re.fullmatch(r"[a-z0-9./:_-]+@sha256:[a-f0-9]{64}", reference),
                    "Registry deployment requires an immutable digest",
                )
                registered = json.loads(self.run(["docker", "image", "inspect", reference]))[0]
                verify_image(registered, release, component, image_id)
            self.env["RELEASE_" + component.upper() + "_IMAGE"] = reference
        self.env["RELEASE_SOURCE_DIR"] = str(source_dir)

    def app(self, *command: str, data: dict | None = None) -> str:
        return self.run(
            [*self.compose, "run", "--rm", "--no-deps", "-T", "checks", *command], data=data
        )

    def db_head(self) -> str:
        return self.run(
            [
                *self.compose,
                "exec",
                "-T",
                "db",
                "psql",
                "-U",
                "recovery",
                "-d",
                "source",
                "-Atc",
                "SELECT version_num FROM alembic_version",
            ]
        ).strip()

    def deploy(self, release: dict, source_dir: Path) -> None:
        self.select(release, source_dir)
        self.run(
            [
                *self.compose,
                "up",
                "-d",
                "--no-build",
                "--pull",
                "never",
                "--force-recreate",
                "--wait",
                "--wait-timeout",
                "90",
                "api",
                "frontend",
            ],
            stream=True,
        )
        for component in ("api", "frontend"):
            container = self.run([*self.compose, "ps", "-q", component]).strip()
            details = json.loads(self.run(["docker", "inspect", container]))[0]
            require(
                details["Image"] == release["images"][component]["image_id"], "Wrong deployed image"
            )

    def validate(self, stage: str, expected: dict, release: dict) -> None:
        self.progress(f"Validate HTTP, browser and data: {stage}")
        checks = json.loads(self.app("python", "/release/checks.py", "validate", data=expected))
        port = self.run([*self.compose, "port", "frontend", "8080"]).strip()
        require(re.fullmatch(r"127\.0\.0\.1:\d+", port), "Frontend must bind only to loopback")
        expected_file = self.report_dir / "expected.json"
        expected_file.write_text(json.dumps(expected) + "\n")
        browser = json.loads(
            self.run(
                [
                    "node",
                    "scripts/release/browser-check.cjs",
                    "http://" + port,
                    str(expected_file),
                    str(self.report_dir / stage),
                ]
            )
        )
        self.report["stages"][stage] = {
            "source_commit": release["source_commit"],
            "images": release["images"],
            "api": checks,
            "browser": browser,
            "snapshot": expected["snapshot"],
        }

    def exercise(self, previous: dict, candidate: dict, old_dir: Path, new_dir: Path) -> None:
        require(
            previous["source_commit"] != candidate["source_commit"],
            "Two distinct commits are required",
        )
        self.run(
            [
                "git",
                "merge-base",
                "--is-ancestor",
                previous["source_commit"],
                candidate["source_commit"],
            ]
        )
        compatible(candidate, previous, previous["migration"]["head"])
        self.select(previous, old_dir)
        self.run([*self.compose, "up", "-d", "--wait", "--wait-timeout", "90", "db"], stream=True)
        self.app("alembic", "upgrade", "head")
        self.app("python", "scripts/seed_demo_data.py")
        expected = json.loads(self.app("python", "/recovery/checks.py", "prepare"))
        self.report["before"] = expected["snapshot"]
        self.deploy(previous, old_dir)
        self.validate("previous", expected, previous)
        self.env["BACKUP_FILE"] = str(self.report_dir / "before-upgrade.dump")
        self.run(["bash", "scripts/db/backup.sh"], stream=True)
        self.report["backup_created"] = True

        # Exercise both conservative migration refusal paths before any rollout.
        for label, target, head in (
            ("changed_migration_history", copy.deepcopy(previous), self.db_head()),
            ("unknown_database_head", previous, "not-a-verified-revision"),
        ):
            if label == "changed_migration_history":
                target["migration"]["history_sha256"] = "0" * 64
            try:
                compatible(candidate, target, head)
            except RuntimeError:
                self.report["negative_checks"][label] = "blocked"
            else:
                require(condition=False, message="Unsafe rollback passed the migration gate")

        compatible(candidate, previous, self.db_head())
        tick = time.monotonic()
        self.select(candidate, new_dir)
        self.app("alembic", "upgrade", "head")
        self.deploy(candidate, new_dir)
        self.validate("upgraded", expected, candidate)
        expected = json.loads(
            self.app("python", "/release/checks.py", "write", "upgrade", data=expected)
        )
        self.report["after_upgrade_write"] = expected["snapshot"]
        self.report["timings_seconds"]["upgrade_and_verification"] = round(
            time.monotonic() - tick, 3
        )

        self.progress("Inject API outage, detect failed health and roll back both images")
        self.run([*self.compose, "stop", "api"], stream=True)
        self.run(
            [
                *self.compose,
                "exec",
                "-T",
                "frontend",
                "wget",
                "-S",
                "-O",
                "/dev/null",
                "http://127.0.0.1:8080/api/ready",
            ],
            allow_failure=True,
        )
        # Probe from the checker too: only a real HTTP 502 is accepted as this injected failure.
        probe = "import urllib.request, urllib.error\ntry:\n urllib.request.urlopen('http://frontend:8080/api/ready',timeout=10)\nexcept urllib.error.HTTPError as e:\n print(e.code)"
        require(
            self.app("python", "-c", probe).strip() == "502", "Injected outage was not detected"
        )
        self.report["negative_checks"]["api_outage"] = "HTTP 502 detected"
        compatible(candidate, previous, self.db_head())
        tick = time.monotonic()
        self.deploy(previous, old_dir)
        self.validate("rolled_back", expected, previous)
        self.report["timings_seconds"]["rollback_and_verification"] = round(
            time.monotonic() - tick, 3
        )
        expected = json.loads(
            self.app("python", "/release/checks.py", "write", "rollback", data=expected)
        )
        self.report["after_rollback_write"] = expected["snapshot"]
        self.report["database_head"] = self.db_head()
        self.report["migration_action"] = "same-head upgrade check; no downgrade, restore or reseed"
        previous["validation"] = candidate["validation"] = "local_drill_passed"
        self.report["status"] = "passed"


def main() -> int:  # noqa: PLR0915 -- one lifecycle owns reporting and cleanup
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--previous-ref", default=BASELINE)
    parser.add_argument("--candidate-ref", default="HEAD")
    parser.add_argument("--report-dir", default="ci-cd/reports/releases")
    parser.add_argument("--build-only", action="store_true")
    parser.add_argument("--keep-images", action="store_true")
    parser.add_argument("--previous-manifest", type=Path)
    parser.add_argument("--candidate-manifest", type=Path)
    args = parser.parse_args()
    require(
        bool(args.previous_manifest) == bool(args.candidate_manifest),
        "Supply both manifests for a build-free drill",
    )
    require(not (args.build_only and args.candidate_manifest), "Cannot build imported images")
    report_dir = Path(args.report_dir).resolve() / ("retailops-release-" + uuid4().hex[:12])
    report_dir.mkdir(parents=True)
    started = time.monotonic()
    with (
        (report_dir / "commands.log").open("w") as log,
        TemporaryDirectory(prefix="retailops-release-") as temp,
    ):
        drill = Drill(report_dir, log)
        drill.report["harness_commit"] = drill.run(["git", "rev-parse", "HEAD"]).strip()
        drill.report["working_tree_dirty"] = bool(drill.run(["git", "status", "--porcelain"]))
        releases = {}
        try:
            if args.candidate_manifest:
                releases["previous"] = drill.imported(
                    args.previous_manifest, Path(temp) / "previous"
                )
                releases["candidate"] = drill.imported(
                    args.candidate_manifest, Path(temp) / "candidate"
                )
            elif not args.build_only:
                releases["previous"] = drill.build(args.previous_ref, Path(temp) / "previous")
            if not args.candidate_manifest:
                releases["candidate"] = drill.build(args.candidate_ref, Path(temp) / "candidate")
            if args.build_only:
                drill.report["status"] = "built_unverified"
            else:
                drill.exercise(
                    releases["previous"],
                    releases["candidate"],
                    Path(temp) / "previous",
                    Path(temp) / "candidate",
                )
        except Exception as error:
            drill.report["error"] = str(error)
            raise
        finally:
            try:
                if "RELEASE_SOURCE_DIR" in drill.env:
                    drill.run([*drill.compose, "logs", "--no-color"], stream=True)
                    drill.run(
                        [
                            *drill.compose,
                            "down",
                            "--volumes",
                            "--remove-orphans",
                            "--timeout",
                            "10",
                        ],
                        stream=True,
                    )
                if not (args.build_only or args.keep_images) or drill.report["status"] == "failed":
                    for tag in drill.tags:
                        drill.run(
                            ["docker", "image", "rm", tag],
                            allow_failure=drill.report["status"] == "failed",
                        )
                drill.report["cleanup"] = "passed"
            except Exception as error:  # noqa: BLE001 -- preserve cleanup failure in final report
                drill.report.update(status="failed", cleanup="failed", cleanup_error=str(error))
            drill.report["releases"] = releases
            drill.report["timings_seconds"]["total"] = round(time.monotonic() - started, 3)
            drill.report["finished_at"] = datetime.now(UTC).isoformat()
            for name, release in releases.items():
                release["ci_run_url"] = drill.report["ci_run_url"]
                (report_dir / (name + "-manifest.json")).write_text(
                    json.dumps(release, indent=2) + "\n"
                )
            (report_dir / "report.json").write_text(json.dumps(drill.report, indent=2) + "\n")
            drill.progress(f"Release drill {drill.report['status']}: {report_dir / 'report.json'}")
    return 0 if drill.report["status"] in {"passed", "built_unverified"} else 1


if __name__ == "__main__":
    sys.exit(main())
