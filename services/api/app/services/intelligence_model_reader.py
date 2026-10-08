"""Scoped immutable native model history; delivery order cannot replace a newer result."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from fastapi import HTTPException
from jsonschema import ValidationError
from psycopg import Error as DatabaseError
from psycopg import sql

from app.db.connection import get_connection
from app.services.intelligence_contract import content_hash
from app.services.intelligence_model_contract import validate_model_payload

if TYPE_CHECKING:
    from app.auth.intelligence_models import ModelPrincipal

MAX_RESULTS = 10000


def model_scope(principal: ModelPrincipal, kind: str) -> dict[str, tuple[str, ...]]:
    if (
        kind == "anomaly_detected"
        and "anomaly:read" in principal.capabilities
        and principal.anomaly_scope
    ):
        grant = principal.anomaly_scope
        return {
            "product_id": grant.product_ids,
            "selling_location_id": grant.selling_location_ids,
            "channel": grant.channels,
            "currency": grant.currencies,
            "release_id": grant.release_ids,
        }
    if (
        kind == "stockout_risk_scored"
        and "stockout:read" in principal.capabilities
        and principal.stockout_scope
    ):
        physical = principal.stockout_scope
        return {
            "product_id": physical.product_ids,
            "stock_location_id": physical.stock_location_ids,
            "release_id": physical.release_ids,
        }
    raise HTTPException(403, detail="intelligence_model_scope_denied")


def read_models(
    principal: ModelPrincipal,
    kind: str,
    filters: dict[str, str | None],
    *,
    limit: int,
    offset: int,
    view_sha256: str | None,
) -> dict[str, Any]:
    scope = model_scope(principal, kind)
    if set(filters) - {*scope, "inference_run_id", "result_id"}:
        raise HTTPException(422, detail="intelligence_query_unknown")
    if any(
        filters.get(field) is not None and filters[field] not in grant
        for field, grant in scope.items()
    ):
        raise HTTPException(403, detail="intelligence_model_scope_denied")
    conditions: list[sql.Composable] = [sql.SQL("event_type=%s")]
    params: list[object] = [kind]
    for field, allowed in scope.items():
        conditions.append(sql.SQL("{}=ANY(%s)").format(sql.Identifier(field)))
        params.append(list(allowed))
    for field, value in filters.items():
        if value is not None:
            conditions.append(sql.SQL("{}=%s").format(sql.Identifier(field)))
            params.append(value)
    where = sql.SQL(" AND ").join(conditions)
    try:
        with get_connection() as connection:
            connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            connection.execute("SET LOCAL statement_timeout='3s'")
            clock = connection.execute("SELECT now() AS now").fetchone()
            if clock is None:
                msg = "intelligence_database_clock_unavailable"
                raise RuntimeError(msg)
            now = clock["now"]
            census = connection.execute(
                sql.SQL(
                    "SELECT result_id,payload_sha256 FROM ai_model_results WHERE {} "
                    "ORDER BY as_of DESC,generated_at DESC,result_id DESC LIMIT %s"
                ).format(where),
                (*params, MAX_RESULTS + 1),
            ).fetchall()
            if len(census) > MAX_RESULTS:
                raise HTTPException(429, detail="intelligence_read_budget")
            view = content_hash(
                {
                    "policy": "model-intelligence-history-v1",
                    "principal": principal.principal_id,
                    "scope": {field: list(grant) for field, grant in scope.items()},
                    "event_type": kind,
                    "filters": filters,
                    "results": census,
                }
            )
            if offset and view_sha256 is None:
                raise HTTPException(409, detail="intelligence_view_required")
            if view_sha256 is not None and view_sha256 != view:
                raise HTTPException(409, detail="intelligence_view_changed")
            selected = [row["result_id"] for row in census[offset : offset + limit]]
            rows = connection.execute(
                "SELECT result_id,event_type,payload,payload_sha256,received_at "
                "FROM ai_model_results WHERE result_id=ANY(%s)",
                (selected,),
            ).fetchall()
            indexed = {row["result_id"]: row for row in rows}
            items = [read_model_item(indexed[identity], now=now) for identity in selected]
    except (DatabaseError, RuntimeError, ValueError, KeyError, ValidationError) as exc:
        raise HTTPException(503, detail="intelligence_model_projection_unavailable") from exc
    return {
        "items": items,
        "pagination": {
            "limit": limit,
            "offset": offset,
            "total": len(census),
            "next_offset": offset + limit if offset + limit < len(census) else None,
        },
        "view_sha256": view,
        "selection": "immutable_history",
        "generated_at": now.isoformat(),
        "data_status": "available" if census else "no_data",
    }


def read_model_item(row: dict[str, Any], *, now: datetime) -> dict[str, Any]:
    kind, item = row["event_type"], row["payload"]
    native_id = item["anomaly_id"] if kind == "anomaly_detected" else item["risk_id"]
    if row["result_id"] != native_id or row["payload_sha256"] != content_hash(item):
        msg = "intelligence_model_stored_binding"
        raise ValueError(msg)
    validate_model_payload(kind, item)
    origin = datetime.fromisoformat(
        item["scoring_origin"] if kind == "anomaly_detected" else item["as_of"]
    )
    max_age = 7 * 86400 if kind == "anomaly_detected" else 86400
    age = (now - origin).total_seconds()
    status = item["freshness_status"]
    reason = "publication_status"
    if age < 0 or datetime.fromisoformat(item["generated_at"]) > now:
        status, reason = "unknown", "publication_from_future"
    elif age > max_age:
        status, reason = "stale", "origin_age_exceeded"
    return {
        "result_id": row["result_id"],
        "event_type": kind,
        "result": item,
        "source": "retailops-ai",
        "received_at": row["received_at"].isoformat(),
        "freshness": {
            "status": status,
            "reason": reason,
            "evaluated_at": now.isoformat(),
            "publication_status": item["freshness_status"],
            "max_origin_age_seconds": max_age,
            "origin_age_seconds": max(0, age),
        },
    }
