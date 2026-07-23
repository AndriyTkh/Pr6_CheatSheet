"""Coalescing flush buffer — the heart of §4 step 7.

The frontend risk at pilot scale is **update rate**, not row count. `dispatch_column`
turns a whole sheet's cells terminal in a burst; without batching that is one SSE
message per cell and the grid re-renders thousands of times in a few seconds. This
buffer collapses that burst: every cell that goes terminal inside one window
(`window_seconds`, 150-250ms) is delivered in a **single** batch. If the burst is
so dense that `max_cells` queue before the window elapses, it flushes early rather
than letting one message grow without bound.

Two updates to the *same* cell inside one window coalesce to one entry, keeping the
**higher** version (`events.CellUpdate.key` is the identity). So a cell that flips
`running → Answered` twice in a window ships once, at its latest version — the grid
never renders a stale intermediate and the version the client last saw never goes
backwards.

Pure and DB-free on purpose: it reads a source `asyncio.Queue` and yields
`list[CellUpdate]`. The queue is fed by a broker subscription in production and by
the test directly, so the "N in → one out" guarantee is asserted without a socket
or a database.
"""

from __future__ import annotations

import asyncio
from typing import AsyncIterator

from app.realtime.events import CellUpdate

#: §4 step 7 names "150-250ms or N cells". These are the defaults; the SSE route
#: and the tests can override them.
DEFAULT_WINDOW_SECONDS = 0.2
DEFAULT_MAX_CELLS = 200


class CellBatcher:
    """Drains a source queue into coalesced, time-or-size-bounded batches."""

    def __init__(
        self,
        source: asyncio.Queue[CellUpdate],
        *,
        window_seconds: float = DEFAULT_WINDOW_SECONDS,
        max_cells: int = DEFAULT_MAX_CELLS,
    ) -> None:
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        if max_cells < 1:
            raise ValueError("max_cells must be >= 1")
        self._source = source
        self._window = window_seconds
        self._max_cells = max_cells

    async def batches(self) -> AsyncIterator[list[CellUpdate]]:
        """Yield one coalesced batch per flush window, forever.

        A batch is never empty: the window clock does not start until the first
        update of the burst arrives (the initial `get()` blocks with no timeout),
        so an idle stream yields nothing rather than a stream of empty flushes.
        """
        loop = asyncio.get_running_loop()
        while True:
            first = await self._source.get()
            pending: dict[tuple, CellUpdate] = {first.key: first}
            deadline = loop.time() + self._window

            while len(pending) < self._max_cells:
                timeout = deadline - loop.time()
                if timeout <= 0:
                    break
                try:
                    update = await asyncio.wait_for(self._source.get(), timeout)
                except asyncio.TimeoutError:
                    break
                self._coalesce(pending, update)

            yield list(pending.values())

    @staticmethod
    def _coalesce(pending: dict[tuple, CellUpdate], update: CellUpdate) -> None:
        """Keep the higher version for a cell already in this window's batch.

        Out-of-order arrival is possible (two workers, two NOTIFYs); the version
        is the tiebreaker, never arrival order, so the batch carries the latest
        state of each cell regardless of how the messages interleaved.
        """
        existing = pending.get(update.key)
        if existing is None or update.version >= existing.version:
            pending[update.key] = update
