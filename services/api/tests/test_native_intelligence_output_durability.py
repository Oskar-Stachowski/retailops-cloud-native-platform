"""Original qualified stockout output -> real broker/checkpoints/SQL -> authenticated TCP API."""

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
from pathlib import Path

import pytest
from app.auth.intelligence_models import ModelAccessPolicy
from app.services.intelligence_contract import TOPIC
from app.services.intelligence_model_contract import model_partition_key
from confluent_kafka import Producer
from native_intelligence_bundle import load_stockout_export
from test_intelligence_checkpoint_durability import receipts, run
from test_intelligence_durability import (
    positions,
    rows,
)

pytestmark = pytest.mark.integration_broker
ROOT = Path(__file__).resolve().parents[1]


def test_complete_original_qualified_stockout_output_survives_transport_duplicate_and_tcp_api(
    context, monkeypatch, tmp_path
):
    # This test deliberately has no fixture fallback. Its dedicated CI caller must
    # provide output from the native frozen model acceptance on the same runner.
    exported = os.environ.get("AI10_NATIVE_STOCKOUT_OUTPUT")
    assert exported, (
        "AI10_NATIVE_STOCKOUT_OUTPUT is required; invented outputs cannot qualify this test"
    )
    acceptance, events = load_stockout_export(Path(exported))
    assert os.environ.get("AI10_NATIVE_PRODUCER_COMMIT") == acceptance["commit"]
    assert acceptance["workflow_run_id"] == int(os.environ["GITHUB_RUN_ID"])
    producer = Producer(
        {
            "bootstrap.servers": context.bootstrap,
            "enable.idempotence": True,
            "acks": "all",
        }
    )
    delivered = []
    for _ in range(2):
        for event, raw in events:
            producer.produce(
                TOPIC,
                key=model_partition_key(event).encode(),
                value=raw,
                on_delivery=lambda error, message: delivered.append((error, message)),
            )
    assert producer.flush(15) == 0
    assert len(delivered) == 2 * len(events) and all(
        error is None for error, _ in delivered
    )
    run(context, count=len(delivered))
    transport = receipts(context)
    assert len(transport) == len(delivered)
    assert sum(row[2] == "projected" for row in transport) == len(events)
    assert sum(row[2] == "duplicate" for row in transport) == len(events)
    committed = positions(context)
    for partition in (0, 1):
        consumed = [
            message.offset()
            for _, message in delivered
            if message.partition() == partition
        ]
        assert committed[partition] == (
            max(consumed) + 1 if consumed else context.initial[partition].offset
        )
    ids = [event["payload"]["risk_id"] for event, _ in events]
    assert rows(
        context, "SELECT count(*) FROM ai_model_results WHERE result_id=ANY(%s)", (ids,)
    ) == [(len(ids),)]
    token = secrets.token_urlsafe(48)
    items = [event["payload"] for event, _ in events]
    policy = {
        "version": "retailops-model-intelligence-access-1.0",
        "principals": [
            {
                "principal_id": "ai10-native-personal-reader",
                "credential_sha256": hashlib.sha256(token.encode()).hexdigest(),
                "capabilities": ["stockout:read"],
                "stockout_scope": {
                    "product_ids": sorted({item["product_id"] for item in items}),
                    "stock_location_ids": sorted(
                        {item["stock_location_id"] for item in items}
                    ),
                    "release_ids": sorted({item["release_id"] for item in items}),
                },
            }
        ],
    }
    ModelAccessPolicy.model_validate_json(json.dumps(policy))
    policy_path = tmp_path / "native-model-access.json"
    policy_path.write_text(json.dumps(policy))
    policy_path.chmod(0o600)
    monkeypatch.setenv("RETAILOPS_INTELLIGENCE_MODEL_ACCESS_POLICY", str(policy_path))
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT)
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
            ],
            cwd=ROOT,
            env=env,
            pass_fds=(listener.fileno(),),
            stdout=log,
            stderr=log,
        )
        try:
            deadline = time.monotonic() + 30
            while True:
                assert process.poll() is None, "owned native read API stopped"
                try:
                    with opener.open(base + "/health", timeout=1) as response:
                        if response.status == 200:
                            break
                except (urllib.error.URLError, TimeoutError):
                    assert time.monotonic() < deadline, (
                        "owned native read API was not ready"
                    )
                    time.sleep(0.1)
            resource = "/intelligence/v2/stockout-risks"
            for item in items:
                request = urllib.request.Request(
                    base + resource + "/" + item["risk_id"],
                    headers={"Authorization": "Bearer " + token},
                )
                with opener.open(request, timeout=10) as response:
                    result = json.load(response)
                    assert response.headers["Cache-Control"] == "no-store"
                assert result["result_id"] == item["risk_id"]
                assert result["source"] == "retailops-ai"
                assert result["result"] == item
            for query, authorization, expected_status in (
                ("", None, 401),
                ("?user_id=platform-admin", token, 422),
                ("?product_id=ffffffff-ffff-4fff-8fff-ffffffffffff", token, 403),
            ):
                request = urllib.request.Request(
                    base + resource + query,
                    headers={}
                    if authorization is None
                    else {"Authorization": "Bearer " + authorization},
                )
                with pytest.raises(urllib.error.HTTPError) as error:
                    opener.open(request, timeout=10)
                assert error.value.code == expected_status
                error.value.close()
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
    report_path = Path(os.environ["AI10_NATIVE_READ_REPORT"])
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(
            {
                "status": "passed",
                "scope": "qualified_native_stockout_output_to_broker_sql_and_authenticated_TCP_API",
                "producer_commit": acceptance["commit"],
                "source_commit": subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
                ).strip(),
                "qualification_id": acceptance["qualification_id"],
                "census_id": acceptance["native_outbox_census_id"],
                "rows": len(events),
                "projected": len(events),
                "duplicates": len(events),
                "http_literal_original_ids": len(items),
                "committed_next_offsets": committed,
                "native_payloads_unchanged": True,
                "model_refits": 0,
                "evidence_boundary": "file-handoff replay of committed outbox; original AI database publisher and UI are not attested",
            },
            indent=2,
        )
        + "\n"
    )
