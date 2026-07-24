"""The one queue — Procrastinate over Postgres `LISTEN/NOTIFY` + `SKIP LOCKED`.

§4's closing paragraph is the whole design of this module: Procrastinate *is*
the queue, so nothing else in the app may lock. `cell.status` is data/display
(`blocked → pending → running → <terminal>`); the row lock that decides which
worker gets a job lives in `procrastinate_jobs`, a table this app never reads.
A poller over `cell.status` would be a second queue fighting the real one.

The connector is built lazily. Importing `app.tasks` must not open a socket —
the pure test suite imports it, and the FastAPI process only opens the pool
when it actually defers something (`open_async`).

Schema: `python scripts/apply_queue_schema.py` (see that file — Procrastinate
brings its own tables and is not one of our numbered migrations).
"""

from __future__ import annotations

import asyncio
import sys

import procrastinate

from app.core.config import settings

#: Tasks live in `app.tasks.cells`; a worker started from the CLI imports it
#: through this list rather than relying on someone having imported it first.
IMPORT_PATHS = ["app.tasks.cells"]


def use_selector_event_loop() -> None:
    """Windows only: psycopg's async stack does not work on `ProactorEventLoop`.

    The default policy on Windows gives a proactor loop, and psycopg's async
    connection silently never completes on it — the pool just times out after
    30s, which reads as "Postgres is unreachable" rather than "wrong loop".
    Call this before `asyncio.run()` in any process that opens the queue: the
    worker entrypoint, the schema script, the tests.

    No-op everywhere else, so it is safe to call unconditionally.
    """
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def queue_dsn(database_url: str | None = None) -> str:
    """SQLAlchemy's `+asyncpg` URL → the plain DSN psycopg wants.

    One URL configures both halves of the app: the ORM talks asyncpg, the queue
    talks psycopg, and a second env var for the same database is a way to point
    them at different ones by accident.
    """
    url = database_url or settings.database_url
    return url.replace("postgresql+asyncpg://", "postgresql://")


def build_connector(database_url: str | None = None) -> procrastinate.PsycopgConnector:
    return procrastinate.PsycopgConnector(conninfo=queue_dsn(database_url))


def build_app(database_url: str | None = None) -> procrastinate.App:
    """A fresh app on a given database — used by tests and the schema script."""
    return procrastinate.App(
        connector=build_connector(database_url), import_paths=IMPORT_PATHS
    )


#: The process-wide app. Tasks register against it at import time; the pool is
#: opened by whoever runs it (`app.open_async()` / the worker CLI).
procrastinate_app = build_app()
