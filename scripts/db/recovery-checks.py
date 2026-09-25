# ruff: noqa: INP001
"""Checks executed inside the disposable recovery API container."""

import hashlib
import json
import os
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import psycopg
from psycopg import sql


def require(condition: object, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def connect() -> psycopg.Connection:
    url = os.environ["DATABASE_URL"]
    parsed = urlparse(url)
    require(
        parsed.hostname == "db"
        and parsed.username == "recovery"
        and parsed.path in {"/source", "/restored"},
        "Recovery checks require the dedicated disposable database",
    )
    return psycopg.connect(url)


def fingerprint(rows: object) -> str:
    return hashlib.sha256(json.dumps(rows, sort_keys=True, default=str).encode()).hexdigest()


def snapshot() -> dict:
    with connect() as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        names = conn.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
        ).fetchall()
        tables = {}
        for (name,) in names:
            rows = conn.execute(
                sql.SQL(
                    'SELECT to_jsonb(t)::text FROM public.{} t ORDER BY to_jsonb(t)::text COLLATE "C"'
                ).format(sql.Identifier(name))
            ).fetchall()
            tables[name] = {"rows": len(rows), "sha256": fingerprint(rows)}
        sequences = {}
        for (name,) in conn.execute(
            "SELECT sequencename FROM pg_sequences WHERE schemaname = 'public' ORDER BY 1"
        ):
            sequences[name] = conn.execute(
                sql.SQL("SELECT last_value, is_called FROM public.{}").format(sql.Identifier(name))
            ).fetchone()
        columns = conn.execute(
            "SELECT table_name, column_name, data_type, udt_name, is_nullable, column_default, "
            "character_maximum_length, numeric_precision, numeric_scale, datetime_precision, is_identity "
            "FROM information_schema.columns WHERE table_schema = 'public' "
            "ORDER BY table_name, ordinal_position"
        ).fetchall()
        constraints = conn.execute(
            "SELECT c.relname, co.conname, pg_get_constraintdef(co.oid), co.convalidated "
            "FROM pg_constraint co JOIN pg_class c ON c.oid = co.conrelid "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' ORDER BY c.relname, co.conname"
        ).fetchall()
        # pg_dump/reparse can move varchar->text casts from an array to its
        # elements. Let PostgreSQL parse both definitions in the same way, in
        # temporary empty tables; do not weaken the comparison by dropping CHECKs.
        temporary_tables = set()
        normalized_constraints = []
        for table, name, definition, validated in constraints:
            normalized = definition
            if definition.startswith("CHECK "):
                temporary = "recovery_schema_" + table
                if table not in temporary_tables:
                    conn.execute(
                        sql.SQL("CREATE TEMP TABLE {} (LIKE public.{}) ON COMMIT DROP").format(
                            sql.Identifier(temporary), sql.Identifier(table)
                        )
                    )
                    temporary_tables.add(table)
                conn.execute(
                    sql.SQL("ALTER TABLE pg_temp.{} ADD CONSTRAINT {} {}").format(
                        sql.Identifier(temporary), sql.Identifier(name), sql.SQL(definition)
                    )
                )
                normalized = conn.execute(
                    "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                    "WHERE conrelid = to_regclass(%s) AND conname = %s",
                    ("pg_temp." + temporary, name),
                ).fetchone()[0]
            normalized_constraints.append((table, name, normalized, validated))
        constraints = normalized_constraints
        indexes = conn.execute(
            "SELECT tablename, indexname, indexdef FROM pg_indexes "
            "WHERE schemaname = 'public' ORDER BY tablename, indexname"
        ).fetchall()
        require(all(row[3] for row in constraints), "Unvalidated database constraint")
        return {
            "tables": tables,
            "sequences_sha256": fingerprint(sequences),
            "sequence_count": len(sequences),
            "schema_sha256": fingerprint([columns, constraints, indexes]),
        }


