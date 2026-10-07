"""Bounded personal reads; expiry is evaluated against the database clock on each request."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from fastapi import HTTPException
from psycopg import Error as DatabaseError
from psycopg import sql

from app.db.connection import get_connection
from app.services.intelligence_contract import content_hash
from app.services.intelligence_suggestion_contract import payload_validator, validate_payload

if TYPE_CHECKING:
    from app.auth.intelligence_suggestions import SuggestionPrincipal

MAX_RESULTS = 500
MAX_VIEW_BYTES = 8 * 1024 * 1024


def read_suggestions(
    principal: SuggestionPrincipal,
    filters: dict[str, str | None],
    *,
    selection: str,
    limit: int,
    offset: int,
    view_sha256: str | None,
) -> dict[str, Any]:
    scope = {
        "product_id": principal.product_ids,
        "selling_location_id": principal.selling_location_ids,
        "channel": principal.channels,
        "policy_sha256": principal.policy_sha256s,
        "agent_config_version": principal.agent_config_versions,
    }
    if any(
        filters.get(key) is not None and filters[key] not in allowed
        for key, allowed in scope.items()
    ):
        raise HTTPException(403, detail="suggestion_scope_denied")
    conditions: list[sql.Composable] = [
        sql.SQL("{}=ANY(%s)").format(sql.Identifier(key)) for key in scope
    ]
    params: list[object] = [list(values) for values in scope.values()]
    # Every model reference must be granted, including multi-model suggestions.
    conditions.append(sql.SQL("(payload->'model_release_refs') <@ to_jsonb(%s::text[])"))
    params.append(list(principal.model_release_refs))
    for field in ("recommendation_id", "trace_id", *scope):
        if filters.get(field) is not None:
            conditions.append(sql.SQL("{}=%s").format(sql.Identifier(field)))
            params.append(filters[field])
    if selection == "current":
        conditions.append(sql.SQL("created_at <= now() AND now() < expires_at"))
    where = sql.SQL(" AND ").join(conditions)
    try:
        with get_connection() as connection:
            connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            connection.execute("SET LOCAL statement_timeout='3s'")
            clock = connection.execute("SELECT now() AS now").fetchone()
            if clock is None:
                msg = "suggestion_database_clock_unavailable"
                raise RuntimeError(msg)
            now = clock["now"]
            identities = connection.execute(
                sql.SQL("""SELECT recommendation_id,payload_sha256,octet_length(payload::text) AS bytes
                FROM ai_recommendation_results WHERE {}
                ORDER BY created_at DESC,recommendation_id DESC LIMIT %s""").format(where),
                (*params, MAX_RESULTS + 1),
            ).fetchall()
            if (
                len(identities) > MAX_RESULTS
                or sum(row["bytes"] for row in identities) > MAX_VIEW_BYTES
            ):
                raise HTTPException(429, detail="suggestion_read_budget")
            ids = [str(row["recommendation_id"]) for row in identities]
            view = content_hash(
                {
                    "reader": "suggestion-read-v1",
                    "principal": principal.principal_id,
                    "scope": {key: list(values) for key, values in scope.items()},
                    "model_release_refs": list(principal.model_release_refs),
                    "selection": selection,
                    "filters": filters,
                    "results": [
                        (identity, row["payload_sha256"])
                        for identity, row in zip(ids, identities, strict=True)
                    ],
                }
            )
            if offset and view_sha256 is None:
                raise HTTPException(409, detail="suggestion_view_required")
            if view_sha256 is not None and view_sha256 != view:
                raise HTTPException(409, detail="suggestion_view_changed")
            selected = ids[offset : offset + limit]
            rows = connection.execute(
                "SELECT recommendation_id,payload,payload_sha256,received_at FROM ai_recommendation_results "
                "WHERE recommendation_id=ANY(%s::uuid[])",
                (selected,),
            ).fetchall()
            records = {str(row["recommendation_id"]): row for row in rows}
            items = [read_suggestion(records[identity], now=now) for identity in selected]
    except (DatabaseError, RuntimeError, ValueError, KeyError, TypeError) as exc:
        raise HTTPException(503, detail="suggestion_projection_unavailable") from exc
    return {
        "items": items,
        "pagination": {
            "limit": limit,
            "offset": offset,
            "total": len(ids),
            "next_offset": offset + limit if offset + limit < len(ids) else None,
        },
        "selection": selection,
        "view_sha256": view,
        "generated_at": now.isoformat(),
        "data_status": "available" if ids else "no_data",
        "execution_authorized": False,
    }


def read_suggestion(row: dict[str, Any], *, now: datetime) -> dict[str, Any]:
    payload = row["payload"]
    validator = payload_validator()
    if (
        content_hash(payload) != row["payload_sha256"]
        or str(row["recommendation_id"]) != payload["recommendation_id"]
        or next(validator.iter_errors(payload), None) is not None
    ):
        msg = "suggestion_projection_corrupt"
        raise ValueError(msg)
    validate_payload(payload)
    expires, created = (
        datetime.fromisoformat(payload[key]) for key in ("expires_at", "created_at")
    )
    status, reason = "current", "within_upstream_lifetime"
    if now >= expires:
        status, reason = "stale", "suggestion_expired"
    elif now < created:
        status, reason = "unknown", "publication_in_future"
    return {
        "suggestion": payload,
        "source": "retailops-ai",
        "received_at": row["received_at"].isoformat(),
        "execution_authorized": False,
        "freshness": {
            "status": status,
            "reason": reason,
            "evaluated_at": now.astimezone(UTC).isoformat(),
            "policy_id": "suggestion-read-v1",
            "valid_until": payload["expires_at"],
        },
    }
