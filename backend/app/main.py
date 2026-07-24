import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.routing import APIRoute

from app.api.routes import api_router
from app.dag.errors import EdgeRejected
from app.db.session import engine
from app.realtime.listener import run_listener

# Import for the side effect of registering every mapper before the first query.
import app.models  # noqa: F401

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown — DB engine connects on first request via get_db().

    One `cheatsheet_cell` LISTEN per web process feeds the SSE broker (§4 step 7).
    It self-reconnects, so a DB that is down at boot doesn't stop the app coming
    up; it attaches once Postgres is reachable.
    """
    listener = asyncio.create_task(run_listener(), name="cell-listener")
    try:
        yield
    finally:
        listener.cancel()
        try:
            await listener
        except asyncio.CancelledError:
            pass
        await engine.dispose()


def operation_id(route: APIRoute) -> str:
    """The handler's function name, used verbatim as the OpenAPI `operationId`.

    FastAPI's default concatenates path and method, so `openapi-typescript`
    would emit `list_rows_sheets__sheet_id__rows_get`. The function name is the
    readable one, and it keeps a path change from renaming a frontend symbol
    (tech-stack-decision.md, "Shared FE/BE types").
    """
    return route.name


app = FastAPI(
    title="CheatSheet",
    version="0.1.0",
    lifespan=lifespan,
    generate_unique_id_function=operation_id,
)
app.include_router(api_router)


@app.exception_handler(EdgeRejected)
async def edge_rejected_handler(request, exc: EdgeRejected):
    """§4 step 2 — a rejected add-column action, surfaced with its own message.

    422 rather than 500: the composition is invalid, nothing failed. The message
    is journalist-facing (the list gate's names the column and offers the two
    Expand modes), so it is passed through verbatim.
    """
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=422,
        content={"detail": exc.message, "reason": type(exc).__name__},
    )
