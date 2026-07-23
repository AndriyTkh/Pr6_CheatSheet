"""The SSE endpoint the grid subscribes to (§4 step 7).

`GET /case/{case_id}/stream` opens one Server-Sent Events connection. It
subscribes to the broker for this case, runs the updates through the coalescing
batcher, and emits **one `cells` event per flush window** — never one per cell.
That is the whole task: at pilot ceiling a wavefront run turns thousands of cells
terminal in a burst, and one message per cell would re-render the grid thousands
of times.

Event shape (what Role 5 parses):

    event: cells
    id: <max cell version in this batch>
    data: {"updates": [{"row_id","column_id","version","status"}, ...],
           "max_version": <int>}

`id:` is the batch's high-water version. The browser resends it as
`Last-Event-ID` on reconnect, and it is exactly the cursor the reconcile endpoint
wants: on reconnect the client calls `GET /case/:id/cells?since=<that id>` to
catch up on anything the live stream dropped, then resumes here. Every `version`
is monotonic (`cell_version_seq`), so nothing filled during a disconnect is lost.
"""

from __future__ import annotations

import json
import uuid
from typing import AsyncIterator

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from app.realtime.batcher import CellBatcher
from app.realtime.broker import broker
from app.realtime.events import CellUpdate

router = APIRouter(tags=["realtime"])

#: sse-starlette sends a comment ping on this cadence so proxies don't reap an
#: idle connection between bursts.
PING_SECONDS = 15


def _encode_batch(batch: list[CellUpdate]) -> dict[str, str]:
    """One coalesced flush → one SSE `cells` event (id = batch high-water version)."""
    max_version = max(update.version for update in batch)
    return {
        "event": "cells",
        "id": str(max_version),
        "data": json.dumps(
            {"updates": [u.as_dict() for u in batch], "max_version": max_version}
        ),
    }


@router.get("/case/{case_id}/stream")
async def stream_cells(case_id: uuid.UUID, request: Request) -> EventSourceResponse:
    """Live, coalesced cell updates for one case over SSE."""

    async def event_stream() -> AsyncIterator[dict[str, str]]:
        with broker.subscribe(case_id) as queue:
            batcher = CellBatcher(queue)
            async for batch in batcher.batches():
                if await request.is_disconnected():
                    break
                yield _encode_batch(batch)

    return EventSourceResponse(event_stream(), ping=PING_SECONDS)
