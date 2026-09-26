# ruff: noqa: INP001, PT009, PT027
"""Prevent promotion of stale CI results, mutable references or untested images."""

import copy
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from drill import Drill
from promotion import passed_main_run
from registry import (
    NAMESPACE,
    consumer_image,
    publication_contract,
    ready_report,
    registry_reference,
)


class PromotionTests(unittest.TestCase):
    def test_registry_digest_binds_different_engine_ids_without_accepting_wrong_image(self) -> None:
        reference = NAMESPACE + "-api@sha256:" + "e" * 64
        image = {
            "image_id": "sha256:" + "a" * 64,
            "registry_ref": reference,
            "platform": "linux/amd64",
        }
        release = {"source_commit": "c" * 40, "version": "0.2.1"}
        inspected = {
            "Id": "sha256:" + "b" * 64,
            "RepoDigests": [reference],
            "Os": "linux",
            "Architecture": "amd64",
            "Config": {
                "Labels": {
                    "org.opencontainers.image.revision": release["source_commit"],
                    "org.opencontainers.image.version": release["version"],
                    "io.retailops.component": "api",
                }
            },
        }
        rebound = consumer_image(image, inspected, release, "api")
        self.assertEqual(rebound["build_image_id"], image["image_id"])
        self.assertEqual(rebound["image_id"], inspected["Id"])
        for changed in (
            {"RepoDigests": [NAMESPACE + "-api@sha256:" + "f" * 64]},
            {"Architecture": "arm64"},
        ):
            with self.assertRaises(RuntimeError):
                consumer_image(image, {**inspected, **changed}, release, "api")

    def test_newer_failed_or_running_ci_attempt_blocks_older_success(self) -> None:
        passed = {
            "head_sha": "a" * 40,
            "head_branch": "main",
            "event": "push",
            "id": 1,
            "run_number": 3,
            "run_attempt": 1,
            "status": "completed",
            "conclusion": "success",
            "html_url": "https://github.com/example/run/1",
        }
        self.assertEqual(passed_main_run([passed], "a" * 40)["id"], 1)
        for status, conclusion in (("completed", "failure"), ("in_progress", None)):
            latest = {**passed, "run_attempt": 2, "status": status, "conclusion": conclusion}
            with self.assertRaisesRegex(RuntimeError, "did not pass"):
                passed_main_run([latest, passed], "a" * 40)

    def test_pr_or_different_commit_cannot_authorize_release(self) -> None:
        for branch, event, sha in (
            ("main", "pull_request", "a" * 40),
            ("feature", "push", "a" * 40),
            ("main", "push", "b" * 40),
        ):
            with self.assertRaisesRegex(RuntimeError, "No Required CI"):
                passed_main_run(
                    [{"head_sha": sha, "head_branch": branch, "event": event}], "a" * 40
                )

    def test_only_expected_registry_and_immutable_digest_are_accepted(self) -> None:
        digest = "sha256:" + "b" * 64
        self.assertEqual(
            registry_reference(NAMESPACE + "-api", digest), NAMESPACE + "-api@" + digest
        )
        for repository, value in (
            ("ghcr.io/another/project-api", digest),
            (NAMESPACE + "-api", "latest"),
            (NAMESPACE + "-api", "sha256:" + "b" * 63),
        ):
            with self.assertRaises(RuntimeError):
                registry_reference(repository, value)

    @patch("registry.run")
    def test_incomplete_or_dirty_drill_never_reaches_docker(self, command: MagicMock) -> None:
        report = {
            "status": "passed",
            "cleanup": "passed",
            "working_tree_dirty": False,
            "stages": {"previous": {}, "upgraded": {}, "rolled_back": {}},
        }
        for changes in (
            {"status": "failed"},
            {"cleanup": "failed"},
            {"working_tree_dirty": True},
            {"stages": {"previous": {}}},
        ):
            with self.assertRaises(RuntimeError):
                ready_report({**report, **changes})
        command.assert_not_called()

    def test_changed_image_or_source_cannot_be_promoted(self) -> None:
        release = {
            "source_commit": "a" * 40,
            "version": "0.2.1",
            "migration": {"head": "abc"},
            "validation": "local_drill_passed",
            "images": {
                name: {
                    "image_id": "sha256:" + "b" * 64,
                    "tag": "temporary:" + name,
                    "platform": "linux/amd64",
                }
                for name in ("api", "frontend")
            },
        }
        report = {
            "harness_commit": "c" * 40,
            "releases": {role: copy.deepcopy(release) for role in ("previous", "candidate")},
        }
        publication_contract(copy.deepcopy(report), report)
        for field, value in (("image_id", "sha256:" + "d" * 64), ("platform", "linux/arm64")):
            altered = copy.deepcopy(report)
            altered["releases"]["candidate"]["images"]["api"][field] = value
            with self.assertRaisesRegex(RuntimeError, "differs from tested artifact"):
                publication_contract(altered, report)
        altered = copy.deepcopy(report)
        altered["releases"]["candidate"]["source_commit"] = "d" * 40
        with self.assertRaisesRegex(RuntimeError, "differs from tested source"):
            publication_contract(altered, report)

    def test_imported_migration_change_is_refused_before_runtime(self) -> None:
        source = {"source_commit": "a" * 40, "version": "0.2.1", "migration": {"head": "abc"}}
        with TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({**source, "migration": {"head": "different"}}))
            with (root / "commands.log").open("w") as log:
                drill = Drill(root, log)
                with (
                    patch.object(drill, "source", return_value=source),
                    patch.object(drill, "select") as select,
                ):
                    with self.assertRaisesRegex(RuntimeError, "differs from source: migration"):
                        drill.imported(manifest, root / "source")
                    select.assert_not_called()


if __name__ == "__main__":
    unittest.main()
