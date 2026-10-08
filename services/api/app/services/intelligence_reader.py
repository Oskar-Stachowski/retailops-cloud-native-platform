"""Bounded immutable forecast history; page identities bind data, scope and principal."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from fastapi import HTTPException
from psycopg import Error as DatabaseError
from psycopg import sql

from app.db.connection import get_connection
from app.services.intelligence_contract import content_hash

MAX_RESULTS = 2800

if TYPE_CHECKING:
    from app.auth.intelligence import IntelligencePrincipal


def read_forecasts(
    principal: IntelligencePrincipal,
    filters: dict[str, str | None],
    *,
    limit: int,
    offset: int,
    view_sha256: str | None,
) -> dict[str, Any]:
    scope_fields = {
        "product_id": principal.product_ids,
        "selling_location_id": principal.selling_location_ids,
        "channel": principal.channels,
        "release_id": principal.release_ids,
    }
    if any(
        filters.get(field) is not None and filters[field] not in allowed
        for field, allowed in scope_fields.items()
    ):
        raise HTTPException(403, detail="intelligence_scope_denied")
    conditions: list[sql.Composable] = [
        sql.SQL(value)
        for value in (
            "product_id=ANY(%s)",
            "selling_location_id=ANY(%s)",
            "channel=ANY(%s)",
            "release_id=ANY(%s)",
        )
    ]
    params: list[object] = [list(values) for values in scope_fields.values()]
    for field in ("prediction_id", "inference_run_id", *scope_fields):
        if filters.get(field) is not None:
            conditions.append(sql.SQL("{}=%s").format(sql.Identifier(field)))
            params.append(filters[field])
    where = sql.SQL(" AND ").join(conditions)
    try:
        with get_connection() as connection:
            connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            connection.execute("SET LOCAL statement_timeout='3s'")
            now_row = connection.execute("SELECT now() AS now").fetchone()
            if now_row is None:
                msg = "intelligence_database_clock_unavailable"
                raise RuntimeError(msg)
            now = now_row["now"]
            ids = [
                row["prediction_id"]
                for row in connection.execute(
                    sql.SQL(
                        "SELECT prediction_id FROM ai_forecast_results WHERE {} "
                        "ORDER BY forecast_origin DESC,generated_at DESC,prediction_id DESC LIMIT %s"
                    ).format(where),
                    (*params, MAX_RESULTS + 1),
                ).fetchall()
            ]
            if len(ids) > MAX_RESULTS:
                raise HTTPException(429, detail="intelligence_read_budget")
            view = content_hash(
                {
                    "policy": "intelligence-history-v1",
                    "principal": principal.principal_id,
                    "scope": {key: list(value) for key, value in scope_fields.items()},
                    "filters": filters,
                    "prediction_ids": ids,
                }
            )
            if offset and view_sha256 is None:
                raise HTTPException(409, detail="intelligence_view_required")
            if view_sha256 is not None and view_sha256 != view:
                raise HTTPException(409, detail="intelligence_view_changed")
            selected = ids[offset : offset + limit]
            rows = connection.execute(
                "SELECT prediction_id,payload,received_at FROM ai_forecast_results "
                "WHERE prediction_id=ANY(%s)",
                (selected,),
            ).fetchall()
            records = {row["prediction_id"]: row for row in rows}
            items = [read_item(records[identity], now=now) for identity in selected]
    except (DatabaseError, RuntimeError) as exc:
        raise HTTPException(503, detail="intelligence_projection_unavailable") from exc
    return {
        "items": items,
        "pagination": {
            "limit": limit,
            "offset": offset,
            "total": len(ids),
            "next_offset": offset + limit if offset + limit < len(ids) else None,
        },
        "view_sha256": view,
        "selection": "immutable_history",
        "generated_at": now.isoformat(),
        "data_status": "available" if ids else "no_data",
    }


def read_item(row: dict[str, Any], *, now: datetime) -> dict[str, Any]:
    payload = row["payload"]
    origin = datetime.fromisoformat(payload["forecast_origin"])
    approval_end = datetime.fromisoformat(payload["approval_valid_until"])
    freshness = payload["freshness"]
    status = freshness["status"]
    reason = freshness["reason"]
    if approval_end <= now:
        status, reason = "stale", "approval_expired"
    elif (now - origin).total_seconds() > freshness["max_origin_age_seconds"]:
        status, reason = "stale", "origin_age_exceeded"
    return {
        "forecast": payload,
        "source": "retailops-ai",
        "received_at": row["received_at"].isoformat(),
        "freshness": {
            "status": status,
            "reason": reason,
            "evaluated_at": now.astimezone(UTC).isoformat(),
            "policy_id": "intelligence-history-v1",
            "publication_evaluated_at": freshness["evaluated_at"],
        },
    }
