"""Bridge the Postgres `cheatsheet_cell` NOTIFY into the in-process broker (§4 step 7).

The wavefront's `publish_cell_terminal()` emits `pg_notify('cheatsheet_cell',
{"row_id":…,"column_id":…})` on every terminal write, from whatever worker ran the
cell. This loop is the one `LISTEN` per web process that turns those notifications
into `CellUpdate`s on the broker.

The payload is deliberately tiny (8000-byte NOTIFY limit, and a body written by one
worker would be stale by the time another reads it — wavefront handoff). So the
listener does **not** trust it: it re-reads the cell for the authoritative
`version`, `status`, and the owning `case_id`, and only then publishes. A NOTIFY for
a case nobody is watching is dropped before the read — no query for a cell no open
connection cares about.

Best-effort and self-healing: a dropped connection is logged and reconnected. A
missed notification is never a lost cell — the reconcile endpoint replays anything
the live stream skipped, keyed on the same monotonic version.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid

import asyncpg
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory
from app.models import Cell, Row
from app.models.enums import TERMINAL
from app.realtime.broker import Broker, broker
from app.realtime.events import CellUpdate
from app.services.wavefront import CELL_CHANNEL

logger = logging.getLogger(__name__)

#: Backoff between reconnect attempts when the LISTEN connection drops.
RECONNECT_DELAY_SECONDS = 2.0


def _listen_dsn(database_url: str) -> str:
    """SQLAlchemy's `+asyncpg` URL → the plain DSN `asyncpg.connect` wants."""
    return database_url.replace("postgresql+asyncpg://", "postgresql://")


async def _resolve_update(
    session: AsyncSession, row_id: uuid.UUID, column_id: uuid.UUID
) -> CellUpdate | None:
    """Re-read the notified cell into a `CellUpdate`, or `None` to drop it.

    Dropped when: the cell vanished (row/column deleted between NOTIFY and read),
    the owning row vanished, or the status is non-terminal — the stream only
    carries terminal cells, and a `running` NOTIFY should never have fired, but
    the read is the authority, not the payload.
    """
    cell = await session.get(Cell, (row_id, column_id))
    if cell is None or cell.status not in TERMINAL:
        return None
    case_id = await session.scalar(select(Row.case_id).where(Row.id == row_id))
    if case_id is None:
        return None
    return CellUpdate(
        case_id=case_id,
        row_id=row_id,
        column_id=column_id,
        version=cell.version,
        status=cell.status.value,
    )


async def _handle_payload(payload: str, target: Broker) -> None:
    """Parse one NOTIFY body, re-read the cell, publish it if anyone is watching."""
    try:
        body = json.loads(payload)
        row_id = uuid.UUID(body["row_id"])
        column_id = uuid.UUID(body["column_id"])
    except (ValueError, KeyError, TypeError) as exc:
        logger.warning("unparseable %s payload %r: %s", CELL_CHANNEL, payload, exc)
        return

    async with async_session_factory() as session:
        update = await _resolve_update(session, row_id, column_id)
    if update is None:
        return
    if target.subscriber_count(update.case_id) == 0:
        return
    target.publish(update)


async def run_listener(target: Broker = broker, *, database_url: str | None = None) -> None:
    """LISTEN on `cheatsheet_cell` forever, reconnecting on failure.

    Started once per web process from the FastAPI lifespan. Runs until cancelled
    (app shutdown); every other exit is a dropped connection it retries.
    """
    from app.core.config import settings

    dsn = _listen_dsn(database_url or settings.database_url)
    queue: asyncio.Queue[str] = asyncio.Queue()

    while True:
        try:
            conn = await asyncpg.connect(dsn)
        except Exception as exc:  # noqa: BLE001 — retry a down DB, don't crash the app
            logger.warning("cell listener could not connect: %s", exc)
            await asyncio.sleep(RECONNECT_DELAY_SECONDS)
            continue

        # asyncpg's callback is sync; hand the payload to the async drain loop.
        await conn.add_listener(
            CELL_CHANNEL, lambda _c, _pid, _ch, payload: queue.put_nowait(payload)
        )
        logger.info("cell listener attached to %s", CELL_CHANNEL)
        try:
            while True:
                payload = await queue.get()
                await _handle_payload(payload, target)
        except asyncio.CancelledError:
            await conn.close()
            raise
        except Exception as exc:  # noqa: BLE001 — reconnect on any transport fault
            logger.warning("cell listener dropped, reconnecting: %s", exc)
            await conn.close()
            await asyncio.sleep(RECONNECT_DELAY_SECONDS)
