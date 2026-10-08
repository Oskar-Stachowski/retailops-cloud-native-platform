"""Seal immutable facts-only exports and read exact bytes through confined file descriptors."""

from __future__ import annotations

import ctypes
import fcntl
import hashlib
import json
import os
import stat
import sys
import tempfile
from pathlib import Path

from app.services.source_bundle_wire import MAX_FILE_BYTES, BundleFile, BundleManifest, canonical

INDEX_LIMIT = 4 * 1024**2


class BundleError(ValueError):
    pass


def unique_pairs(pairs: list[tuple]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            msg = "duplicate_json_key"
            raise BundleError(msg)
        result[key] = value
    return result


def decode(raw: bytes) -> dict:
    result = json.loads(raw, object_pairs_hook=unique_pairs)
    if not isinstance(result, dict):
        msg = "json_object_required"
        raise BundleError(msg)
    return result


def read_confined(root: Path, relative: str, maximum: int, *, private: bool = True) -> bytes:
    parts = relative.split("/")
    if any(part in {"", ".", ".."} for part in parts) or relative.startswith("/"):
        msg = "unsafe_bundle_reference"
        raise BundleError(msg)
    descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        handle = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW, dir_fd=descriptor)
        with os.fdopen(handle, "rb") as stream:
            info = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_nlink != 1
                or info.st_size > maximum
                or (private and (info.st_uid != os.geteuid() or info.st_mode & 0o077))
            ):
                msg = "unsafe_bundle_file"
                raise BundleError(msg)
            raw = stream.read(maximum + 1)
            if len(raw) > maximum:
                msg = "bundle_file_limit"
                raise BundleError(msg)
            return raw
    finally:
        os.close(descriptor)


def checked_root(root: Path) -> Path:
    if root.is_symlink():
        msg = "unsafe_bundle_root"
        raise BundleError(msg)
    resolved = root.resolve(strict=True)
    info = resolved.stat()
    if not resolved.is_dir() or info.st_uid != os.geteuid() or info.st_mode & 0o077:
        msg = "unsafe_bundle_root"
        raise BundleError(msg)
    return resolved


def load_manifest(root: Path, bundle_id: str) -> BundleManifest:
    if len(bundle_id) != 85 or not bundle_id.startswith("source-bundle-sha256-"):
        msg = "invalid_bundle_id"
        raise BundleError(msg)
    manifest = BundleManifest.model_validate_json(
        canonical(decode(read_confined(checked_root(root), bundle_id + "/index.json", INDEX_LIMIT)))
    )
    if manifest.bundle_id != bundle_id:
        msg = "bundle_identity_mismatch"
        raise BundleError(msg)
    return manifest


def file_bytes(root: Path, manifest: BundleManifest, file_id: str) -> tuple[bytes, BundleFile]:
    reference = next((file for file in manifest.files if file.file_id == file_id), None)
    if reference is None:
        raise FileNotFoundError
    raw = read_confined(
        checked_root(root), manifest.bundle_id + "/" + reference.path, reference.bytes
    )
    if len(raw) != reference.bytes or hashlib.sha256(raw).hexdigest() != reference.sha256:
        msg = "bundle_file_integrity"
        raise BundleError(msg)
    return raw, reference


