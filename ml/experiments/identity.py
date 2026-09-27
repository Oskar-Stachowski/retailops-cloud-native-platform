from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import subprocess
import zipfile
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping
    from pathlib import Path

DEPENDENCIES = ("joblib", "numpy", "scikit-learn", "scipy", "threadpoolctl")
SOURCE_DIRECTORIES = ("data/generator", "ml")
SOURCE_FILES = (
    "Makefile",
    "data/__init__.py",
    "pyproject.toml",
    "services/api/requirements.txt",
    "services/api/requirements-dev.txt",
)
SOURCE_ARCHIVE_FILENAME = "experiment_source.zip"
INPUT_MANIFEST_FILENAME = "experiment_inputs.json"
RUN_MANIFEST_FILENAME = "run_manifest.json"


def canonical_sha256(value: object) -> str:
    """Hash logical JSON content independently of object insertion order."""
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def logical_rows_sha256(rows: Iterable[Mapping[str, object]]) -> str:
    """Hash ordered rows without materializing a second full dataset in memory."""
    digest = hashlib.sha256()
    for row in rows:
        digest.update(canonical_sha256(row).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_file(path: Path, value: dict[str, object]) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )


def source_files(repo_root: Path) -> list[Path]:
    paths = [repo_root / name for name in SOURCE_FILES]
    for directory in SOURCE_DIRECTORIES:
        paths.extend((repo_root / directory).rglob("*.py"))
        paths.extend((repo_root / directory).rglob("*.json"))
    return sorted({path for path in paths if path.is_file()}, key=lambda path: path.as_posix())


def source_identity(repo_root: Path) -> tuple[dict[str, object], list[Path], dict[str, str]]:
    paths = source_files(repo_root)
    checksums = {path.relative_to(repo_root).as_posix(): file_sha256(path) for path in paths}
    git_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],  # noqa: S607 - git from project PATH
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    changed_paths = subprocess.run(  # noqa: S603 - fixed git command, no shell
        ["git", "status", "--porcelain", "--untracked-files=normal", "--", *checksums],  # noqa: S607 - git from project PATH
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    return (
        {
            "git_commit": git_commit,
            "source_tree_sha256": canonical_sha256(checksums),
            "source_files_sha256": checksums,
            "source_worktree_changes": changed_paths,
        },
        paths,
        checksums,
    )


def write_source_archive(repo_root: Path, paths: list[Path], output_path: Path) -> None:
    """Preserve exact source bytes, including uncommitted changes, for reproduction."""
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in paths:
            name = path.relative_to(repo_root).as_posix()
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())


def environment_identity() -> dict[str, object]:
    return {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "system": platform.system(),
        "machine": platform.machine(),
        "dependencies": {name: importlib.metadata.version(name) for name in DEPENDENCIES},
    }


def artifact_checksums(output_dir: Path, filenames: list[str]) -> dict[str, str]:
    return {name: file_sha256(output_dir / name) for name in sorted(filenames)}
