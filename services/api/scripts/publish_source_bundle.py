"""Explicit operator command; never export legacy database pages as a snapshot."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.services.source_bundles import publish


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot-dir", type=Path, required=True)
    parser.add_argument("--store", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = publish(args.snapshot_dir, args.store)
    except (OSError, ValueError, KeyError, TypeError, RecursionError):
        sys.stdout.write('{"status":"failed","code":"snapshot_publication_rejected"}\n')
        return 1
    sys.stdout.write(
        json.dumps({"status": "published_or_verified", **result.model_dump(mode="json")}) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