def write_private(path: Path, raw: bytes) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def sync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def publish_noreplace(source: Path, destination: Path) -> None:
    library = ctypes.CDLL(None, use_errno=True)
    name, flag = ("renameat2", 1) if sys.platform == "linux" else ("renameatx_np", 4)
    function = getattr(library, name, None) if sys.platform in {"linux", "darwin"} else None
    if function is None:
        msg = "atomic_publication_unavailable"
        raise BundleError(msg)
    function.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    function.restype = ctypes.c_int
    first = os.open(source.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        second = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            if function(
                first, os.fsencode(source.name), second, os.fsencode(destination.name), flag
            ):
                raise OSError(ctypes.get_errno(), "atomic_publication_rejected")
            os.fsync(second)
        finally:
            os.close(second)
    finally:
        os.close(first)


def publish(snapshot: Path, store: Path) -> BundleManifest:  # noqa: PLR0912, PLR0915 - ordered sealing and publication
    """Copy the declared byte inventory; consumers independently verify typed source qualification."""
    if snapshot.is_symlink():
        msg = "unsafe_snapshot_root"
        raise BundleError(msg)
    snapshot = snapshot.resolve(strict=True)
    original = read_confined(snapshot, "snapshot_manifest.json", INDEX_LIMIT, private=False)
    document = decode(original)
    if document["descriptor"]["include_evaluation_truth"] is not False or any(
        table["data_class"] == "simulation_truth" for table in document["tables"]
    ):
        msg = "evaluation_truth_cannot_be_published"
        raise BundleError(msg)
    refs = [*document["metadata_files"], *(r for t in document["tables"] for r in t["files"])]
    main_sha = hashlib.sha256(original).hexdigest()
    checksum = read_confined(snapshot, "manifest.sha256", 80, private=False)
    if checksum.decode().strip() != main_sha:
        msg = "snapshot_manifest_integrity"
        raise BundleError(msg)
    refs.extend(
        (
            {"path": "snapshot_manifest.json", "sha256": main_sha, "bytes": len(original)},
            {
                "path": "manifest.sha256",
                "sha256": hashlib.sha256(checksum).hexdigest(),
                "bytes": len(checksum),
            },
        )
    )
    files = tuple(
        BundleFile.model_validate(
            {
                "file_id": hashlib.sha256(ref["path"].encode()).hexdigest(),
                "path": ref["path"],
                "sha256": ref["sha256"],
                "bytes": ref["bytes"],
            }
        )
        for ref in sorted(refs, key=lambda ref: ref["path"])
    )
    description = {
        "version": "retailops-source-bundle-1.0",
        "snapshot_id": document["snapshot_id"],
        "source_dataset_id": document["source_dataset_id"],
        "source_snapshot_version": document["schema_version"],
        "snapshot_manifest_sha256": main_sha,
        "files": [file.model_dump() for file in files],
        "total_bytes": sum(file.bytes for file in files),
        "replay_handoff": False,
    }
    payload = {
        **description,
        "bundle_id": "source-bundle-sha256-" + hashlib.sha256(canonical(description)).hexdigest(),
    }
    manifest = BundleManifest.model_validate_json(canonical(payload))
    if any(path.is_symlink() for path in snapshot.rglob("*")):
        msg = "snapshot_symlink_rejected"
        raise BundleError(msg)
    actual = {
        path.relative_to(snapshot).as_posix() for path in snapshot.rglob("*") if not path.is_dir()
    }
    if actual != {file.path for file in files}:
        msg = "snapshot_inventory_mismatch"
        raise BundleError(msg)
    store.mkdir(mode=0o700, parents=True, exist_ok=True)
    store = checked_root(store)
    if snapshot == store or snapshot.is_relative_to(store) or store.is_relative_to(snapshot):
        msg = "separate_publication_storage_required"
        raise BundleError(msg)
    lock = os.open(store / ".publication.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with (
        os.fdopen(lock, "a") as stream,
        tempfile.TemporaryDirectory(prefix=".staging-", dir=store) as temporary,
    ):
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        staging = Path(temporary) / "bundle"
        staging.mkdir(mode=0o700)
        for reference in files:
            raw = read_confined(
                snapshot, reference.path, min(MAX_FILE_BYTES, reference.bytes), private=False
            )
            if len(raw) != reference.bytes or hashlib.sha256(raw).hexdigest() != reference.sha256:
                msg = "snapshot_changed_or_corrupt"
                raise BundleError(msg)
            write_private(staging / reference.path, raw)
        write_private(staging / "index.json", canonical(payload) + b"\n")
        target = store / manifest.bundle_id
        if target.exists():
            if load_manifest(store, manifest.bundle_id) != manifest:
                msg = "immutable_bundle_conflict"
                raise BundleError(msg)
            for file in files:
                file_bytes(store, manifest, file.file_id)
        else:
            for path in sorted(staging.rglob("*"), key=lambda path: len(path.parts), reverse=True):
                if path.is_dir():
                    sync_directory(path)
            sync_directory(staging)
            publish_noreplace(staging, target)
            sync_directory(store)
    return manifest
