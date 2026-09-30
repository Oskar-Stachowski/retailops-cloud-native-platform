# ruff: noqa: INP001
"""Reject mutable external action/image references in the maintained build surfaces."""

import argparse
import ast
import json
import re
import sys
from collections.abc import Iterator
from pathlib import Path

SHA = r"[a-f0-9]{40}"
DIGEST = r"sha256:[a-f0-9]{64}"
IMAGE = r"[a-z0-9][a-z0-9./_-]*(?::[a-zA-Z0-9_.-]+)?@" + DIGEST
# A literal transport reference, not a URL, filesystem mount or port mapping.
IMAGE_TOKEN = re.compile(
    r"(?<![a-z0-9/_.-])([a-z][a-z0-9./_-]*(?::v?\d[a-zA-Z0-9_.-]*)?"
    r"(?:@sha256:[a-f0-9]+)?)(?![a-z0-9/_.-])"
)
LOCAL_IMAGES = {
    "docker-compose.yml": {
        "${API_IMAGE:-retailops-api:0.1.0}",
        "${FRONTEND_IMAGE:-retailops-frontend:0.1.0}",
    },
    "scripts/db/recovery-compose.yml": {"${COMPOSE_PROJECT_NAME}-api"},
    "scripts/release/compose.yml": {
        "${RELEASE_API_IMAGE:?Exact API image ID is required}",
        "${RELEASE_FRONTEND_IMAGE:?Exact frontend image ID is required}",
    },
}


def scalar(value: str) -> str:
    return value.split(" #", 1)[0].strip().strip("\"'")


def dockerfile_references(document: str) -> Iterator[tuple[str, int]]:
    stages = set()
    for number, line in enumerate(document.splitlines(), 1):
        if not re.match(r"\s*FROM\s", line, re.IGNORECASE):
            continue
        fields = [f for f in line.split(" #", 1)[0].split()[1:] if not f.startswith("--platform=")]
        reference = fields[0]
        if reference.lower() not in stages | {"scratch"}:
            yield reference, number
        if len(fields) == 3 and fields[1].lower() == "as":
            stages.add(fields[2].lower())


def python_references(document: str) -> Iterator[tuple[str, int]]:
    found = set()
    for node in ast.walk(ast.parse(document)):
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id in {"TRIVY", "NODE", "POSTGRES", "REDPANDA"}
            for target in node.targets
        ):
            value = (
                node.value.value if isinstance(node.value, ast.Constant) else "<dynamic tool image>"
            )
            found.add((str(value), node.value.lineno))
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and re.fullmatch(
                r"[a-z][a-z0-9./_-]*:[a-zA-Z0-9_.-]+(?:@sha256:[a-f0-9]+)?", node.value
            )
        ):
            found.add((node.value, node.lineno))
    yield from sorted(found, key=lambda item: item[1])


def shell_references(document: str) -> Iterator[tuple[str, int]]:
    logical = document.replace("\\\n", " ")
    for match in re.finditer(r"docker\s+(?:run|pull)\s+([^\n]+)", logical):
        candidates = [m[1] for m in IMAGE_TOKEN.finditer(match[1]) if ":" in m[1] or "@" in m[1]]
        yield (
            candidates[0] if candidates else "<dynamic tool image>",
            logical[: match.start()].count("\n") + 1,
        )


def check_document(path: str, document: str) -> tuple[list[dict], list[str]]:
    references = []
    errors = []

    def record(kind: str, reference: str, line: int, *, build_target: bool = False) -> None:
        entry = {"path": path, "line": line, "kind": kind, "reference": reference}
        references.append(entry)
        if kind == "action":
            valid = reference.startswith("./.github/") or bool(
                re.fullmatch(r"[\w.-]+/[\w./-]+@" + SHA, reference)
            )
            if reference.startswith("docker://"):
                valid = bool(re.fullmatch(IMAGE, reference.removeprefix("docker://")))
        else:
            valid = bool(re.fullmatch(IMAGE, reference)) or reference in LOCAL_IMAGES.get(
                path, set()
            )
            if build_target and path == ".github/workflows/security-ci.yml":
                valid |= reference in {"retailops-api:security", "retailops-frontend:security"}
            if path.startswith("k8s/"):
                valid |= bool(re.fullmatch(r"retailops-(api|frontend):\d+\.\d+\.\d+", reference))
        if not valid:
            errors.append(f"{path}:{line}: mutable or unsupported {kind}: {reference}")

    if path.endswith((".yml", ".yaml")):
        for number, line in enumerate(document.splitlines(), 1):
            match = re.match(r"\s*(?:-\s*)?(uses|image|[A-Z_]+_IMAGE):\s*(.+)", line)
            if match:
                record(
                    "action" if match[1] == "uses" else "image",
                    scalar(match[2]),
                    number,
                    build_target=match[1].endswith("_IMAGE"),
                )

    if path.endswith("Dockerfile"):
        for reference, number in dockerfile_references(document):
            record("image", reference, number)

    if path.startswith(".github/"):
        for reference, number in shell_references(document):
            record("image", reference, number)

    if path.endswith(".py"):
        for reference, number in python_references(document):
            record("image", reference, number)
    return references, errors


def inventory(root: Path) -> dict:
    paths = set()
    for directory in (".github", "k8s", "scripts/kubernetes"):
        paths.update((root / directory).rglob("*.yml"))
        paths.update((root / directory).rglob("*.yaml"))
    paths.update(root.glob("docker-compose*.yml"))
    paths.update((root / "scripts").rglob("*compose*.yml"))
    paths.update(
        root / name
        for name in (
            "services/api/Dockerfile",
            "frontend/Dockerfile",
            "scripts/release/registry.py",
            "scripts/kubernetes/drill.py",
            "services/api/tests/test_realtime_durability.py",
        )
    )
    references = []
    errors = []
    for path in sorted(paths):
        found, rejected = check_document(path.relative_to(root).as_posix(), path.read_text())
        references.extend(found)
        errors.extend(rejected)
    return {"status": "failed" if errors else "passed", "references": references, "errors": errors}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = inventory(args.root)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n")
    for error in result["errors"]:
        sys.stdout.write(error + "\n")
    sys.stdout.write(
        f"Immutable inputs: {result['status']} ({len(result['references'])} references)\n"
    )
    return int(bool(result["errors"]))


if __name__ == "__main__":
    raise SystemExit(main())
