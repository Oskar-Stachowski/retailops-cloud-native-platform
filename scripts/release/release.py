# ruff: noqa: INP001
"""Release identities and a deliberately conservative application rollback gate."""

import ast
import hashlib
import re
from pathlib import Path


def require(condition: object, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def migration_contract(directory: Path) -> dict:
    digest = hashlib.sha256()
    revisions = set()
    parents = set()
    graph = {}
    for path in sorted(directory.glob("*.py")):
        digest.update(path.name.encode() + b"\0" + path.read_bytes() + b"\0")
        values = {}
        for node in ast.parse(path.read_text()).body:
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                values[node.target.id] = node.value
            elif (
                isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
            ):
                values[node.targets[0].id] = node.value
        if "revision" in values:
            revision = ast.literal_eval(values["revision"])
            parent = ast.literal_eval(values["down_revision"])
            require(
                isinstance(revision, str) and (parent is None or isinstance(parent, str)),
                "Only a linear migration history is supported",
            )
            require(revision not in revisions, "Duplicate migration revision")
            revisions.add(revision)
            graph[revision] = parent
            if parent:
                parents.add(parent)
    heads = revisions - parents
    require(len(heads) == 1 and parents <= revisions, "Migration history is incomplete or branched")
    head = next(iter(heads))
    visited = set()
    cursor = head
    while cursor is not None:
        require(cursor not in visited, "Cyclic migration history")
        visited.add(cursor)
        cursor = graph[cursor]
    require(visited == revisions, "Disconnected migration history")
    return {"head": head, "history_sha256": digest.hexdigest()}


def compatible(current: dict, target: dict, database_head: str) -> None:
    require(
        current["migration"] == target["migration"],
        "Application-only rollback blocked: migration histories differ; review recovery/forward-fix plan",
    )
    require(
        database_head == target["migration"]["head"],
        "Application-only rollback blocked: database revision is outside the verified contract",
    )


def verify_image(image: dict, release: dict, component: str, expected_id: str) -> None:
    require(re.fullmatch(r"sha256:[a-f0-9]{64}", expected_id), "Invalid immutable image ID")
    require(image["Id"] == expected_id, "Running image does not match the release manifest")
    labels = image["Config"]["Labels"]
    require(
        labels.get("org.opencontainers.image.revision") == release["source_commit"],
        "Image revision differs from the release manifest",
    )
    require(
        labels.get("org.opencontainers.image.version") == release["version"],
        "Image version differs from the release manifest",
    )
    require(labels.get("io.retailops.component") == component, "Image component mismatch")
