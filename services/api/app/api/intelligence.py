"""AI projections have a separate resource and explicitly authenticated access."""

from __future__ import annotations

import copy
from datetime import datetime, timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from pydantic import BaseModel

from app.auth.intelligence import IntelligencePrincipal, verified_principal
from app.services.intelligence_contract import event_validator
from app.services.intelligence_head import read_active_forecasts
from app.services.intelligence_reader import read_forecasts

router = APIRouter(prefix="/intelligence/v2/forecasts", tags=["intelligence-v2"])
Principal = Annotated[IntelligencePrincipal, Depends(verified_principal)]
Identifier = Annotated[str | None, Query(min_length=1, max_length=128)]
ViewID = Annotated[str | None, Query(pattern=r"^[0-9a-f]{64}$")]


class ForecastProjection(BaseModel):
    forecast: dict[str, Any]
    source: Literal["retailops-ai"]
    received_at: str
    freshness: dict[str, Any]


class ForecastPage(BaseModel):
    items: list[ForecastProjection]
    pagination: dict[str, int | None]
    view_sha256: str
    generated_at: str
    data_status: Literal["available", "no_data"]


class ForecastHistory(ForecastPage):
    selection: Literal["immutable_history"]


class ForecastActive(ForecastPage):
    selection: Literal["approved_release_as_of_run"]
    approval_authority: Literal["private_operator_selection"]
    heads: list[dict[str, str]]


@router.get("/active", response_model=ForecastActive)
def active_forecasts(
    request: Request,
    principal: Principal,
    product_id: Identifier = None,
    selling_location_id: Identifier = None,
    channel: Annotated[Literal["store", "online"] | None, Query()] = None,
    release_id: Identifier = None,
    inference_run_id: Identifier = None,
    as_of: Annotated[datetime | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=2800)] = 0,
    view_sha256: ViewID = None,
) -> dict[str, Any]:
    allowed = {
        "product_id",
        "selling_location_id",
        "channel",
        "release_id",
        "inference_run_id",
        "as_of",
        "limit",
        "offset",
        "view_sha256",
    }
    if set(request.query_params) - allowed or any(
        len(request.query_params.getlist(key)) != 1 for key in request.query_params
    ):
        raise HTTPException(422, detail="intelligence_query_unknown_or_repeated")
    if as_of is not None and (as_of.tzinfo is None or as_of.utcoffset() != timedelta(0)):
        raise HTTPException(422, detail="intelligence_as_of_requires_utc")
    return read_active_forecasts(
        principal,
        {
            "product_id": product_id,
            "selling_location_id": selling_location_id,
            "channel": channel,
            "release_id": release_id,
            "inference_run_id": inference_run_id,
            "as_of": as_of.isoformat() if as_of is not None else None,
        },
        limit=limit,
        offset=offset,
        view_sha256=view_sha256,
    )


@router.get("", response_model=ForecastHistory)
def list_forecasts(
    request: Request,
    principal: Principal,
    product_id: Identifier = None,
    selling_location_id: Identifier = None,
    channel: Annotated[Literal["store", "online"] | None, Query()] = None,
    inference_run_id: Identifier = None,
    release_id: Identifier = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=2800)] = 0,
    view_sha256: ViewID = None,
) -> dict[str, Any]:
    allowed = {
        "product_id",
        "selling_location_id",
        "channel",
        "inference_run_id",
        "release_id",
        "limit",
        "offset",
        "view_sha256",
    }
    if set(request.query_params) - allowed:
        raise HTTPException(422, detail="intelligence_query_unknown")
    return read_forecasts(
        principal,
        {
            "product_id": product_id,
            "selling_location_id": selling_location_id,
            "channel": channel,
            "inference_run_id": inference_run_id,
            "release_id": release_id,
        },
        limit=limit,
        offset=offset,
        view_sha256=view_sha256,
    )


@router.get("/{prediction_id}", response_model=ForecastProjection)
def get_forecast(
    request: Request,
    principal: Principal,
    prediction_id: Annotated[str, Path(pattern=r"^prediction-sha256-[0-9a-f]{64}$")],
) -> dict[str, Any]:
    if request.query_params:
        raise HTTPException(422, detail="intelligence_query_unknown")
    result = read_forecasts(
        principal, {"prediction_id": prediction_id}, limit=1, offset=0, view_sha256=None
    )
    if not result["items"]:
        raise HTTPException(404, detail="intelligence_forecast_not_found")
    return result["items"][0]


def add_payload_openapi(schema: dict[str, Any]) -> None:
    """Expose the exact generated ML payload definitions in OpenAPI, without field copies."""
    definitions = copy.deepcopy(event_validator().schema["$defs"])

    def relocate(value: object) -> None:
        if isinstance(value, dict):
            if "$ref" in value:
                value["$ref"] = value["$ref"].replace("#/$defs/", "#/components/schemas/AI10_")
            for child in value.values():
                relocate(child)
        elif isinstance(value, list):
            for child in value:
                relocate(child)

    relocate(definitions)
    schema["components"]["schemas"].update(
        {"AI10_" + name: document for name, document in definitions.items()}
    )
    schema["components"]["schemas"]["ForecastProjection"]["properties"]["forecast"] = {
        "$ref": "#/components/schemas/AI10_V12ForecastItem",
    }
