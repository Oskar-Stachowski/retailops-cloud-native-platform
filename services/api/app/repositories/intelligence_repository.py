"""One transaction for inbox and immutable domain projection, independent of live metrics."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from psycopg.types.json import Jsonb

from app.db.connection import get_connection
from app.services.intelligence_contract import content_hash
from app.services.realtime_consumer import InvalidRealtimeEventError

if TYPE_CHECKING:
    from psycopg import Connection


class IntelligenceRepository:
    def project(self, event: dict[str, Any]) -> dict[str, Any]:
        payload = event["payload"]
        event_hash, payload_hash = content_hash(event), content_hash(payload)
        with get_connection() as connection:
            connection.execute("SET LOCAL statement_timeout='3s'")
            connection.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                ("ai-intelligence:" + payload["prediction_id"],),
            )
            old = connection.execute(
                "SELECT document_sha256 FROM ai_intelligence_inbox WHERE event_id=%s",
                (event["event_id"],),
            ).fetchone()
            if old is not None:
                if old["document_sha256"] != event_hash:
                    msg = "intelligence_event_identity_collision"
                    raise InvalidRealtimeEventError(msg)
                return {"status": "ignored_duplicate", "prediction_id": payload["prediction_id"]}
            self._insert_result(connection, payload, payload_hash)
            stored = connection.execute(
                "SELECT payload_sha256 FROM ai_forecast_results WHERE prediction_id=%s",
                (payload["prediction_id"],),
            ).fetchone()
            if stored is None or stored["payload_sha256"] != payload_hash:
                msg = "intelligence_result_identity_collision"
                raise InvalidRealtimeEventError(msg)
            connection.execute(
                """INSERT INTO ai_intelligence_inbox
                   (event_id,event_type,prediction_id,document_sha256) VALUES (%s,%s,%s,%s)""",
                (event["event_id"], event["event_type"], payload["prediction_id"], event_hash),
            )
        return {"status": "processed", "prediction_id": payload["prediction_id"]}

    @staticmethod
    def _insert_result(
        connection: Connection[dict[str, Any]], payload: dict[str, Any], payload_hash: str
    ) -> None:
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
        connection.execute(
            """INSERT INTO ai_forecast_results
               (prediction_id,prediction_dataset_id,product_id,selling_location_id,channel,
                forecast_origin,target_date,horizon_days,release_id,inference_run_id,generated_at,
                payload,payload_sha256)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT(prediction_id) DO NOTHING""",
            (*[payload[name] for name in fields], Jsonb(payload), payload_hash),
        )
