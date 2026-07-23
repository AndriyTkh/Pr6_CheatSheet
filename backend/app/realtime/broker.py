"""In-process fan-out of cell updates to open SSE connections.

One process runs the Postgres listener (`listener.py`); it publishes each
`CellUpdate` here, and the broker copies it to every SSE connection subscribed to
that update's case. Scoping is by `case_id`: a connection watching case A never
sees case B's cells.

The queues are bounded. A client that cannot keep up (a paused tab, a slow link)
fills its queue; rather than balloon memory or block the publisher, the broker
**drops** the overflow and the client is expected to catch up via the
reconcile-on-reconnect endpoint (`GET /case/:id/cells?since=<version>`) — which is
exactly why every update carries a monotonic version. A dropped live message is
never a lost cell.

The broker is process-local. A multi-process deployment runs the listener in each
web process (each opens its own `LISTEN`), so every process's subscribers are fed;
Postgres `NOTIFY` fans out to all listeners. Nothing here needs Redis at pilot
scale (§4 closing paragraph).
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Iterator
from contextlib import contextmanager

from app.realtime.events import CellUpdate

logger = logging.getLogger(__name__)

#: Per-connection backlog before overflow is dropped (reconcile covers the gap).
SUBSCRIBER_QUEUE_MAX = 2000


class Broker:
    def __init__(self) -> None:
        self._subscribers: dict[uuid.UUID, set[asyncio.Queue[CellUpdate]]] = {}

    @contextmanager
    def subscribe(
        self, case_id: uuid.UUID
    ) -> Iterator[asyncio.Queue[CellUpdate]]:
        """Register a per-connection queue for one case; unregister on exit.

        A context manager so a disconnecting client is always cleaned up — the
        SSE route wraps its whole lifetime in this, so an abandoned connection
        never leaks a queue that the publisher keeps writing to.
        """
        queue: asyncio.Queue[CellUpdate] = asyncio.Queue(maxsize=SUBSCRIBER_QUEUE_MAX)
        self._subscribers.setdefault(case_id, set()).add(queue)
        try:
            yield queue
        finally:
            subs = self._subscribers.get(case_id)
            if subs is not None:
                subs.discard(queue)
                if not subs:
                    del self._subscribers[case_id]

    def publish(self, update: CellUpdate) -> None:
        """Fan one update out to every connection watching its case.

        Non-blocking: a full subscriber queue drops the update (see module
        docstring) instead of stalling the listener that feeds every connection.
        """
        for queue in self._subscribers.get(update.case_id, ()):
            try:
                queue.put_nowait(update)
            except asyncio.QueueFull:
                logger.warning(
                    "SSE subscriber backlog full for case %s — dropping cell "
                    "(%s, %s) v%s; client reconciles on reconnect",
                    update.case_id,
                    update.row_id,
                    update.column_id,
                    update.version,
                )

    def subscriber_count(self, case_id: uuid.UUID) -> int:
        """Open connections for a case — used by the listener to skip dead cases."""
        return len(self._subscribers.get(case_id, ()))


#: Process-wide broker. The listener publishes to it; SSE routes subscribe.
broker = Broker()
