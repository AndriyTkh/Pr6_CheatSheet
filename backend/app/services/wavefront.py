"""§4 step 5 — wavefront-gated enqueue. Readiness lives in data, not in order.

Topo order of *enqueue* is not topo order of *execution*: under parallel workers
the job you deferred second can be picked up first. So nothing here relies on
insertion order. A cell is created in one of exactly two states —

* every input already terminal → `pending`, and its job is deferred now;
* otherwise → `blocked`, and no job exists at all.

— and the only thing that moves a cell from `blocked` to `pending` is
`on_cell_terminal()`, which runs when some cell in that row actually reached a
terminal status. A cell therefore cannot run before its inputs are ready, no
matter how the workers interleave.

**Grain is the other half (§2a).** Rows are scoped to the column's
`target_depth`: off-grain rows get **no cell at all**, not a blocked one. That is
what keeps an `inline`-expanded sheet's two grains from crossing — "run YouControl
on the participants" cannot fire on the lot rows, because the cells do not exist.
Dormant rows (`row.state != 'active'`) are skipped the same way.

**On `LISTEN/NOTIFY`.** §4 names it as the wake-up, and `publish_cell_terminal()`
emits a real `pg_notify` for out-of-process listeners (the SSE task, §4 step 7).
The wavefront itself does not need to listen: the only writer of a terminal cell
status is the worker running that cell, so the re-check is called directly at the
end of that job — same event, no round trip, no second poller. `cell.status` is
still never a lock; it is read here to decide what to *create*, which is the
data-side gate §4 asks for.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Iterable, Sequence

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.dag.invariants import cell_is_placeable
from app.models import Cell, Column, ColumnInput, Row, cell_version_seq
from app.models.enums import TERMINAL, CellStatus, RowState

logger = logging.getLogger(__name__)

#: The seam from `role-2/wk2-queue`: (row_id, column_id, *, cache_bust) -> job id.
EnqueueFn = Callable[..., Awaitable[int]]

#: Out-of-process wake-up channel. Payload is small on purpose — a listener
#: re-reads the cell rather than trusting a NOTIFY body (8000-byte limit).
CELL_CHANNEL = "cheatsheet_cell"


@dataclass(slots=True)
class WavefrontPlan:
    """What one wavefront pass decided. Returned so callers can log/assert it."""

    enqueued: list[tuple[uuid.UUID, uuid.UUID]] = field(default_factory=list)
    blocked: list[tuple[uuid.UUID, uuid.UUID]] = field(default_factory=list)
    #: rows on the sheet at the wrong grain — deliberately cell-less (§2a)
    off_grain: int = 0
    #: `row.state != 'active'` — dormant in P0, skipped anyway (§4 step 5)
    dormant: int = 0

    def __len__(self) -> int:
        return len(self.enqueued) + len(self.blocked)


def inputs_ready(statuses: Iterable[CellStatus | None]) -> bool:
    """All inputs terminal? A missing cell is not terminal — it is not ready.

    Pure, and the whole readiness rule: a cell with any non-terminal input is
    never enqueued. Terminal-*empty* still counts as ready — the dead-end lock
    (§6, week 3) is what turns it into a cheap `InsufficientData` without
    spending, and that lock needs the cell dispatched to fire.
    """
    return all(status is not None and status in TERMINAL for status in statuses)


# ---------------------------------------------------------------------
# Step 5 — on confirm
# ---------------------------------------------------------------------


async def dispatch_column(
    session: AsyncSession,
    column: Column,
    *,
    cache_bust: bool = False,
    enqueue: EnqueueFn | None = None,
) -> WavefrontPlan:
    """Create this column's cells across its sheet and enqueue the ready ones.

    Commits the cells **before** deferring any job: a worker woken by the
    `NOTIFY` must be able to see the row it was told about.
    """
    plan = WavefrontPlan()
    input_column_ids = await _input_column_ids(session, column.id)

    rows = (
        (await session.execute(select(Row).where(Row.sheet_id == column.sheet_id)))
        .scalars()
        .all()
    )
    for row in rows:
        if row.state is not RowState.active:
            plan.dormant += 1
            continue
        if not cell_is_placeable(row, column):
            # §2a: no cell at all off-grain — not a blocked one, not an error.
            plan.off_grain += 1
            continue

        ready = inputs_ready(await _input_statuses(session, row.id, input_column_ids))
        await _upsert_cell(
            session,
            row.id,
            column.id,
            CellStatus.pending if ready else CellStatus.blocked,
        )
        (plan.enqueued if ready else plan.blocked).append((row.id, column.id))

    await session.commit()
    await _defer_all(plan.enqueued, enqueue, cache_bust=cache_bust)
    return plan


# ---------------------------------------------------------------------
# Step 5 — the wake-up
# ---------------------------------------------------------------------


async def on_cell_terminal(
    session: AsyncSession,
    row_id: uuid.UUID,
    column_id: uuid.UUID,
    *,
    enqueue: EnqueueFn | None = None,
) -> WavefrontPlan:
    """A cell went terminal → promote the `blocked` cells it just unblocked.

    Scoped exactly as §4 scopes it: **the same row**, and only columns that
    declare an edge from the column that finished. A dependent in another row is
    another row's business and will be woken by that row's own finishing cell.
    """
    plan = WavefrontPlan()
    row = await session.get(Row, row_id)
    if row is None or row.state is not RowState.active:
        return plan

    dependents = (
        (
            await session.execute(
                select(Column)
                .join(ColumnInput, ColumnInput.column_id == Column.id)
                .where(ColumnInput.input_column_id == column_id)
            )
        )
        .scalars()
        .all()
    )
    for dependent in dependents:
        if not cell_is_placeable(row, dependent):
            plan.off_grain += 1
            continue
        cell = await session.get(Cell, (row.id, dependent.id))
        if cell is None or cell.status is not CellStatus.blocked:
            # Not blocked = already pending, running, or answered. Re-enqueueing
            # it here is how a cell gets run (and paid for) twice.
            continue
        statuses = await _input_statuses(
            session, row.id, await _input_column_ids(session, dependent.id)
        )
        if not inputs_ready(statuses):
            plan.blocked.append((row.id, dependent.id))
            continue
        cell.status = CellStatus.pending
        cell.version = cell_version_seq.next_value()
        plan.enqueued.append((row.id, dependent.id))

    await session.commit()
    await _defer_all(plan.enqueued, enqueue)
    return plan


async def publish_cell_terminal(
    session: AsyncSession, row_id: uuid.UUID, column_id: uuid.UUID
) -> None:
    """Emit the §4 `NOTIFY` for out-of-process listeners (SSE, §4 step 7).

    Fire-and-forget: nothing in the wavefront depends on a listener existing, so
    a failure here must never cost a completed cell.
    """
    try:
        await session.execute(
            text(f"SELECT pg_notify('{CELL_CHANNEL}', :payload)"),
            {"payload": f'{{"row_id":"{row_id}","column_id":"{column_id}"}}'},
        )
    except Exception as exc:  # noqa: BLE001 — a missed notify is not a lost cell
        logger.warning("pg_notify on %s failed: %s", CELL_CHANNEL, exc)


# ---------------------------------------------------------------------
# Force refresh (§4 step 6, cache-bust)
# ---------------------------------------------------------------------


async def invalidate_cell(
    session: AsyncSession,
    row_id: uuid.UUID,
    column_id: uuid.UUID,
    *,
    enqueue: EnqueueFn | None = None,
) -> bool:
    """User (or stale-column confirm) invalidates ONE cell → re-run, bypassing cache.

    `status='pending'` plus `cache_bust` on the job, exactly as §4 step 6 spells
    it out. The old `run` is retained — history is append-only (Principle 5) — and
    no `recipe_version` bump is needed to re-run a single row. The cell keeps its
    old value and citation until the new run overwrites them, so the grid does not
    blank out while a slow recipe is in flight.
    """
    cell = await session.get(Cell, (row_id, column_id))
    if cell is None:
        return False
    cell.status = CellStatus.pending
    cell.version = cell_version_seq.next_value()
    await session.commit()
    await _defer_all([(row_id, column_id)], enqueue, cache_bust=True)
    return True


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------


async def _input_column_ids(
    session: AsyncSession, column_id: uuid.UUID
) -> list[uuid.UUID]:
    return list(
        (
            await session.execute(
                select(ColumnInput.input_column_id).where(
                    ColumnInput.column_id == column_id
                )
            )
        )
        .scalars()
        .all()
    )


async def _input_statuses(
    session: AsyncSession, row_id: uuid.UUID, input_column_ids: Sequence[uuid.UUID]
) -> list[CellStatus | None]:
    """`None` where the input cell does not exist yet — which is not ready."""
    statuses: list[CellStatus | None] = []
    for input_column_id in input_column_ids:
        cell = await session.get(Cell, (row_id, input_column_id))
        statuses.append(None if cell is None else cell.status)
    return statuses


async def _upsert_cell(
    session: AsyncSession,
    row_id: uuid.UUID,
    column_id: uuid.UUID,
    status: CellStatus,
) -> Cell:
    """Create the cell, or re-arm an existing one that has not run yet.

    A terminal cell is left alone: re-dispatching a column must not discard an
    answer the journalist is already reading. Re-running one is `invalidate_cell`.
    """
    cell = await session.get(Cell, (row_id, column_id))
    if cell is None:
        cell = Cell(row_id=row_id, column_id=column_id, status=status)
        session.add(cell)
        return cell
    if cell.status in TERMINAL or cell.status is CellStatus.running:
        return cell
    cell.status = status
    cell.version = cell_version_seq.next_value()
    return cell


async def _defer_all(
    targets: Sequence[tuple[uuid.UUID, uuid.UUID]],
    enqueue: EnqueueFn | None,
    *,
    cache_bust: bool = False,
) -> None:
    """The one call into the queue layer — imported late to keep the seam one-way.

    `app.tasks.cells` imports the execution service, which imports this module;
    a module-level import here would close that loop.
    """
    if not targets:
        return
    if enqueue is None:
        from app.tasks.cells import enqueue_cell

        enqueue = enqueue_cell
    for row_id, column_id in targets:
        await enqueue(row_id, column_id, cache_bust=cache_bust)
