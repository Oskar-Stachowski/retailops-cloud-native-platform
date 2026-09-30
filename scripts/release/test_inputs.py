# ruff: noqa: INP001, PT009, PT027
"""Refuse release receipts with missing materials or substituted source/artifact identities."""

import copy
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from inputs import build_inputs, verify_source_inputs


class BuildInputTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.context = Path(self.temp.name)
        self.base_digest = "sha256:" + "a" * 64
        (self.context / "Dockerfile").write_text("FROM python:3.11@" + self.base_digest + "\n")
        (self.context / "requirements.txt").write_text("fastapi==1.0.0\n")
        self.image = {"Id": "sha256:" + "b" * 64, "Os": "linux", "Architecture": "amd64"}
        self.metadata = {
            "containerimage.digest": self.image["Id"],
            "buildx.build.provenance": {
                "materials": [{"uri": "pkg:docker/python@3.11", "digest": {"sha256": "a" * 64}}],
                "invocation": {"environment": {"platform": "linux/amd64"}},
            },
        }

    def test_verified_receipt_binds_materials_source_and_exported_image(self) -> None:
        recorded = build_inputs(self.context, self.metadata, self.image)
        verify_source_inputs(self.context, recorded)
        self.assertEqual(recorded["declared_bases"], ["python:3.11@" + self.base_digest])
        self.assertEqual(recorded["exported_image_digest"], self.image["Id"])
        self.assertIn("requirements.txt", recorded["source_files_sha256"])

    def test_classic_docker_config_identity_is_supported(self) -> None:
        self.metadata["containerimage.config.digest"] = self.image["Id"]
        self.metadata["containerimage.digest"] = "sha256:" + "c" * 64
        build_inputs(self.context, self.metadata, self.image)

    def test_missing_or_different_base_material_is_refused(self) -> None:
        for materials in ([], [{"uri": "pkg:docker/python@3.11", "digest": {"sha256": "c" * 64}}]):
            altered = copy.deepcopy(self.metadata)
            altered["buildx.build.provenance"]["materials"] = materials
            with self.assertRaises(RuntimeError):
                build_inputs(self.context, altered, self.image)

    def test_wrong_artifact_or_platform_is_refused(self) -> None:
        for changes in ({"Id": "sha256:" + "c" * 64}, {"Architecture": "arm64"}):
            with self.assertRaises(RuntimeError):
                build_inputs(self.context, self.metadata, {**self.image, **changes})

    def test_imported_receipt_rejects_changed_lockfile(self) -> None:
        recorded = build_inputs(self.context, self.metadata, self.image)
        (self.context / "requirements.txt").write_text("fastapi==2.0.0\n")
        with self.assertRaisesRegex(RuntimeError, "source_files_sha256"):
            verify_source_inputs(self.context, recorded)

    def test_old_predecessor_tag_is_recorded_with_its_actual_material_digest(self) -> None:
        (self.context / "Dockerfile").write_text("FROM python:3.11\n")
        recorded = build_inputs(self.context, self.metadata, self.image)
        self.assertEqual(recorded["declared_bases"], ["python:3.11"])
        self.assertEqual(recorded["materials"][0]["digest"]["sha256"], "a" * 64)
