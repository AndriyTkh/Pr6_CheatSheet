"""HTTP surface. The OpenAPI spec generated from here is what Role 5 types against.

Grid routes (rows, columns, cells, the grid payload) all live under
`/sheets/{sheet_id}/…`. A case has ≥1 sheet (§2a); putting the scope in the path
is what makes "which grid" unanswerable by accident.
"""

from fastapi import APIRouter

from app.api.routes import (
    cases,
    cells,
    columns,
    documents,
    health,
    reconcile,
    recipes,
    rows,
    runs,
    sheets,
)
from app.realtime.routes import router as realtime_router

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(cases.router)
api_router.include_router(sheets.router)
api_router.include_router(rows.router)
api_router.include_router(columns.router)
api_router.include_router(cells.router)
api_router.include_router(recipes.router)
api_router.include_router(runs.router)
api_router.include_router(documents.router)
api_router.include_router(realtime_router)
api_router.include_router(reconcile.router)

__all__ = ["api_router"]
