from fastapi import APIRouter, status
from pydantic import BaseModel, Field
import os

router = APIRouter(tags=["health"])

class HealthResponse(BaseModel):
    status: str = Field(example="ok")
    service: str = Field(example="retailops-api")
    environment: str = Field(example="local")

@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Health check",
    description="Returns basic service health information for local checks, Docker health checks, CI validation and future Kubernetes probes.",
)
def health_check() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="retailops-api",
        environment=os.getenv("APP_ENV", "local"),
    )