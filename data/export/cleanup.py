"""Preview generated artifact cleanup; deletion requires an explicit CLI flag."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from data.export.policy import cleanup


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Clean a child of data/generated; protect tracked fixtures."
    )
    parser.add_argument("target", type=Path)
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Delete after all path/Git checks; default is preview.",
    )
    args = parser.parse_args()
    print(json.dumps(cleanup(args.target, delete=args.delete)))  # noqa: T201 - bounded CLI result


if __name__ == "__main__":
    main()