def api(path: str, body: dict | None = None) -> dict:
    request = Request(
        "http://127.0.0.1:8000" + path,
        data=None if body is None else json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urlopen(request, timeout=10) as response:  # noqa: S310 -- fixed loopback HTTP origin
        require(response.status == 200, f"Unexpected HTTP status for {path}")
        return json.load(response)


@contextmanager
def running_api() -> Iterator[None]:
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1"],
        stdout=sys.stderr,
        stderr=sys.stderr,
    )
    try:
        deadline = time.monotonic() + 30
        while True:
            require(process.poll() is None, "API exited before readiness")
            try:
                require(api("/ready")["database"] == "ok", "Database is not ready")
                break
            except URLError:
                require(time.monotonic() < deadline, "API readiness timed out")
                time.sleep(0.25)
        require(api("/health")["status"] == "ok", "API health failed")
        yield
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def prepare() -> dict:
    with connect() as conn:
        alert = conn.execute(
            "SELECT id, product_id FROM alerts WHERE status = 'open' ORDER BY id LIMIT 1"
        ).fetchone()
        recs = conn.execute(
            "SELECT id, product_id FROM recommendations WHERE status = 'proposed' ORDER BY id LIMIT 2"
        ).fetchall()
    require(alert and len(recs) == 2, "Demo fixture lacks recovery workflow candidates")
    cases = [
        ("alerts", alert, "acknowledge", "acknowledged"),
        ("alerts", alert, "resolve", "resolved"),
        ("recommendations", recs[0], "accept", "accepted"),
        ("recommendations", recs[0], "resolve", "implemented"),
        ("recommendations", recs[1], "reject", "rejected"),
    ]
    mutations = []
    with running_api():
        for resource, (entity_id, _product_id), action, status in cases:
            path = f"/{resource}/{entity_id}/{action}?user_id=platform-admin"
            body = {
                "comment": f"Recovery drill: {action} before backup",
                "idempotency_key": f"recovery-{resource}-{action}",
            }
            result = api(path, body)
            require(result["status"] == status, f"Workflow did not persist {status}")
            require(result["workflow_action"]["performed_by_user_id"], "Missing actor")
            mutations.append({"path": path, "body": body, "response": result})
        entities = [
            {"resource": resource, "id": str(row[0]), "product_id": str(row[1]), "status": status}
            for resource, row, status in [
                ("alerts", alert, "resolved"),
                ("recommendations", recs[0], "implemented"),
                ("recommendations", recs[1], "rejected"),
            ]
        ]
    return {"snapshot": snapshot(), "mutations": mutations, "entities": entities}


def verify(expected: dict) -> dict:
    require(snapshot() == expected["snapshot"], "Restored rows, schema or sequences differ")
    with running_api():
        for entity in expected["entities"]:
            detail = api(f"/products/{entity['product_id']}/360?limit=50")
            matches = [row for row in detail[entity["resource"]] if row["id"] == entity["id"]]
            require(
                len(matches) == 1 and matches[0]["status"] == entity["status"],
                "Product 360 lost the recorded decision",
            )
        for mutation in expected["mutations"]:
            require(
                api(mutation["path"], mutation["body"]) == mutation["response"],
                "Idempotent replay changed the recorded response",
            )
        require(snapshot() == expected["snapshot"], "Replay duplicated or changed audit history")
        # A new write after recovery also exercises restored defaults/sequences and FKs.
        alert = expected["entities"][0]
        result = api(
            f"/alerts/{alert['id']}/comment?user_id=platform-admin",
            {
                "comment": "Recovery drill: new write after restore",
                "idempotency_key": "recovery-after-restore",
            },
        )
        require(result["status"] == "resolved", "New comment changed the decision")
        after = snapshot()
        for table in ("workflow_actions", "workflow_audit_log"):
            require(
                after["tables"][table]["rows"] == expected["snapshot"]["tables"][table]["rows"] + 1,
                "New write did not append exactly one history record",
            )
    return {
        "health": "passed",
        "product_360": "passed",
        "idempotency": "passed",
        "new_workflow_write": "passed",
        "decisions_restored": len(expected["entities"]),
        "actions_replayed": len(expected["mutations"]),
    }


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "prepare":
        result = prepare()
    elif mode == "snapshot":
        result = snapshot()
    elif mode == "verify":
        result = verify(json.load(sys.stdin))
    else:
        sys.exit(2)
    sys.stdout.write(json.dumps(result, sort_keys=True) + "\n")
