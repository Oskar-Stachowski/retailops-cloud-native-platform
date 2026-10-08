"""Immutable AI suggestions and inbox participate in the caller's checkpoint transaction."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from psycopg.types.json import Jsonb

from app.services.intelligence_contract import content_hash
from app.services.realtime_consumer import InvalidRealtimeEventError

if TYPE_CHECKING:
    from psycopg import Connection


def project_suggestion(
    connection: Connection[dict[str, Any]], event: dict[str, Any]
) -> dict[str, Any]:
    payload = event["payload"]
    identity = payload["recommendation_id"]
    event_hash, payload_hash = content_hash(event), content_hash(payload)
    connection.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
        ("ai-suggestion:" + identity,),
    )
    old = connection.execute(
        "SELECT document_sha256 FROM ai_recommendation_inbox WHERE event_id=%s",
        (event["event_id"],),
    ).fetchone()
    if old is not None:
        if old["document_sha256"] != event_hash:
            msg = "intelligence_event_identity_collision"
            raise InvalidRealtimeEventError(msg)
        return {"status": "ignored_duplicate", "recommendation_id": identity}
    fields = (
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
    connection.execute(
        """INSERT INTO ai_recommendation_results
        (recommendation_id,trace_id,answer_id,candidate_id,product_id,selling_location_id,channel,
         policy_sha256,agent_config_version,created_at,expires_at,payload,payload_sha256)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT(recommendation_id) DO NOTHING""",
        (*[payload[name] for name in fields], Jsonb(payload), payload_hash),
    )
    stored = connection.execute(
        "SELECT payload_sha256 FROM ai_recommendation_results WHERE recommendation_id=%s",
        (identity,),
    ).fetchone()
    if stored is None or stored["payload_sha256"] != payload_hash:
        msg = "intelligence_result_identity_collision"
        raise InvalidRealtimeEventError(msg)
    connection.execute(
        """INSERT INTO ai_recommendation_inbox
        (event_id,recommendation_id,document_sha256) VALUES (%s,%s,%s)""",
        (event["event_id"], identity, event_hash),
    )
    return {"status": "processed", "recommendation_id": identity}
