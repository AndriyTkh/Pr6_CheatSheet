"""Reconcile-on-reconnect endpoint (§4 step 7).

`GET /case/{case_id}/cells?since=<version>` — the companion to the SSE stream in
`realtime/routes.py`. The stream has no replay of its own; on reconnect a client
reads its last `Last-Event-ID` (the high-water `cell.version` it saw), calls this
once to catch up on anything the stream dropped during the disconnect, then
resumes the stream. Because every terminal write bumps `cell_version_seq`, the two
page the same number line — nothing that filled while disconnected is lost.

See `_docs/handoffs/role-2-wk2-reconcile.md` for the full handshake (Role 5 builds
the client half against it).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.reconcile import fetch_cells_since

router = APIRouter(tags=["realtime"])


@router.get("/case/{case_id}/cells")
async def reconcile_cells(
    case_id: uuid.UUID,
    since: int = Query(
        0, ge=0, description="last cell.version the client saw (its reconnect cursor)"
    ),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Terminal cells in the case past `since`, ordered by version.

    `max_version` is the new cursor the client carries into the resumed stream —
    the highest version returned, or `since` unchanged when nothing advanced (so
    the cursor never goes backwards on an empty catch-up).
    """
    cells = await fetch_cells_since(session, case_id, since)
    max_version = cells[-1].version if cells else since
    return {
        "since": since,
        "max_version": max_version,
        "updates": [cell.as_dict() for cell in cells],
    }
