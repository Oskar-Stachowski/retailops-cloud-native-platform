"""Original v12 SQL publisher -> broker -> complete Source SQL, authenticated TCP API and UI."""

import hashlib
import json
import os
import secrets
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from confluent_kafka import Producer
from native_forecast_browser import run_forecast_browser
from native_forecast_bundle import load_forecast_export
from scripts.prepare_intelligence_head import prepare_policy
from test_intelligence_checkpoint_durability import receipts, run
from test_intelligence_durability import (
    context as context,
)
from test_intelligence_durability import (
    intelligence_runtime as intelligence_runtime,
)
from test_intelligence_durability import (
    positions,
    rows,
)
from test_intelligence_durability import (
    runtime as runtime,
)

pytestmark = [
    pytest.mark.integration_broker,
    pytest.mark.skipif(
        os.getenv("REQUIRE_AI10_NATIVE_FORECAST_READ") != "1",
        reason="Dedicated original v12 output and live original database are required",
    ),
]
ROOT = Path(__file__).resolve().parents[1]


def test_original_v12_sql_outbox_complete_api_and_browser(
    context, monkeypatch, tmp_path
):
    acceptance, output, owner, events = load_forecast_export(
        Path(os.environ["AI10_NATIVE_FORECAST_OUTPUT"])
    )
    assert acceptance["commit"] == os.environ["AI10_NATIVE_PRODUCER_COMMIT"]
    assert acceptance["workflow_run_id"] == int(os.environ["GITHUB_RUN_ID"])
    broker = tmp_path / "broker-control.json"
    broker.write_text(json.dumps({"bootstrap.servers": context.bootstrap}))
    broker.chmod(0o600)
    publisher_report = tmp_path / "original-publisher.json"
    subprocess.run(
        [
            os.environ["AI10_NATIVE_DELIVERY_PYTHON"],
            os.environ["AI10_NATIVE_DELIVERY_SCRIPT"],
            "--original-control",
            os.environ["AI10_V12_ORIGINAL_DATABASE_CONTROL"],
            "--broker-control",
            str(broker),
            "--report",
            str(publisher_report),
        ],
        check=True,
        timeout=180,
    )
    original = json.loads(publisher_report.read_text())
    assert original["original_AI_database_publisher_attested"] is True
    assert original["delivered"] == 56
    expected = {value["event_id"]: (value, raw) for value, raw in events}
    delivery_positions = {
        (row["partition"], row["offset"]) for row in original["receipts"]
    }
    assert len(delivery_positions) == 56
    for row in original["receipts"]:
        assert (
            row["event_sha256"]
            == hashlib.sha256(expected[row["event_id"]][1]).hexdigest()
        )
    # Replay the same original bytes once. Original AI delivery already came from SQL.
    producer = Producer(
        {
            "bootstrap.servers": context.bootstrap,
            "enable.idempotence": True,
            "acks": "all",
        }
    )
    duplicate = []
    for _, raw in events:
        producer.produce(
            "retailops.intelligence.v2",
            value=raw,
            on_delivery=lambda error, message: duplicate.append((error, message)),
        )
    assert producer.flush(15) == 0 and len(duplicate) == 56
    assert all(error is None for error, _ in duplicate)
    run(context, count=100, bootstrap=True)
    run(context, count=12)
    transport = receipts(context)
    assert len(transport) == 112
    assert sum(row[2] == "projected" for row in transport) == 56
    assert sum(row[2] == "duplicate" for row in transport) == 56
    assert delivery_positions <= {(row[0], row[1]) for row in transport}
    assert rows(
        context,
        "SELECT count(*) FROM ai_forecast_results WHERE prediction_dataset_id=%s",
        (acceptance["publication_id"],),
    ) == [(56,)]
    committed = positions(context)
    assert all(
        committed[partition] > offset for partition, offset in delivery_positions
    )
    token = secrets.token_urlsafe(48)
    access = {
        "version": "retailops-intelligence-access-1.0",
        "principals": [
            dict(
                principal_id="ai10-native-v12-reader",
                credential_sha256=hashlib.sha256(token.encode()).hexdigest(),
                capabilities=["forecast:read"],
                product_ids=output["scope"]["product_ids"],
                selling_location_ids=output["scope"]["selling_location_ids"],
                channels=[output["scope"]["channel"]],
                release_ids=[output["release_id"]],
            )
        ],
    }
    access_path = tmp_path / "access.json"
    access_path.write_text(json.dumps(access))
    access_path.chmod(0o600)
    now = datetime.now(UTC)
    head = prepare_policy(
        [value for value, _ in events],
        products=output["scope"]["product_ids"],
        locations=output["scope"]["selling_location_ids"],
        horizon=14,
        reviewer="ai10-original-reviewed-development-publisher",
        owner_review_receipt=owner,
        reviewed_at=now,
        valid_until=now + timedelta(minutes=5),
    )
    head_path = tmp_path / "head.json"
    head_path.write_text(head.model_dump_json())
    head_path.chmod(0o600)
    monkeypatch.setenv("RETAILOPS_INTELLIGENCE_ACCESS_POLICY", str(access_path))
    monkeypatch.setenv("RETAILOPS_INTELLIGENCE_HEAD_POLICY", str(head_path))
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with socket.socket() as listener, (tmp_path / "api.log").open("wb") as log:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        base = "http://127.0.0.1:" + str(listener.getsockname()[1])
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--fd",
                str(listener.fileno()),
                "--no-access-log",
                "--log-level",
                "error",
            ],
            cwd=ROOT,
            env=env,
            pass_fds=(listener.fileno(),),
            stdout=log,
            stderr=log,
        )
        try:
            deadline = time.monotonic() + 30
            headers = {"Authorization": "Bearer " + token}
            while True:
                assert process.poll() is None
                try:
                    with opener.open(
                        urllib.request.Request(
                            base + "/intelligence/v2/forecasts/active?limit=100",
                            headers=headers,
                        ),
                        timeout=2,
                    ) as response:
                        body = json.load(response)
                    break
                except (urllib.error.URLError, TimeoutError):
                    assert time.monotonic() < deadline
                    time.sleep(0.1)
            assert body["pagination"]["total"] == 56
            actual = {
                item["forecast"]["prediction_id"]: item["forecast"]
                for item in body["items"]
            }
            assert actual == {
                value["payload"]["prediction_id"]: value["payload"]
                for value, _ in events
            }
            for suffix, status in (
                ("?user_id=platform-admin", 422),
                ("?product_id=foreign-product", 403),
            ):
                with pytest.raises(urllib.error.HTTPError) as failure:
                    opener.open(
                        urllib.request.Request(
                            base + "/intelligence/v2/forecasts" + suffix,
                            headers=headers,
                        ),
                        timeout=2,
                    )
                assert failure.value.code == status
            with pytest.raises(urllib.error.HTTPError) as failure:
                opener.open(base + "/intelligence/v2/forecasts", timeout=2)
            assert failure.value.code == 401
            browser = run_forecast_browser(
                api_url=base,
                control=tmp_path / "browser",
                policy_path=access_path,
                token=token,
                items=list(actual.values()),
                frontend=ROOT.parents[1] / "frontend",
                report=Path(os.environ["AI10_NATIVE_READ_REPORT"]).with_name(
                    "source-native-browser.json"
                ),
            )
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
    report = dict(
        status="passed",
        scope="original_v12_AI_SQL_publisher_broker_Source_SQL_TCP_API_built_UI",
        producer_commit=acceptance["commit"],
        source_commit=subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        original_AI_database_publisher_attested=True,
        original_delivery=original,
        rows=56,
        projected=56,
        duplicates=56,
        committed_next_offsets=committed,
        native_payloads_unchanged=True,
        original_quality_status="not_ready",
        original_quality_reclassified=False,
        model_refits=0,
        browser=browser,
    )
    Path(os.environ["AI10_NATIVE_READ_REPORT"]).write_text(
        json.dumps(report, sort_keys=True, indent=2) + "\n"
    )
