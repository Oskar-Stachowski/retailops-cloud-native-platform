# ruff: noqa: INP001
"""Validate the deployed API through its real Nginx proxy and inspect stored data."""

import hashlib
import importlib.util
import json
import sys
from urllib.request import Request, urlopen

from psycopg.types.json import Jsonb

spec = importlib.util.spec_from_file_location("recovery_checks", "/recovery/checks.py")
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)


def api(path: str, body: dict | None = None) -> dict:
    request = Request(
        "http://frontend:8080/api" + path,
        data=None if body is None else json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urlopen(request, timeout=10) as response:  # noqa: S310 -- fixed private Compose origin
        recovery.require(response.status == 200, "Deployed API returned an error")
        return json.load(response)


def validate(expected: dict) -> dict:
    recovery.require(
        recovery.snapshot() == expected["snapshot"], "Deployment changed stored data/schema"
    )
    recovery.require(api("/health")["status"] == "ok", "API health failed")
    recovery.require(api("/ready")["database"] == "ok", "API readiness failed")
    for entity in expected["entities"]:
        detail = api(f"/products/{entity['product_id']}/360?limit=50")
        matching = [r for r in detail[entity["resource"]] if r["id"] == entity["id"]]
        recovery.require(
            len(matching) == 1 and matching[0]["status"] == entity["status"],
            "Stored decision is missing from the deployed API",
        )
    for mutation in expected["mutations"]:
        recovery.require(
            api(mutation["path"], mutation["body"]) == mutation["response"],
            "Idempotent replay differs from its original response",
        )
    recovery.require(recovery.snapshot() == expected["snapshot"], "Replay duplicated audit history")
    return {
        "http_health_readiness": "passed",
        "decisions": 3,
        "idempotent_actions": 5,
        "data_schema_unchanged": True,
    }


def write(expected: dict, stage: str) -> dict:
    alert = expected["entities"][0]
    result = api(
        f"/alerts/{alert['id']}/comment?user_id=platform-admin",
        {
            "comment": f"Release drill: write after {stage}",
            "idempotency_key": "release-drill-" + stage,
        },
    )
    recovery.require(result["status"] == "resolved", "Comment changed the decision")
    after = recovery.snapshot()
    for table in ("workflow_actions", "workflow_audit_log"):
        recovery.require(
            after["tables"][table]["rows"] == expected["snapshot"]["tables"][table]["rows"] + 1,
            "New write did not append exactly one audit/history row",
        )
    return {**expected, "snapshot": after}


def seed_expansion(event: dict) -> dict:
    """Retain a known mechanics result through both image versions in the isolated drill."""
    suggestion = event["suggestion"]
    models = event["models"]
    event = event["forecast"]
    payload = event["payload"]
    fields = (
        "prediction_id",
        "prediction_dataset_id",
        "product_id",
        "selling_location_id",
        "channel",
        "forecast_origin",
        "target_date",
        "horizon_days",
        "release_id",
        "inference_run_id",
        "generated_at",
    )

    def digest(value: dict) -> str:
        return hashlib.sha256(
            json.dumps(
                value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
            ).encode()
        ).hexdigest()

    with recovery.connect() as connection:
        connection.execute(
            """INSERT INTO ai_forecast_results
               (prediction_id,prediction_dataset_id,product_id,selling_location_id,channel,
                forecast_origin,target_date,horizon_days,release_id,inference_run_id,generated_at,
                payload,payload_sha256)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (*[payload[name] for name in fields], Jsonb(payload), digest(payload)),
        )
        connection.execute(
            """INSERT INTO ai_intelligence_inbox
               (event_id,event_type,prediction_id,document_sha256) VALUES (%s,%s,%s,%s)""",
            (event["event_id"], event["event_type"], payload["prediction_id"], digest(event)),
        )
        # Explicit mechanics coordinates; this fixture is not a broker handoff.
        connection.execute(
            """INSERT INTO ai_intelligence_partitions
               (consumer_group,topic,partition,cluster_id,topic_id,coverage_start,next_offset,
                initial_policy,epoch,owner_id,claimed_at,checkpoint_at)
               VALUES ('rollback-mechanics','retailops.intelligence.v2',0,
                       'fixture-cluster','fixture-topic',0,1,'log_low',1,%s,now(),now())""",
            (event["event_id"],),
        )
        connection.execute(
            """INSERT INTO ai_intelligence_transport
               (consumer_group,topic,partition,offset_number,raw_sha256,outcome,prediction_id)
               VALUES ('rollback-mechanics','retailops.intelligence.v2',0,0,%s,'projected',%s)""",
            (digest({"mechanics_fixture": event}), payload["prediction_id"]),
        )
        item = suggestion["payload"]
        connection.execute(
            """INSERT INTO ai_recommendation_results
            (recommendation_id,trace_id,answer_id,candidate_id,product_id,selling_location_id,
             channel,policy_sha256,agent_config_version,created_at,expires_at,payload,payload_sha256)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                *[
                    item[key]
                    for key in (
                        "recommendation_id",
                        "trace_id",
                        "answer_id",
                        "candidate_id",
                        "product_id",
                        "selling_location_id",
                        "channel",
                        "policy_sha256",
                        "agent_config_version",
                        "created_at",
                        "expires_at",
                    )
                ],
                Jsonb(item),
                digest(item),
            ),
        )
        connection.execute(
            """INSERT INTO ai_recommendation_inbox
            (event_id,recommendation_id,document_sha256) VALUES (%s,%s,%s)""",
            (suggestion["event_id"], item["recommendation_id"], digest(suggestion)),
        )
        connection.execute(
            """INSERT INTO ai_intelligence_transport
            (consumer_group,topic,partition,offset_number,raw_sha256,outcome,recommendation_id)
            VALUES ('rollback-mechanics','retailops.intelligence.v2',0,1,%s,'projected',%s)""",
            (digest({"mechanics_fixture": suggestion}), item["recommendation_id"]),
        )
        for offset, model in enumerate(models, start=2):
            item = model["payload"]
            anomaly = model["event_type"] == "anomaly_detected"
            result_id = item["anomaly_id"] if anomaly else item["risk_id"]
            connection.execute(
                """INSERT INTO ai_model_results
                (result_id,event_type,product_id,selling_location_id,stock_location_id,channel,currency,
                 as_of,generated_at,model_name,model_version,release_id,inference_run_id,source_dataset_id,
                 payload,payload_sha256)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    result_id,
                    model["event_type"],
                    item["product_id"],
                    item["selling_location_id"] if anomaly else None,
                    None if anomaly else item["stock_location_id"],
                    item["channel"] if anomaly else None,
                    item["currency"] if anomaly else None,
                    item["as_of"],
                    item["generated_at"],
                    item["detector_name"] if anomaly else item["model_name"],
                    item["detector_version"] if anomaly else item["model_version"],
                    item["release_id"],
                    item["inference_run_id"],
                    item["source_dataset_id"] if anomaly else item["lineage"]["source_dataset_id"],
                    Jsonb(item),
                    digest(item),
                ),
            )
            connection.execute(
                """INSERT INTO ai_model_intelligence_inbox
                (event_id,result_id,document_sha256) VALUES (%s,%s,%s)""",
                (model["event_id"], result_id, digest(model)),
            )
            connection.execute(
                """INSERT INTO ai_intelligence_transport
                (consumer_group,topic,partition,offset_number,raw_sha256,outcome,model_result_id)
                VALUES ('rollback-mechanics','retailops.intelligence.v2',0,%s,%s,'projected',%s)""",
                (offset, digest({"mechanics_fixture": model}), result_id),
            )
        connection.execute(
            "UPDATE ai_intelligence_partitions SET next_offset=%s WHERE consumer_group='rollback-mechanics'",
            (2 + len(models),),
        )
    return {
        "forecast_results": 1,
        "inbox_records": 1,
        "partition_checkpoints": 1,
        "transport_receipts": 2 + len(models),
        "suggestion_results": 1,
        "suggestion_inbox_records": 1,
        "model_results": len(models),
        "model_inbox_records": len(models),
        "fixture": "mechanics",
    }


if __name__ == "__main__":
    expected = json.load(sys.stdin)
    if sys.argv[1] == "seed-expansion":
        result = seed_expansion(expected)
    else:
        result = validate(expected) if sys.argv[1] == "validate" else write(expected, sys.argv[2])
    sys.stdout.write(json.dumps(result) + "\n")
