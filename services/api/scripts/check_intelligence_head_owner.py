"""Check the existing CI owner checkout against the exact lifecycle review implementation."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "app/contracts"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner-root", type=Path, required=True)
    args = parser.parse_args()
    owner = json.loads((ROOT / "intelligence-head-v1/owner.json").read_bytes())
    client = json.loads((ROOT / "source-reads-v2/client.json").read_bytes())
    if (
        owner["repository"] != client["repository"]
        or owner["commit"] != client["commit"]
        or owner["path"] != "scripts/mlflow_v12_lifecycle.py"
        or hashlib.sha256((args.owner_root / owner["path"]).read_bytes()).hexdigest()
        != owner["sha256"]
    ):
        parser.exit(1, "AI10 lifecycle owner pin drift\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
