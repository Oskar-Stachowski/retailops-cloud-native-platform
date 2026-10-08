"""Authenticated source reads preserving existing operational resource semantics."""

from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict

from app.api.schemas import (
    ForecastListResponse,
    InventorySnapshotListResponse,
    ProductListResponse,
    SaleListResponse,
    StockRiskListResponse,
)
from app.api.source_queries import (
    ForecastsQuery,
    InventoryQuery,
    ProductsQuery,
    RisksQuery,
    SalesQuery,
)
from app.auth.source_reads import Resource, SourcePrincipal, authorize, verified_principal
from app.services.source_reader import PageQuery, read_page

router = APIRouter(prefix="/integration/v2", tags=["source-integration"])
Principal = Annotated[SourcePrincipal, Depends(verified_principal)]


@lru_cache
def contract_digest() -> str:
    return hashlib.sha256(
        (
            Path(__file__).resolve().parents[1] / "contracts/source-reads-v2/openapi.json"
        ).read_bytes()
    ).hexdigest()


def read_headers(response: Response) -> None:
    response.headers["X-RetailOps-Read-Mode"] = "bounded-live"
    response.headers["X-RetailOps-Snapshot-Supported"] = "false"
    response.headers["X-RetailOps-Source-Contract-Sha256"] = contract_digest()
    response.headers["Cache-Control"] = "no-store"


class SourceCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid")
    contract_version: Literal["retailops-source-reads-2.0"] = "retailops-source-reads-2.0"
    read_mode: Literal["bounded_live"] = "bounded_live"
    immutable_snapshot: Literal[False] = False
    snapshot_replay_handoff: Literal[False] = False
    sales_full_ml_grain: Literal[False] = False
    missing_sales_fields: tuple[
        Literal["store_id", "order_id", "ingested_at", "record_version"], ...
    ] = ("store_id", "order_id", "ingested_at", "record_version")
    warehouse_location_mapping: Literal["not_available"] = "not_available"
    freshness: Literal["unknown_without_completeness_watermark"] = (
        "unknown_without_completeness_watermark"
    )
    legacy_forecast_semantics: Literal["product_period_quantity"] = "product_period_quantity"
    legacy_risk_semantics: Literal["product_heuristic_not_ml_probability"] = (
        "product_heuristic_not_ml_probability"
    )
    max_limit: Literal[100] = 100
    max_period_days: Literal[90] = 90


def checked_page(
    resource: Resource,
    query: PageQuery,
    principal: SourcePrincipal,
    request: Request,
    response: Response,
) -> dict[str, Any]:
    authorize(principal, resource, query.product_id)
    if len(request.query_params) != len(request.query_params.multi_items()):
        raise HTTPException(422, detail="duplicate_query_parameter")
    if isinstance(query, SalesQuery) and query.channel not in principal.channels:
        raise HTTPException(403, detail="source_scope_denied")
    if isinstance(query, InventoryQuery) and query.warehouse_code not in principal.warehouse_codes:
        raise HTTPException(403, detail="source_scope_denied")
    read_headers(response)
    try:
        return read_page(query)
    except (psycopg.Error, RuntimeError) as exc:
        raise HTTPException(503, detail="source_read_unavailable") from exc


@router.get("/capabilities", response_model=SourceCapabilities)
def capabilities(principal: Principal, response: Response) -> SourceCapabilities:
    del principal
    read_headers(response)
    return SourceCapabilities()


@router.get("/snapshot")
def unsupported_snapshot(principal: Principal) -> None:
    del principal
    raise HTTPException(409, detail="source_snapshot_unsupported")


@router.get("/products", response_model=ProductListResponse)
def products(
    query: Annotated[ProductsQuery, Query()],
    principal: Principal,
    request: Request,
    response: Response,
) -> dict[str, Any]:
    return checked_page("products", query, principal, request, response)


@router.get("/sales", response_model=SaleListResponse)
def sales(
    query: Annotated[SalesQuery, Query()],
    principal: Principal,
    request: Request,
    response: Response,
) -> dict[str, Any]:
    return checked_page("sales", query, principal, request, response)


@router.get("/inventory-snapshots", response_model=InventorySnapshotListResponse)
def inventory(
    query: Annotated[InventoryQuery, Query()],
    principal: Principal,
    request: Request,
    response: Response,
) -> dict[str, Any]:
    return checked_page("inventory-snapshots", query, principal, request, response)


@router.get("/forecasts", response_model=ForecastListResponse)
def forecasts(
    query: Annotated[ForecastsQuery, Query()],
    principal: Principal,
    request: Request,
    response: Response,
) -> dict[str, Any]:
    return checked_page("forecasts", query, principal, request, response)


@router.get("/inventory-risks", response_model=StockRiskListResponse)
def risks(
    query: Annotated[RisksQuery, Query()],
    principal: Principal,
    request: Request,
    response: Response,
) -> dict[str, Any]:
    return checked_page("inventory-risks", query, principal, request, response)
