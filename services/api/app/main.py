from fastapi import FastAPI

from app.api import analytics, dashboard, forecasts, products
from app.api.health import router as health_router
from app.api.errors import register_exception_handlers

app = FastAPI(
    title="RetailOps API",
    description="Backend API for the RetailOps cloud-native AI platform.",
    version="0.1.0",
    docs_url="/docs",
    openapi_url="/openapi.json"
)

register_exception_handlers(app)

app.include_router(health_router)
app.include_router(dashboard.router)
app.include_router(analytics.router)
app.include_router(products.router)
app.include_router(forecasts.router)
