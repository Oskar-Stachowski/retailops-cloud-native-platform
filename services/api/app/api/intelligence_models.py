"""Native anomaly and physical risk resources share scoped personal read authentication."""

from __future__ import annotations

import copy
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from pydantic import BaseModel

from app.auth.intelligence_models import ModelPrincipal, verified_model_principal
from app.services.intelligence_contract import event_validator
from app.services.intelligence_model_reader import read_models

router = APIRouter(prefix="/intelligence/v2", tags=["intelligence-v2-models"])
Principal = Annotated[ModelPrincipal, Depends(verified_model_principal)]
Identifier = Annotated[str | None, Query(min_length=1, max_length=128)]
ViewID = Annotated[str | None, Query(pattern=r"^[0-9a-f]{64}$")]


class ModelProjection(BaseModel):
    result_id: str
    event_type: Literal["anomaly_detected", "stockout_risk_scored"]
    result: dict[str, Any]
    source: Literal["retailops-ai"]
    received_at: str
    freshness: dict[str, Any]


class ModelHistory(BaseModel):
    items: list[ModelProjection]
    pagination: dict[str, int | None]
    view_sha256: str
    selection: Literal["immutable_history"]
    generated_at: str
    data_status: Literal["available", "no_data"]


def query_allowed(request: Request, allowed: set[str]) -> None:
    if set(request.query_params) - allowed or any(
        len(request.query_params.getlist(key)) != 1 for key in request.query_params
    ):
        raise HTTPException(422, detail="intelligence_query_unknown_or_repeated")


@router.get("/anomalies", response_model=ModelHistory)
def list_anomalies(
    request: Request,
    principal: Principal,
    product_id: Identifier = None,
    selling_location_id: Identifier = None,
    channel: Annotated[
        Literal["store", "online", "marketplace", "wholesale"] | None, Query()
    ] = None,
    currency: Annotated[Literal["PLN", "EUR"] | None, Query()] = None,
    release_id: Identifier = None,
    inference_run_id: Identifier = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=10000)] = 0,
    view_sha256: ViewID = None,
) -> dict[str, Any]:
    filters = {
        "product_id": product_id,
        "selling_location_id": selling_location_id,
        "channel": channel,
        "currency": currency,
        "release_id": release_id,
        "inference_run_id": inference_run_id,
    }
    query_allowed(request, {*filters, "limit", "offset", "view_sha256"})
    return read_models(
        principal, "anomaly_detected", filters, limit=limit, offset=offset, view_sha256=view_sha256
    )


@router.get("/stockout-risks", response_model=ModelHistory)
def list_stockout_risks(
    request: Request,
    principal: Principal,
    product_id: Identifier = None,
    stock_location_id: Identifier = None,
    release_id: Identifier = None,
    inference_run_id: Identifier = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=10000)] = 0,
    view_sha256: ViewID = None,
) -> dict[str, Any]:
    filters = {
        "product_id": product_id,
        "stock_location_id": stock_location_id,
        "release_id": release_id,
        "inference_run_id": inference_run_id,
    }
    query_allowed(request, {*filters, "limit", "offset", "view_sha256"})
    return read_models(
        principal,
        "stockout_risk_scored",
        filters,
        limit=limit,
        offset=offset,
        view_sha256=view_sha256,
    )


def model_detail(
    request: Request, principal: ModelPrincipal, kind: str, result_id: str
) -> dict[str, Any]:
    query_allowed(request, set())
    page = read_models(
        principal, kind, {"result_id": result_id}, limit=1, offset=0, view_sha256=None
    )
    if not page["items"]:
        raise HTTPException(404, detail="intelligence_model_result_not_found")
    return page["items"][0]


@router.get("/anomalies/{anomaly_id}", response_model=ModelProjection)
def get_anomaly(
    request: Request,
    principal: Principal,
    anomaly_id: Annotated[str, Path(pattern=r"^anomaly-sha256-[0-9a-f]{64}$")],
) -> dict[str, Any]:
    return model_detail(request, principal, "anomaly_detected", anomaly_id)


@router.get("/stockout-risks/{risk_id}", response_model=ModelProjection)
def get_stockout_risk(
    request: Request,
    principal: Principal,
    risk_id: Annotated[str, Path(pattern=r"^risk-sha256-[0-9a-f]{64}$")],
) -> dict[str, Any]:
    return model_detail(request, principal, "stockout_risk_scored", risk_id)


def add_payload_openapi(schema: dict[str, Any]) -> None:
    variants = []
    for kind, prefix, owner in (
        ("anomaly_detected", "AI10_ANOMALY_", "Item"),
        ("stockout_risk_scored", "AI10_STOCKOUT_", "RiskItem"),
    ):
        definitions = copy.deepcopy(event_validator(kind).schema["$defs"])

        def relocate(value: object, prefix: str = prefix) -> None:
            if isinstance(value, dict):
                if "$ref" in value:
                    value["$ref"] = value["$ref"].replace(
                        "#/$defs/", "#/components/schemas/" + prefix
                    )
                for child in value.values():
                    relocate(child)
            elif isinstance(value, list):
                for child in value:
                    relocate(child)

        relocate(definitions)
        schema["components"]["schemas"].update(
            {prefix + name: value for name, value in definitions.items()}
        )
        variants.append({"$ref": "#/components/schemas/" + prefix + owner})
    schema["components"]["schemas"]["ModelProjection"]["properties"]["result"] = {"oneOf": variants}
