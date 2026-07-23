import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

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


app = FastAPI(title="CheatSheet", version="0.1.0", lifespan=lifespan)
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
