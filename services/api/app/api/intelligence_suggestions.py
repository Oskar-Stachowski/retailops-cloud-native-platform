"""Personal, read-only AI suggestions; no demo principal or operational mutation route."""

from __future__ import annotations

import copy
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from pydantic import BaseModel

from app.auth.intelligence_suggestions import SuggestionPrincipal, verified_suggestion_principal
from app.services.intelligence_suggestion_contract import suggestion_validator
from app.services.intelligence_suggestion_reader import read_suggestions

router = APIRouter(prefix="/intelligence/v2/recommendations", tags=["intelligence-v2"])
Principal = Annotated[SuggestionPrincipal, Depends(verified_suggestion_principal)]
Identifier = Annotated[str | None, Query(min_length=1, max_length=128)]
CanonicalUUID = r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"


class SuggestionProjection(BaseModel):
    suggestion: dict[str, Any]
    source: Literal["retailops-ai"]
    received_at: str
    freshness: dict[str, Any]
    execution_authorized: Literal[False]


class SuggestionPage(BaseModel):
    items: list[SuggestionProjection]
    pagination: dict[str, int | None]
    selection: Literal["current", "immutable_history"]
    view_sha256: str
    generated_at: str
    data_status: Literal["available", "no_data"]
    execution_authorized: Literal[False]


@router.get("", response_model=SuggestionPage)
def list_suggestions(
    request: Request,
    principal: Principal,
    product_id: Identifier = None,
    selling_location_id: Identifier = None,
    channel: Annotated[Literal["store", "online"] | None, Query()] = None,
    trace_id: Annotated[str | None, Query(pattern=CanonicalUUID)] = None,
    selection: Annotated[Literal["current", "immutable_history"], Query()] = "current",
    limit: Annotated[int, Query(ge=1, le=50)] = 50,
    offset: Annotated[int, Query(ge=0, le=500)] = 0,
    view_sha256: Annotated[str | None, Query(pattern=r"^[0-9a-f]{64}$")] = None,
) -> dict[str, Any]:
    allowed = {
        "product_id",
        "selling_location_id",
        "channel",
        "trace_id",
        "selection",
        "limit",
        "offset",
        "view_sha256",
    }
    reject_query(request, allowed)
    return read_suggestions(
        principal,
        {
            "product_id": product_id,
            "selling_location_id": selling_location_id,
            "channel": channel,
            "trace_id": trace_id,
        },
        selection=selection,
        limit=limit,
        offset=offset,
        view_sha256=view_sha256,
    )


@router.get("/{recommendation_id}", response_model=SuggestionProjection)
def get_suggestion(
    request: Request,
    principal: Principal,
    recommendation_id: Annotated[str, Path(pattern=CanonicalUUID)],
) -> dict[str, Any]:
    reject_query(request, set())
    result = read_suggestions(
        principal,
        {"recommendation_id": recommendation_id},
        selection="immutable_history",
        limit=1,
        offset=0,
        view_sha256=None,
    )
    if not result["items"]:
        raise HTTPException(404, detail="suggestion_not_found")
    return result["items"][0]


def reject_query(request: Request, allowed: set[str]) -> None:
    if set(request.query_params) - allowed or any(
        len(request.query_params.getlist(key)) != 1 for key in request.query_params
    ):
        raise HTTPException(422, detail="suggestion_query_unknown_or_repeated")


def add_payload_openapi(schema: dict[str, Any]) -> None:
    schema["components"]["schemas"]["AI12_PersistedSuggestion"] = copy.deepcopy(
        suggestion_validator().schema["properties"]["payload"]
    )
    schema["components"]["schemas"]["SuggestionProjection"]["properties"]["suggestion"] = {
        "$ref": "#/components/schemas/AI12_PersistedSuggestion"
    }
