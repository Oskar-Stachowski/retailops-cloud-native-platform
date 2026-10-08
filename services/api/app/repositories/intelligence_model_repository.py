"""Native model history and inbox join the fenced consumer transaction."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from psycopg.types.json import Jsonb

from app.services.intelligence_contract import content_hash
from app.services.realtime_consumer import InvalidRealtimeEventError

if TYPE_CHECKING:
    from psycopg import Connection


def project_model(connection: Connection[dict[str, Any]], event: dict[str, Any]) -> dict[str, Any]:
    kind, payload = event["event_type"], event["payload"]
    anomaly = kind == "anomaly_detected"
    identity = payload["anomaly_id"] if anomaly else payload["risk_id"]
    event_hash, payload_hash = content_hash(event), content_hash(payload)
    connection.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
        ("ai-model:" + identity,),
    )
    old = connection.execute(
        "SELECT document_sha256 FROM ai_model_intelligence_inbox WHERE event_id=%s",
        (event["event_id"],),
    ).fetchone()
    if old is not None:
        if old["document_sha256"] != event_hash:
            msg = "intelligence_event_identity_collision"
            raise InvalidRealtimeEventError(msg)
        return {"status": "ignored_duplicate", "model_result_id": identity}
    connection.execute(
        """INSERT INTO ai_model_results
        (result_id,event_type,product_id,selling_location_id,stock_location_id,channel,currency,
         as_of,generated_at,model_name,model_version,release_id,inference_run_id,source_dataset_id,
         payload,payload_sha256)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT(result_id) DO NOTHING""",
        (
            identity,
            kind,
            payload["product_id"],
            payload["selling_location_id"] if anomaly else None,
            None if anomaly else payload["stock_location_id"],
            payload["channel"] if anomaly else None,
            payload["currency"] if anomaly else None,
            payload["as_of"],
            payload["generated_at"],
            payload["detector_name"] if anomaly else payload["model_name"],
            payload["detector_version"] if anomaly else payload["model_version"],
            payload["release_id"],
            payload["inference_run_id"],
            payload["source_dataset_id"] if anomaly else payload["lineage"]["source_dataset_id"],
            Jsonb(payload),
            payload_hash,
        ),
    )
    stored = connection.execute(
        "SELECT payload_sha256 FROM ai_model_results WHERE result_id=%s",
        (identity,),
    ).fetchone()
    if stored is None or stored["payload_sha256"] != payload_hash:
        msg = "intelligence_result_identity_collision"
        raise InvalidRealtimeEventError(msg)
    connection.execute(
        """INSERT INTO ai_model_intelligence_inbox
        (event_id,result_id,document_sha256) VALUES (%s,%s,%s)""",
        (event["event_id"], identity, event_hash),
    )
    return {"status": "processed", "model_result_id": identity}
