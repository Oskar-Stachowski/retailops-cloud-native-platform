# ruff: noqa: INP001
"""Bind declared source inputs and BuildKit materials to a built release image."""

import hashlib
import re
from pathlib import Path

from release import require

DIGEST = r"sha256:[a-f0-9]{64}"


def harness_inputs(root: Path) -> dict:
    paths = sorted((root / ".github").rglob("*.yml"))
    actions = []
    for path in paths:
        for match in re.finditer(r"\buses:\s*([^\s#]+)", path.read_text()):
            reference = match[1].strip("\"'")
            if reference.startswith("./"):
                continue
            require(
                re.fullmatch(r"[\w.-]+/[\w./-]+@[a-f0-9]{40}", reference),
                "Release harness action must use a full commit SHA",
            )
            actions.append({"path": path.relative_to(root).as_posix(), "reference": reference})
    paths.extend((root / "scripts/release").glob("*.py"))
    paths.extend((root / "scripts/release").glob("*.json"))
    paths.append(root / "scripts/release/compose.yml")
    return {
        "actions": actions,
        "files_sha256": {
            path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(paths)
        },
    }


def source_inputs(context: Path) -> dict:
    stages = set()
    bases = []
    for line in (context / "Dockerfile").read_text().splitlines():
        if not re.match(r"\s*FROM\s", line, re.IGNORECASE):
            continue
        fields = line.split(" #", 1)[0].split()
        fields = [field for field in fields[1:] if not field.startswith("--platform=")]
        reference = fields[0]
        if reference.lower() not in stages | {"scratch"}:
            bases.append(reference)
        if len(fields) == 3 and fields[1].lower() == "as":
            stages.add(fields[2].lower())
    files = ["Dockerfile", ".dockerignore", "requirements.txt", "package.json", "package-lock.json"]
    return {
        "declared_bases": bases,
        "source_files_sha256": {
            name: hashlib.sha256((context / name).read_bytes()).hexdigest()
            for name in files
            if (context / name).is_file()
        },
    }


def build_inputs(context: Path, metadata: dict, image: dict) -> dict:
    declared = source_inputs(context)
    exported = metadata.get("containerimage.digest", "")
    config = metadata.get("containerimage.config.digest")
    require(re.fullmatch(DIGEST, exported), "BuildKit did not record the exported image digest")
    require(
        image["Id"] in {exported, config}, "BuildKit metadata does not identify the built image"
    )
    provenance = metadata.get("buildx.build.provenance", {})
    materials = provenance.get("materials", [])
    docker_materials = [m for m in materials if m.get("uri", "").startswith("pkg:docker/")]
    require(
        len(docker_materials) >= len(set(declared["declared_bases"])),
        "BuildKit did not record all external base images",
    )
    digests = {"sha256:" + m.get("digest", {}).get("sha256", "") for m in docker_materials}
    require(all(re.fullmatch(DIGEST, value) for value in digests), "Invalid base material digest")
    for reference in declared["declared_bases"]:
        if "@" in reference:
            require(
                reference.split("@", 1)[1] in digests, "BuildKit base differs from pinned source"
            )
    platform = image["Os"] + "/" + image["Architecture"]
    require(
        provenance.get("invocation", {}).get("environment", {}).get("platform", "").split("/")[:2]
        == platform.split("/"),
        "BuildKit platform differs from the built image",
    )
    return {
        **declared,
        "materials": materials,
        "exported_image_digest": exported,
        "config_digest": config,
        "platform": platform,
    }


def verify_source_inputs(context: Path, recorded: dict) -> None:
    for key, expected in source_inputs(context).items():
        require(recorded.get(key) == expected, f"Build inputs differ from committed source: {key}")
