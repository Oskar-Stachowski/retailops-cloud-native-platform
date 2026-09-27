# ruff: noqa: INP001
"""Verify that normal Compose down/up preserves seeded application data."""

import json
import os
import shlex
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "ci-cd/reports/docker/compose-persistence.json"


def run(args: list[str], *, capture: bool = False, stdin: str | None = None) -> str:
    result = subprocess.run(  # noqa: S603 -- fixed commands in an isolated CI project
        args,
        cwd=ROOT,
        text=True,
        check=True,
        capture_output=capture,
        input=stdin,
        timeout=600,
    )
    return result.stdout.strip() if capture else ""


def main() -> None:
    project = os.environ.get("COMPOSE_PROJECT_NAME", "")
    compose = shlex.split(os.environ.get("COMPOSE", ""))
    if not project.startswith("retailops-ci-") or compose[:2] != ["docker", "compose"]:
        msg = "Persistence check requires an isolated Compose CI project"
        raise SystemExit(msg)
    if "-p" not in compose or compose[compose.index("-p") + 1] != project:
        msg = "Compose command does not target the isolated CI project"
        raise SystemExit(msg)

    report = {
        "project": project,
        "started_at": datetime.now(UTC).isoformat(),
        "status": "failed",
    }
    marker = "ops01_persistence_" + uuid4().hex
    psql = [
        *compose,
        "exec",
        "-T",
        "db",
        "psql",
        "-X",
        "-A",
        "-t",
        "-v",
        "ON_ERROR_STOP=1",
        "-U",
        os.environ["POSTGRES_USER"],
        "-d",
        os.environ["POSTGRES_DB"],
    ]
    try:
        product_id = run(psql, capture=True, stdin="SELECT id FROM products ORDER BY id LIMIT 1;\n")
        if not product_id:
            msg = "Disposable seed contains no products"
            raise RuntimeError(msg)
        UUID(product_id)
        report["product_id"] = product_id
        run(
            [*psql, "-v", "marker=" + marker, "-v", "product_id=" + product_id],
            stdin="UPDATE products SET name = :'marker' WHERE id = :'product_id';\n",
        )

        run(["make", "compose-down"])
        run(["make", "compose-up"])

        observed = run(
            [*psql, "-v", "product_id=" + product_id],
            capture=True,
            stdin="SELECT name FROM products WHERE id = :'product_id';\n",
        )
        if observed != marker:
            msg = "Product changed or disappeared after normal Compose down/up"
            raise RuntimeError(msg)
        report["status"] = "passed"
        print("Compose persistence check passed: product survived down/up.")  # noqa: T201
    finally:
        report["finished_at"] = datetime.now(UTC).isoformat()
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
