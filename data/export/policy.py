"""Constrain generated writes/cleanup to this repository and protect Git fixtures."""

from __future__ import annotations

import shutil
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GENERATED_ROOT = ROOT / "data/generated"
FIXTURE_LIMIT_BYTES = 5 * 1024 * 1024
LAYOUT = ("facts", "truth", "raw_events", "operational_outputs", "reports", "manifests")


def tracked_files(repository: Path, target: Path | None = None) -> list[Path]:
    executable = shutil.which("git")
    if executable is None:
        msg = "Git is required to protect tracked artifacts."
        raise ValueError(msg)
    args = [executable, "ls-files", "-z"]
    if target is not None:
        args.extend(["--", ":(literal)" + target.relative_to(repository).as_posix()])
    result = subprocess.run(  # noqa: S603 - fixed executable, repository-relative path, no shell
        args,
        cwd=repository,
        capture_output=True,
        check=True,
    )
    return [repository / name.decode() for name in result.stdout.split(b"\0") if name]


def generated_target(target: Path, repository: Path = ROOT) -> Path:
    repository = repository.resolve()
    root = repository / "data/generated"
    candidate = target if target.is_absolute() else repository / target
    if ".." in candidate.parts or candidate == root or not candidate.is_relative_to(root):
        msg = "Target must be a child of the repository's data/generated root."
        raise ValueError(msg)
    for part in (candidate, *candidate.parents):
        if part.is_symlink():
            msg = "Symlink paths are forbidden for generated writes/cleanup."
            raise ValueError(msg)
        if part == repository:
            break
    if tracked_files(repository, candidate):
        msg = "Refusing to write/delete tracked artifacts or fixtures."
        raise ValueError(msg)
    if candidate.exists() and (
        not candidate.is_dir() or any(path.is_symlink() for path in candidate.rglob("*"))
    ):
        msg = "Generated target must be a directory without symlinks."
        raise ValueError(msg)
    return candidate


def cleanup(target: Path, *, delete: bool = False, repository: Path = ROOT) -> dict:
    target = generated_target(target, repository)
    if not target.is_dir():
        msg = "Cleanup target does not exist."
        raise ValueError(msg)
    files = [path for path in target.rglob("*") if path.is_file()]
    report = {
        "files": len(files),
        "bytes": sum(path.stat().st_size for path in files),
        "deleted": delete,
    }
    if delete:
        # Recheck immediately before deletion; rmtree itself does not follow directory symlinks.
        shutil.rmtree(generated_target(target, repository))
    return report


def fixture_budget(repository: Path = ROOT) -> dict:
    files = tracked_files(repository)
    forbidden = [
        path
        for path in files
        if any(
            path.is_relative_to(repository / prefix)
            for prefix in ("data/generated", "data/synthetic", "data/replay")
        )
        or (path.suffix == ".parquet" and not path.is_relative_to(repository / "data/fixtures"))
    ]
    if forbidden:
        msg = "Generated exports must not be tracked by Git."
        raise ValueError(msg)
    archives = [
        p
        for p in files
        if p.parent == repository / "services/api/tests/fixtures"
        and p.name.startswith("source_manifest_v2_")
    ]
    total = 0
    for path in archives:
        with zipfile.ZipFile(path) as archive:
            total += sum(info.file_size for info in archive.infolist())
    current = [p for p in files if p.is_relative_to(repository / "data/fixtures")]
    fixture_names = {p.relative_to(repository / "data/fixtures").parts[0] for p in current}
    for path in current:
        if path.suffix == ".zip":
            with zipfile.ZipFile(path) as archive:
                total += sum(info.file_size for info in archive.infolist())
        else:
            total += path.stat().st_size
    if total > FIXTURE_LIMIT_BYTES or len(fixture_names) > 1:
        msg = "Tracked fixtures exceed 5 MiB unpacked or one current fixture."
        raise ValueError(msg)
    return {
        "unpacked_bytes": total,
        "limit_bytes": FIXTURE_LIMIT_BYTES,
        "current_fixtures": len(fixture_names),
        "legacy_archives": len(archives),
    }
