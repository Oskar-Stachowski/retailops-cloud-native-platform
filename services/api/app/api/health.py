from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.api.errors import error_response
from app.core.config import get_settings
from app.db.connection import check_database_connection


router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str = Field(json_schema_extra={"example": "ok"})
    service: str = Field(json_schema_extra={"example": "retailops-api"})
    environment: str = Field(json_schema_extra={"example": "local"})


class ReadinessResponse(BaseModel):
    status: str = Field(json_schema_extra={"example": "ok"})
    service: str = Field(json_schema_extra={"example": "retailops-api"})
    environment: str = Field(json_schema_extra={"example": "local"})
    database: str = Field(json_schema_extra={"example": "ok"})


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Health check",
    description=(
        "Returns basic service health information for local checks, "
        "Docker health checks, CI validation and future Kubernetes probes."
    ),
)
def health_check() -> HealthResponse:
    settings = get_settings()

    return HealthResponse(
        status="ok",
        service="retailops-api",
        environment=settings.app_env,
    )


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    status_code=status.HTTP_200_OK,
    summary="Readiness check",
    description=(
        "Returns service readiness information, "
        "including database connectivity."
    ),
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Database is not available",
        }
    },
)
def readiness_check() -> ReadinessResponse | JSONResponse:
    settings = get_settings()

    if not check_database_connection():
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=error_response(
                code="database_unavailable",
                message="Database is not available.",
            ),
        )

    return ReadinessResponse(
        status="ok",
        service="retailops-api",
        environment=settings.app_env,
        database="ok",
    )
