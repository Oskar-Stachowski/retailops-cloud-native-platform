# ruff: noqa: INP001, PT009, PT027
# Standard-library unittest keeps the host drill free of Python package installs.
"""Refusal cases that prevent unsafe rollback before runtime mutation."""

import copy
import hashlib
import json
import shutil
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from release import additive_expansion, compatible, migration_contract, verify_image


class ReleaseGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.release = {
            "source_commit": "a" * 40,
            "version": "0.2.0+git.aaaa",
            "migration": {"head": "abc", "history_sha256": "b" * 64},
        }

    def test_same_contract_allows_application_only_rollback(self) -> None:
        compatible(self.release, copy.deepcopy(self.release), "abc")

    def test_same_head_with_modified_migration_is_rejected(self) -> None:
        target = copy.deepcopy(self.release)
        target["migration"]["history_sha256"] = "c" * 64
        with self.assertRaisesRegex(RuntimeError, "histories differ"):
            compatible(self.release, target, "abc")

    def test_unknown_database_revision_is_rejected(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "outside the verified contract"):
            compatible(self.release, self.release, "unknown")

    def test_wrong_image_or_revision_is_rejected(self) -> None:
        image_id = "sha256:" + "d" * 64
        image = {
            "Id": image_id,
            "Config": {
                "Labels": {
                    "org.opencontainers.image.revision": self.release["source_commit"],
                    "org.opencontainers.image.version": self.release["version"],
                    "io.retailops.component": "api",
                }
            },
        }
        verify_image(image, self.release, "api", image_id)
        with self.assertRaisesRegex(RuntimeError, "does not match"):
            verify_image(image, self.release, "api", "sha256:" + "e" * 64)
        image["Config"]["Labels"]["org.opencontainers.image.revision"] = "f" * 40
        with self.assertRaisesRegex(RuntimeError, "revision differs"):
            verify_image(image, self.release, "api", image_id)

    def test_migration_fingerprint_catches_same_revision_rewrite(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "first.py"
            path.write_text("revision = 'a'\ndown_revision = None\n")
            before = migration_contract(root)
            path.write_text("revision = 'a'\ndown_revision = None\n# altered migration\n")
            after = migration_contract(root)
            self.assertEqual(before["head"], after["head"])
            self.assertNotEqual(before["history_sha256"], after["history_sha256"])
            (root / "branch.py").write_text("revision = 'b'\ndown_revision = None\n")
            with self.assertRaisesRegex(RuntimeError, "incomplete or branched"):
                migration_contract(root)


class AdditiveRollbackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.plan = json.loads(Path(__file__).with_name("additive-rollback.json").read_text())
        self.current = {"migration": self.plan["expanded"]}
        self.previous = {"migration": self.plan["parent"]}

    def test_exact_expansion_allows_only_parent_and_expanded_database_heads(self) -> None:
        for head in (self.plan["parent"]["head"], self.plan["expanded"]["head"]):
            compatible(self.current, self.previous, head)
        with self.assertRaisesRegex(RuntimeError, "outside the verified contract"):
            compatible(self.current, self.previous, "unverified")

    def test_rewritten_previous_history_is_still_blocked(self) -> None:
        previous = copy.deepcopy(self.previous)
        previous["migration"]["history_sha256"] = "0" * 64
        with self.assertRaisesRegex(RuntimeError, "histories differ"):
            compatible(self.current, previous, self.plan["expanded"]["head"])

    def test_rewritten_expansion_is_still_blocked(self) -> None:
        current = copy.deepcopy(self.current)
        current["migration"]["history_sha256"] = "0" * 64
        with self.assertRaisesRegex(RuntimeError, "histories differ"):
            compatible(current, self.previous, self.plan["parent"]["head"])

    def test_other_new_revision_is_not_assumed_compatible(self) -> None:
        current = copy.deepcopy(self.current)
        current["migration"]["head"] = "another_new_head"
        self.assertIsNone(additive_expansion(current, self.previous))
        with self.assertRaisesRegex(RuntimeError, "histories differ"):
            compatible(current, self.previous, self.plan["parent"]["head"])

    def test_plan_pins_actual_migration_and_unchanged_parent_files(self) -> None:
        versions = Path(__file__).resolve().parents[2] / "services/api/alembic/versions"
        self.assertEqual(migration_contract(versions), self.plan["expanded"])
        additions = self.plan["migration_files"]
        self.assertEqual(len(additions), 5)
        for name, fingerprint in additions.items():
            self.assertEqual(
                hashlib.sha256((versions / name).read_bytes()).hexdigest(), fingerprint
            )
        with TemporaryDirectory() as temporary:
            parent = Path(temporary)
            for path in versions.glob("*.py"):
                if path.name not in additions:
                    shutil.copyfile(path, parent / path.name)
            self.assertEqual(migration_contract(parent), self.plan["parent"])


if __name__ == "__main__":
    unittest.main()
