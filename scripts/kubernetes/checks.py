# ruff: noqa: INP001
"""Checks run only in the disposable Kubernetes drill's checker Pod."""

import ipaddress
import json
import os
import sys
import time
from contextlib import nullcontext
from datetime import UTC, datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from uuid import uuid4

import psycopg

sys.path.insert(0, "/release")
import checks as release_checks

recovery = release_checks.recovery
require = recovery.require


def connect() -> psycopg.Connection:
    parsed = urlparse(os.environ["DATABASE_URL"])
    require(
        os.environ.get("RETAILOPS_K8S_DRILL") == "1"
        and parsed.hostname == "postgres"
        and parsed.username == "retailops"
        and parsed.path == "/retailops",
        "Only the isolated drill database is allowed",
    )
    return psycopg.connect(os.environ["DATABASE_URL"])


def request(
    path: str, body: dict | None = None, *, origin: str = "http://retailops-frontend"
) -> tuple:
    req = Request(  # noqa: S310 -- controlled cluster HTTP origin
        origin + path,
        data=None if body is None else json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(req, timeout=4) as response:  # noqa: S310 -- controlled cluster services
            return response.status, response.read().decode()
    except HTTPError as error:
        return error.code, error.read().decode()


def api(path: str, body: dict | None = None) -> dict:
    status, content = request("/api" + path, body)
    require(status == 200, f"API failed: {path} HTTP {status}")
    return json.loads(content)


snapshot_all = recovery.snapshot


def snapshot() -> dict:
    result = snapshot_all()
    # Consumer start/stop counters and timestamps are expected to change on rollout.
    # Every other table, including ingested events/metrics and all schema/sequences,
    # is compared byte-for-byte using the shared recovery checks.
    result["tables"].pop("realtime_consumer_state", None)
    return result


recovery.connect = connect
recovery.api = api
recovery.running_api = nullcontext
recovery.snapshot = snapshot
release_checks.api = api


def streaming() -> dict:
    from confluent_kafka import Producer

    event_id = str(uuid4())
    now = datetime.now(UTC).isoformat()
    event = {
        "event_id": event_id,
        "event_type": "sale_completed",
        "schema_version": "1.0",
        "source": "kubernetes-drill",
        "correlation_id": event_id,
        "occurred_at": now,
        "ingested_at": now,
        "payload": {"quantity": 2, "unit_price": 7, "total_amount": 14},
    }
    producer = Producer({"bootstrap.servers": "redpanda:9092"})
    errors = []

    def delivered(error: object, _message: object) -> None:
        if error is not None:
            errors.append(str(error))

    # A duplicate proves broker delivery and the real consumer's idempotency.
    for _ in range(2):
        producer.produce("retailops.sales.v1", json.dumps(event).encode(), callback=delivered)
    require(producer.flush(20) == 0 and not errors, "Broker publish failed")
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        with connect() as conn:
            row = conn.execute(
                "SELECT status FROM realtime_event_log WHERE event_id=%s", (event_id,)
            ).fetchone()
            state = conn.execute(
                "SELECT ignored_events FROM realtime_consumer_state "
                "WHERE consumer_name='retailops-realtime-consumer'"
            ).fetchone()
            count = conn.execute(
                "SELECT count(*) FROM realtime_metric_observations WHERE event_id=%s", (event_id,)
            ).fetchone()[0]
        if row == ("processed",) and state and state[0] >= 1 and count == 3:
            live = api("/dashboard/live-operations?window_minutes=15")
            require(event_id in json.dumps(live), "Processed event absent from live operations API")
            return {"event_id": event_id, "deliveries": 2, "stored_events": 1, "metric_rows": count}
        time.sleep(1)
    require(condition=False, message="Broker-to-consumer-to-database processing timed out")
    return {}


def database_outage() -> dict:
    # The caller passes the Pod IP because the Service must lose its ready endpoint.
    origin = "http://" + sys.argv[2] + ":8000"
    healthy = request("/health", origin=origin)[0]
    ready = request("/ready", origin=origin)[0]
    require(healthy == 200 and ready == 503, "Liveness/readiness did not separate DB outage")
    return {"direct_health": healthy, "direct_ready": ready}


def probe() -> dict:
    try:
        with urlopen(
            "http://" + str(ipaddress.ip_address(sys.argv[2])) + ":8000/health", timeout=3
        ) as response:
            return {"reachable": response.status == 200}
    except (URLError, TimeoutError):
        return {"reachable": False}


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "prepare":
        result = recovery.prepare()
    elif mode == "validate":
        result = release_checks.validate(json.load(sys.stdin))
    elif mode == "write":
        result = release_checks.write(json.load(sys.stdin), sys.argv[2])
    elif mode == "stream":
        result = streaming()
    elif mode == "snapshot":
        result = snapshot()
    elif mode == "db-outage":
        result = database_outage()
    elif mode == "probe":
        result = probe()
    elif mode == "head":
        with connect() as conn:
            result = conn.execute("SELECT version_num FROM alembic_version").fetchone()[0]
    else:
        require(condition=False, message="Unknown check")
    sys.stdout.write(json.dumps(result) + "\n")
