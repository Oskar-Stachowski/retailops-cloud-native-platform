# ruff: noqa: INP001, PT009
"""Prevent a tag, short SHA or dynamic external image from passing the CI gate."""

import unittest

from check_immutable_inputs import check_document


class ImmutableInputTests(unittest.TestCase):
    def test_external_actions_require_full_commit(self) -> None:
        for value in ("actions/checkout@v6", "actions/checkout@1234567", "actions/checkout@main"):
            with self.subTest(value=value):
                self.assertTrue(
                    check_document(".github/workflows/test.yml", f"- uses: '{value}'")[1]
                )
        self.assertFalse(
            check_document(
                ".github/workflows/test.yml", "uses: actions/checkout@" + "a" * 40 + " # v6"
            )[1]
        )

    def test_local_actions_and_workflows_follow_the_checked_out_commit(self) -> None:
        for value in ("./.github/actions/setup-python-ci", "./.github/workflows/api-ci.yml"):
            self.assertFalse(check_document(".github/workflows/test.yml", "uses: " + value)[1])

    def test_docker_action_requires_digest(self) -> None:
        self.assertTrue(
            check_document(".github/actions/example/action.yml", "uses: docker://alpine:3")[1]
        )
        self.assertFalse(
            check_document(
                ".github/actions/example/action.yml", "uses: docker://alpine:3@sha256:" + "b" * 64
            )[1]
        )

    def test_image_tag_and_truncated_digest_are_rejected(self) -> None:
        for ref in ("postgres:16", "postgres:16@sha256:" + "c" * 63, "${UNVERIFIED_IMAGE}"):
            self.assertTrue(check_document(".github/workflows/test.yml", "image: " + ref)[1])
        self.assertFalse(
            check_document(
                ".github/workflows/test.yml", 'image: "postgres:16@sha256:' + "c" * 64 + '"'
            )[1]
        )

    def test_base_stage_alias_and_scratch_do_not_need_a_registry_digest(self) -> None:
        document = (
            "FROM node:22@sha256:" + "d" * 64 + " AS build\nFROM build AS tests\nFROM scratch\n"
        )
        self.assertFalse(check_document("frontend/Dockerfile", document)[1])
        self.assertTrue(check_document("frontend/Dockerfile", "FROM ${BASE}\n")[1])

    def test_local_image_exception_cannot_be_used_for_a_ci_service(self) -> None:
        ref = "${API_IMAGE:-retailops-api:0.1.0}"
        self.assertFalse(check_document("docker-compose.yml", "image: " + ref)[1])
        self.assertTrue(check_document(".github/workflows/test.yml", "image: " + ref)[1])

    def test_security_build_tag_exception_is_limited_to_build_targets(self) -> None:
        path = ".github/workflows/security-ci.yml"
        self.assertFalse(check_document(path, "API_IMAGE: retailops-api:security")[1])
        self.assertTrue(check_document(path, "image: retailops-api:security")[1])

    def test_shell_tool_images_are_checked_across_continuations(self) -> None:
        command = 'docker run --rm \\\n  -v "${PWD}:/repo" \\\n  rhysd/actionlint:1.7.7 -color\n'
        self.assertTrue(check_document(".github/workflows/test.yml", command)[1])
        self.assertFalse(
            check_document(
                ".github/workflows/test.yml", command.replace("1.7.7", "1.7.7@sha256:" + "e" * 64)
            )[1]
        )
        self.assertTrue(
            check_document(".github/workflows/test.yml", "docker run --rm ${TOOL_IMAGE}\n")[1]
        )

    def test_generated_wrapper_uses_the_same_digest_rule(self) -> None:
        command = '"exec docker run --rm -i ghcr.io/yannh/kubeconform:v0.7.0 \\"$@\\""'
        self.assertTrue(check_document(".github/workflows/test.yml", command)[1])
        self.assertFalse(
            check_document(
                ".github/workflows/test.yml", command.replace("v0.7.0", "v0.7.0@sha256:" + "f" * 64)
            )[1]
        )

    def test_python_tool_constant_cannot_fall_back_to_a_tag(self) -> None:
        self.assertTrue(
            check_document("scripts/release/registry.py", 'TRIVY = "aquasec/trivy:0.74.0"')[1]
        )
        self.assertFalse(
            check_document(
                "scripts/release/registry.py",
                'TRIVY = "aquasec/trivy:0.74.0@sha256:' + "a" * 64 + '"',
            )[1]
        )

    def test_latest_tagless_and_dynamic_python_tools_are_refused(self) -> None:
        for value in ('"aquasec/trivy:latest"', '"aquasec/trivy"', 'os.getenv("SCANNER_IMAGE")'):
            self.assertTrue(check_document("scripts/release/registry.py", "TRIVY = " + value)[1])


if __name__ == "__main__":
    unittest.main()
