"""Build or verify an explicit closure artifact from a verified source 2.8."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from data.day_coverage.package import build, verify


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "verify"))
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--directory", type=Path)
    args = parser.parse_args()
    if args.action == "build":
        if args.output_root is None:
            parser.error("build requires --output-root")
        value = build(args.source, args.output_root)
    else:
        if args.directory is None:
            parser.error("verify requires --directory")
        value = verify(args.directory, args.source).model_dump()
    sys.stdout.write(json.dumps(value, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
