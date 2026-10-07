"""Generate only the executable source-read OpenAPI and reachable schemas."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.main import app

OUTPUT = Path(__file__).resolve().parents[1] / "app/contracts/source-reads-v2/openapi.json"


def contract() -> dict[str, Any]:
    source = app.openapi()
    paths = {k: v for k, v in source["paths"].items() if k.startswith("/integration/v2/")}
    schemas: dict[str, Any] = {}

    def include_refs(value: Any) -> None:  # noqa: ANN401 - OpenAPI is a JSON tree
        if isinstance(value, dict):
            reference = value.get("$ref", "")
            if reference.startswith("#/components/schemas/"):
                name = reference.rsplit("/", 1)[-1]
                if name not in schemas:
                    schemas[name] = source["components"]["schemas"][name]
                    include_refs(schemas[name])
            for child in value.values():
                include_refs(child)
        elif isinstance(value, list):
            for child in value:
                include_refs(child)

    include_refs(paths)
    return {
        "openapi": source["openapi"],
        "info": {"title": "RetailOps authenticated source reads", "version": "2.0"},
        "paths": paths,
        "components": {
            "schemas": schemas,
            "securitySchemes": {
                "SourceReadCredential": source["components"]["securitySchemes"][
                    "SourceReadCredential"
                ]
            },
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rendered = (
        json.dumps(contract(), sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    ).encode()
    if args.check:
        if not OUTPUT.is_file() or OUTPUT.read_bytes() != rendered:
            parser.exit(1, "Source-read OpenAPI drift\n")
    else:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_bytes(rendered)
    print("Source-read OpenAPI verified" if args.check else "Source-read OpenAPI generated")  # noqa: T201 - CLI result
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
