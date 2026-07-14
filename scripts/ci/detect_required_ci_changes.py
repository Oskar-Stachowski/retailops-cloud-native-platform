# ruff: noqa: INP001
"""Classify changed repository paths for the Required CI workflow."""

from __future__ import annotations

import argparse
import fnmatch
import os
import sys
from dataclasses import dataclass, fields
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable


DOC_PATTERNS = (
    "docs/**",
    "**/README.md",
    "README.md",
    "*.md",
    "LICENSE",
    "LICENSE.*",
)

SHARED_PATTERNS = (
    "Makefile",
    ".github/actions/**",
    ".github/workflows/**",
    "scripts/ci/**",
)

API_PATTERNS = (
    "services/api/**",
    "pyproject.toml",
    "pytest.ini",
)

FRONTEND_PATTERNS = ("frontend/**",)

DATA_PATTERNS = (
    "data/**",
    "events/**",
    "scripts/data/**",
    "ml/**",
)

DOCKER_PATTERNS = (
    "docker-compose.yml",
    "docker-compose.yaml",
    "docker-compose.*.yml",
    "docker-compose.*.yaml",
    "compose.yml",
    "compose.yaml",
    "compose.*.yml",
    "compose.*.yaml",
    "Dockerfile",
    "**/Dockerfile",
    ".dockerignore",
    "**/.dockerignore",
    ".env.example",
    "scripts/db/**",
)

TERRAFORM_PATTERNS = (
    "infra/**",
    "infracost.yml",
    "infracost-usage.yml",
    "security/iac/**",
)

KUBERNETES_PATTERNS = (
    "k8s/**",
    "security/k8s/**",
)
POLICY_PATTERNS = ("policy/**",)

SECURITY_PATTERNS = (
    "security/**",
    ".gitleaks.toml",
    ".github/dependabot.yml",
    "services/api/requirements*.txt",
    "frontend/package.json",
    "frontend/package-lock.json",
)

GATE_FIELDS = (
    "api",
    "frontend",
    "data",
    "docker",
    "terraform",
    "kubernetes",
    "security",
)


def matches(path: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


@dataclass
class Decision:
    api: bool = False
    frontend: bool = False
    data: bool = False
    docker: bool = False
    terraform: bool = False
    kubernetes: bool = False
    security: bool = False
    policy: bool = False
    shared: bool = False
    unknown: bool = False
    docs_only: bool = False

    def enable_all_gates(self) -> None:
        for name in GATE_FIELDS:
            setattr(self, name, True)

    def as_outputs(self) -> dict[str, str]:
        return {field.name: str(getattr(self, field.name)).lower() for field in fields(self)}


def classify_paths(  # noqa: PLR0912
    paths: Iterable[str], *, force_all: bool = False
) -> Decision:
    normalized = [path.strip().removeprefix("./") for path in paths if path.strip()]
    decision = Decision(docs_only=bool(normalized))

    if force_all or not normalized:
        decision.shared = True
        decision.docs_only = False
        decision.enable_all_gates()
        return decision

    for path in normalized:
        if matches(path, DOC_PATTERNS):
            continue

        decision.docs_only = False

        if matches(path, SHARED_PATTERNS):
            decision.shared = True
            continue

        recognized = False

        if matches(path, API_PATTERNS):
            decision.api = True
            recognized = True
        if matches(path, FRONTEND_PATTERNS):
            decision.frontend = True
            recognized = True
        if matches(path, DATA_PATTERNS):
            decision.data = True
            recognized = True
        if matches(path, DOCKER_PATTERNS):
            decision.docker = True
            recognized = True
        if matches(path, TERRAFORM_PATTERNS):
            decision.terraform = True
            recognized = True
        if matches(path, KUBERNETES_PATTERNS):
            decision.kubernetes = True
            recognized = True
        if matches(path, POLICY_PATTERNS):
            decision.policy = True
            decision.kubernetes = True
            recognized = True
        if matches(path, SECURITY_PATTERNS):
            decision.security = True
            recognized = True

        if not recognized:
            decision.unknown = True

    if decision.shared or decision.unknown:
        decision.enable_all_gates()
        return decision

    if decision.data:
        decision.api = True
    if decision.api or decision.frontend or decision.data:
        decision.docker = True
        decision.security = True
    if decision.docker or decision.kubernetes or decision.policy:
        decision.security = True

    return decision


def read_paths(*, stdin_zero_delimited: bool) -> list[str]:
    data = sys.stdin.buffer.read()
    separator = b"\0" if stdin_zero_delimited else b"\n"
    return [item.decode("utf-8") for item in data.split(separator) if item]


def append_lines(path: str, lines: Iterable[str]) -> None:
    with Path(path).open("a", encoding="utf-8") as output:
        for line in lines:
            output.write(f"{line}\n")


def write_summary(path: str, decision: Decision, changed_paths: list[str]) -> None:
    outputs = decision.as_outputs()
    lines = [
        "## Required CI path detection",
        "",
        f"Changed files: {len(changed_paths)}",
        "",
        "| Area | Required |",
        "|---|---|",
    ]
    labels = {
        "api": "API",
        "frontend": "Frontend",
        "data": "Data",
        "docker": "Docker/Compose",
        "terraform": "Terraform/IaC",
        "kubernetes": "Kubernetes/policy",
        "security": "Security",
        "docs_only": "Docs only",
        "shared": "Shared path",
        "unknown": "Unknown path",
    }
    lines.extend(f"| {label} | {outputs[name]} |" for name, label in labels.items())
    append_lines(path, lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stdin0", action="store_true")
    parser.add_argument("--all", action="store_true", dest="force_all")
    parser.add_argument("--github-output", default=os.getenv("GITHUB_OUTPUT"))
    parser.add_argument("--summary", default=os.getenv("GITHUB_STEP_SUMMARY"))
    args = parser.parse_args()

    changed_paths = read_paths(stdin_zero_delimited=args.stdin0)
    decision = classify_paths(changed_paths, force_all=args.force_all)
    output_lines = [f"{name}={value}" for name, value in decision.as_outputs().items()]
    output_lines.append(f"changed_files={len(changed_paths)}")

    if args.github_output:
        append_lines(args.github_output, output_lines)
    else:
        sys.stdout.write("\n".join(output_lines) + "\n")

    if args.summary:
        write_summary(args.summary, decision, changed_paths)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
