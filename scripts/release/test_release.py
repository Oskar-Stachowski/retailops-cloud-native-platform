# ruff: noqa: INP001, PT009, PT027
# Standard-library unittest keeps the host drill free of Python package installs.
"""Refusal cases that prevent unsafe rollback before runtime mutation."""

import copy
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from release import compatible, migration_contract, verify_image


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


if __name__ == "__main__":
    unittest.main()
