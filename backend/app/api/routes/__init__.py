"""HTTP surface. The OpenAPI spec generated from here is what Role 5 types against."""

from fastapi import APIRouter

from app.api.routes import health, reconcile
from app.realtime.routes import router as realtime_router

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(realtime_router)
api_router.include_router(reconcile.router)

__all__ = ["api_router"]
