"""Read only explicitly selected, complete immutable publications in one DB snapshot."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Never
from uuid import uuid5

from fastapi import HTTPException
from psycopg import Error as DatabaseError

from app.db.connection import get_connection
from app.services.intelligence_contract import (
    EVENT_NAMESPACE,
    TOPIC,
    content_hash,
    validate_event,
)
from app.services.intelligence_head_policy import ApprovedForecastHead, head_policy
from app.services.intelligence_reader import read_item
from app.services.realtime_consumer import InvalidRealtimeEventError

if TYPE_CHECKING:
    from psycopg import Connection

    from app.auth.intelligence import IntelligencePrincipal

MAX_PUBLICATION_BYTES = 16 * 1024 * 1024
BINDING_FIELDS = (
    "release_id",
    "inference_run_id",
    "prediction_dataset_id",
    "model_name",
    "model_version",
    "approval_sha256",
    "runtime_pin_sha256",
    "image_digest",
    "receipt_id",
    "source_dataset_id",
    "curated_dataset_id",
    "feature_set_id",
    "profile_id",
    "channel",
)


def _fail(reason: str) -> Never:
    raise HTTPException(503, detail=reason)


def _matches(
    head: ApprovedForecastHead, principal: IntelligencePrincipal, filters: dict[str, str | None]
) -> bool:
    if (
        head.release_id not in principal.release_ids
        or head.channel not in principal.channels
        or not set(head.product_ids).intersection(principal.product_ids)
        or not set(head.selling_location_ids).intersection(principal.selling_location_ids)
    ):
        return False
    return all(
        value is None
        or (
            value in head.product_ids
            if key == "product_id"
            else value in head.selling_location_ids
            if key == "selling_location_id"
            else datetime.fromisoformat(value) == head.forecast_origin
            if key == "as_of"
            else value == getattr(head, key)
        )
        for key, value in filters.items()
    )


def _publication_rows(
    connection: Connection[dict[str, Any]], heads: list[ApprovedForecastHead]
) -> dict[str, dict[str, Any]]:
    artifacts = [head.prediction_dataset_id for head in heads]
    summaries = connection.execute(
        "SELECT prediction_dataset_id,count(*) AS count,"
        "sum(octet_length(payload::text)) AS bytes FROM ai_forecast_results "
        "WHERE prediction_dataset_id=ANY(%s) GROUP BY prediction_dataset_id",
        (artifacts,),
    ).fetchall()
    expected = {head.prediction_dataset_id: len(head.rows) for head in heads}
    if {row["prediction_dataset_id"]: row["count"] for row in summaries} != expected:
        _fail("intelligence_head_incomplete")
    if sum(row["bytes"] for row in summaries) > MAX_PUBLICATION_BYTES:
        raise HTTPException(429, detail="intelligence_head_read_budget")
    return {
        row["prediction_id"]: row
        for row in connection.execute(
            "SELECT prediction_id,payload,payload_sha256,received_at FROM ai_forecast_results "
            "WHERE prediction_dataset_id=ANY(%s)",
            (artifacts,),
        ).fetchall()
    }


def verify_head_rows(head: ApprovedForecastHead, records: dict[str, dict[str, Any]]) -> None:
    keys = set()
    for expected in head.rows:
        row = records.get(expected.prediction_id)
        if row is None:
            _fail("intelligence_head_incomplete")
        payload = row["payload"]
        if (
            row["payload_sha256"] != expected.payload_sha256
            or content_hash(payload) != expected.payload_sha256
            or payload["prediction_id"] != expected.prediction_id
            or any(payload[field] != getattr(head, field) for field in BINDING_FIELDS)
            or any(
                datetime.fromisoformat(payload[field]) != getattr(head, field)
                for field in ("forecast_origin", "generated_at", "approval_valid_until")
            )
        ):
            _fail("intelligence_head_binding_invalid")
        validate_event(
            {
                "event_id": str(
                    uuid5(EVENT_NAMESPACE, "forecast_generated:" + expected.prediction_id)
                ),
                "event_type": "forecast_generated",
                "schema_version": "2.0",
                "topic": TOPIC,
                "source": "retailops-ai",
                "correlation_id": payload["inference_run_id"],
                "occurred_at": payload["generated_at"],
                "ingested_at": payload["generated_at"],
                "payload": payload,
            },
            transport_topic=TOPIC,
        )
        key = (payload["product_id"], payload["selling_location_id"], payload["horizon_days"])
        if key in keys:
            _fail("intelligence_head_binding_invalid")
        keys.add(key)
    if keys != {
        (product, location, horizon)
        for product in head.product_ids
        for location in head.selling_location_ids
        for horizon in range(1, head.horizon_days + 1)
    }:
        _fail("intelligence_head_binding_invalid")


def read_active_forecasts(
    principal: IntelligencePrincipal,
    filters: dict[str, str | None],
    *,
    limit: int,
    offset: int,
    view_sha256: str | None,
) -> dict[str, Any]:
    scope = {
        "product_id": principal.product_ids,
        "selling_location_id": principal.selling_location_ids,
        "channel": principal.channels,
        "release_id": principal.release_ids,
    }
    if any(
        filters.get(key) is not None and filters[key] not in allowed
        for key, allowed in scope.items()
    ):
        raise HTTPException(403, detail="intelligence_scope_denied")
    policy = head_policy()
    heads = [head for head in policy.heads if _matches(head, principal, filters)]
    try:
        with get_connection() as connection:
            connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            connection.execute("SET LOCAL statement_timeout='3s'")
            clock = connection.execute("SELECT now() AS now").fetchone()
            if clock is None:
                _fail("intelligence_projection_unavailable")
            now = clock["now"]
            for head in heads:
                if head.reviewed_at > now:
                    _fail("intelligence_head_review_in_future")
                if head.valid_until <= now:
                    _fail("intelligence_head_approval_expired")
            records = _publication_rows(connection, heads)
            for head in heads:
                verify_head_rows(head, records)
            visible = [
                row
                for row in records.values()
                if all(row["payload"][key] in allowed for key, allowed in scope.items())
                and all(
                    filters.get(key) is None or row["payload"][key] == filters[key]
                    for key in ("product_id", "selling_location_id", "channel")
                )
            ]
            visible.sort(
                key=lambda row: (
                    row["payload"]["product_id"],
                    row["payload"]["selling_location_id"],
                    row["payload"]["channel"],
                    row["payload"]["horizon_days"],
                    row["prediction_id"],
                )
            )
            view = content_hash(
                {
                    "selection": "approved_release_as_of_run",
                    "principal": principal.principal_id,
                    "scope": scope,
                    "filters": filters,
                    "policy_sha256": policy.policy_sha256,
                    "prediction_ids": [row["prediction_id"] for row in visible],
                }
            )
            if offset and view_sha256 is None:
                raise HTTPException(409, detail="intelligence_view_required")
            if view_sha256 is not None and view_sha256 != view:
                raise HTTPException(409, detail="intelligence_view_changed")
            items = [read_item(row, now=now) for row in visible[offset : offset + limit]]
    except DatabaseError as exc:
        raise HTTPException(503, detail="intelligence_projection_unavailable") from exc
    except (InvalidRealtimeEventError, ValueError, KeyError, TypeError) as exc:
        raise HTTPException(503, detail="intelligence_head_binding_invalid") from exc
    return {
        "items": items,
        "pagination": {
            "limit": limit,
            "offset": offset,
            "total": len(visible),
            "next_offset": offset + limit if offset + limit < len(visible) else None,
        },
        "view_sha256": view,
        "selection": "approved_release_as_of_run",
        "approval_authority": "private_operator_selection",
        "generated_at": now.isoformat(),
        "data_status": "available" if visible else "no_data",
        "heads": [
            {
                "selection_sha256": head.selection_sha256,
                "release_id": head.release_id,
                "inference_run_id": head.inference_run_id,
                "prediction_dataset_id": head.prediction_dataset_id,
                "as_of": head.forecast_origin.isoformat(),
                "valid_until": head.valid_until.isoformat(),
            }
            for head in heads
        ],
    }
