"""The cell-execution task, and the one function that enqueues it (§4).

The division of labour §4 spells out:

* **Wavefront readiness decides *when* a cell's job is created.** That is the
  next task (§4 step 5) and it is not implemented here — this module offers
  `enqueue_cell()` and nothing calls it automatically.
* **Procrastinate decides *which worker* runs it.** That is this module.

So the seam is exactly one call: the wavefront, having found a cell whose
inputs are all terminal, calls `await enqueue_cell(row_id, column_id)`. It
never touches the queue tables and never reasons about workers.
"""

from __future__ import annotations

import logging
import uuid

from app.db.session import async_session_factory
from app.services.cell_execution import execute_cell as run_cell
from app.tasks.app import procrastinate_app

logger = logging.getLogger(__name__)

#: Named explicitly so the queue row is readable in `procrastinate_jobs` and so
#: a rename of this function never orphans jobs already deferred.
TASK_NAME = "cheatsheet.execute_cell"


@procrastinate_app.task(name=TASK_NAME, queue="cells")
async def execute_cell(
    row_id: str, column_id: str, cache_bust: bool = False
) -> dict[str, object]:
    """Run one cell. Arguments are strings — job args are JSON, so UUIDs aren't.

    Its own session: a worker job shares nothing with the request that deferred
    it. `execute_cell` in the service owns the commits (claim, then result).
    """
    async with async_session_factory() as session:
        outcome = await run_cell(
            session,
            uuid.UUID(row_id),
            uuid.UUID(column_id),
            cache_bust=cache_bust,
        )
    logger.info("execute_cell %s", outcome.as_log())
    return outcome.as_log()


async def enqueue_cell(
    row_id: uuid.UUID,
    column_id: uuid.UUID,
    *,
    cache_bust: bool = False,
) -> int:
    """Hand one cell to the queue. **The** seam for §4 step 5.

    Returns the Procrastinate job id. Deferring is a plain INSERT plus a
    `NOTIFY`; a listening worker wakes immediately and takes the row under
    `SKIP LOCKED`. Nothing here waits, polls, or looks at `cell.status`.

    The caller is responsible for having decided the cell is ready. Calling this
    on a cell whose inputs aren't terminal is not blocked at this layer — the
    dead-end lock (§6) will still stop it spending, but the wavefront is what
    makes it never happen.
    """
    job_id = await execute_cell.defer_async(
        row_id=str(row_id), column_id=str(column_id), cache_bust=cache_bust
    )
    return job_id
