# ruff: noqa: INP001, PT009, PT027, SIM117
"""Guard the acceptance controller against shared networks and leaked private files."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "intelligence_runtime_drill",
    Path(__file__).resolve().parents[1] / "intelligence-runtime/drill.py",
)
DRILL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DRILL)


def configuration() -> dict:
    return {
        "name": "owned-project",
        "services": {
            "source": {"networks": {"source-db": {}, "bus": {}}},
            "consumer": {"networks": {"source-db": {}, "bus": {}}},
            "delivery": {"networks": {"ai-db": {}, "bus": {}}},
        },
        "networks": {name: {"internal": True} for name in ("source-db", "ai-db", "bus")},
        "volumes": {"owned-data": {}},
    }


class RuntimeBoundaryTests(unittest.TestCase):
    def test_only_own_private_networks_are_accepted(self) -> None:
        DRILL.validate_configuration(configuration(), "owned-project")
        for change in (
            "host_port",
            "external_network",
            "public_network",
            "foreign_database",
            "external_volume",
            "global_container",
            "privileged",
            "host_network",
        ):
            with self.subTest(change=change):
                value = configuration()
                if change == "host_port":
                    value["services"]["source"]["ports"] = [{"published": "8000"}]
                elif change == "external_network":
                    value["networks"]["bus"]["external"] = True
                elif change == "public_network":
                    value["networks"]["bus"]["internal"] = False
                elif change == "foreign_database":
                    value["services"]["delivery"]["networks"]["source-db"] = {}
                elif change == "external_volume":
                    value["volumes"]["owned-data"]["external"] = True
                elif change == "global_container":
                    value["services"]["source"]["container_name"] = "existing-source"
                elif change == "privileged":
                    value["services"]["source"]["privileged"] = True
                else:
                    value["services"]["source"]["network_mode"] = "host"
                with self.assertRaises(ValueError):
                    DRILL.validate_configuration(value, "owned-project")

    def test_project_identity_is_exact(self) -> None:
        with self.assertRaisesRegex(ValueError, "runtime_project_mismatch"):
            DRILL.validate_configuration(configuration(), "foreign-project")

    def test_private_file_is_exclusive_and_owner_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "secret"
            DRILL.private_file(path, "private-value")
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError):
                DRILL.private_file(path, "overwrite")
            target = Path(directory) / "target"
            target.write_text("original")
            link = Path(directory) / "link"
            link.symlink_to(target)
            with self.assertRaises(FileExistsError):
                DRILL.private_file(link, "overwrite")
            self.assertEqual(target.read_text(), "original")

    def test_owner_commit_and_dirty_tree_are_rejected(self) -> None:
        with patch.object(DRILL, "command", return_value="wrong-head"):
            with self.assertRaisesRegex(ValueError, "owner_commit_mismatch"):
                DRILL.verify_owner(Path("/unused"))
        pin = json.loads((DRILL.HERE / "owner.json").read_text())
        with patch.object(DRILL, "command", side_effect=[pin["commit"], " M uv.lock"]):
            with self.assertRaisesRegex(ValueError, "owner_tracked_changes"):
                DRILL.verify_owner(Path("/unused"))

    def test_failed_commands_expose_only_fixed_probe_codes(self) -> None:
        with patch.object(DRILL.subprocess, "run") as run:
            run.return_value.returncode = 1
            run.return_value.stdout = '{"code":"consumer_write_denied"}'
            with self.assertRaisesRegex(DRILL.RuntimeCommandError, "consumer_write_denied"):
                DRILL.command(["unused"])
            run.return_value.stdout = '{"code":"password=should-never-be-exposed"}'
            with self.assertRaisesRegex(DRILL.RuntimeCommandError, "runtime_command_failed"):
                DRILL.command(["unused"])


if __name__ == "__main__":
    unittest.main()
