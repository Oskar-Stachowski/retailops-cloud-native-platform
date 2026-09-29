"""Publish a complete local directory atomically, with kernel-enforced no replacement."""

from __future__ import annotations

import ctypes
import os
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def publish_directory(staging: Path, destination: Path) -> None:
    """Fail closed on unsupported filesystems/platforms, including empty destinations."""
    libc = ctypes.CDLL(None, use_errno=True)
    if sys.platform == "darwin":
        rename = libc.renamex_np
        rename.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        result = rename(os.fsencode(staging), os.fsencode(destination), 4)  # RENAME_EXCL
    elif sys.platform == "linux" and hasattr(libc, "renameat2"):
        rename = libc.renameat2
        rename.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        rename.restype = ctypes.c_int
        result = rename(-100, os.fsencode(staging), -100, os.fsencode(destination), 1)
        # AT_FDCWD=-100, RENAME_NOREPLACE=1. No check-then-rename fallback.
    else:
        msg = "Atomic no-replace publication requires Linux renameat2 or macOS renamex_np."
        raise OSError(msg)
    if result != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), str(destination))
    sync_directory(destination.parent)


def sync_directory(directory: Path) -> None:
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def sync_bundle(directory: Path) -> None:
    paths = list(directory.rglob("*"))
    for path in paths:
        if path.is_file():
            with path.open("rb") as stream:
                os.fsync(stream.fileno())
    for path in sorted((p for p in paths if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
        sync_directory(path)
    sync_directory(directory)
