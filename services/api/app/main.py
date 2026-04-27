from fastapi import FastAPI
from app.api.health import router as health_router

app = FastAPI(
    title="RetailOps API",
    version="0.1.0",
    description="First FastAPI service for the RetailOps platform."
)

app.include_router(health_router)