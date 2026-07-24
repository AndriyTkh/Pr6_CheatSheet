"""§4 step 5 — a cell never runs before its inputs are ready, and never off-grain.

Three things are proved, and they are the three the task file names:

1. **A cell with a non-terminal input is never enqueued.** Asserted with a spy on
   the enqueue seam, not on the resulting status — "it ended up blocked" would
   still be true if the job had been deferred and the worker simply lost the
   race. The spy is what proves the job does not exist.
2. **Off-grain rows get no cell at all** (§2a) — not a blocked cell, not an empty
   one. `SELECT` finds nothing.
3. **A terminal cell promotes the blocked cells it unblocked, in its own row
   only.** Another row's dependent stays blocked until that row's own input
   finishes.

These tests own committed data (`dispatch_column` commits, so the shared
rolled-back `session` fixture would leak rows) and delete their case at the end;
a case cascades sheet/row/column/cell. No `run`/`recipe` rows are involved — the
wavefront decides *whether* to enqueue and never executes anything.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Case, Cell, Column, ColumnInput, Row, Sheet
from app.models.enums import CellStatus, RowOrigin, RowState, SheetKind
from app.services.wavefront import (
    dispatch_column,
    inputs_ready,
    on_cell_terminal,
)
from app.tests.conftest import TEST_DB_URL, requires_db

# =====================================================================
# Readiness — pure, always runs
# =====================================================================


def test_all_terminal_inputs_are_ready():
    assert inputs_ready([CellStatus.Answered, CellStatus.NotApplicable]) is True
    # Terminal-EMPTY is still terminal: the dead-end lock (§6) is what makes it
    # cheap, and the lock only fires on a dispatched cell.
    assert inputs_ready([CellStatus.NotFound, CellStatus.InsufficientData]) is True


def test_no_inputs_is_ready():
    """A seed/connector column depends on nothing, so it is ready immediately."""
    assert inputs_ready([]) is True


@pytest.mark.parametrize(
    "status",
    [CellStatus.blocked, CellStatus.pending, CellStatus.running, None],
)
def test_a_non_terminal_input_is_not_ready(status):
    """`None` = the input cell does not exist yet, which is not an answer."""
    assert inputs_ready([CellStatus.Answered, status]) is False


# =====================================================================
# Fixtures — committed, self-cleaning
# =====================================================================


class EnqueueSpy:
    """Stands in for `app.tasks.cells.enqueue_cell` — records, never defers."""

    def __init__(self) -> None:
        self.calls: list[tuple[uuid.UUID, uuid.UUID, bool]] = []

    async def __call__(
        self, row_id: uuid.UUID, column_id: uuid.UUID, *, cache_bust: bool = False
    ) -> int:
        self.calls.append((row_id, column_id, cache_bust))
        return len(self.calls)

    def pairs(self) -> set[tuple[uuid.UUID, uuid.UUID]]:
        return {(r, c) for r, c, _ in self.calls}


@pytest.fixture
def spy() -> EnqueueSpy:
    return EnqueueSpy()


@pytest_asyncio.fixture
async def db() -> AsyncSession:
    """A committing session; the case it created is deleted on the way out."""
    engine = create_async_engine(TEST_DB_URL)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    created: list[uuid.UUID] = []
    async with factory() as session:
        session.info["cases"] = created
        try:
            yield session
        finally:
            await session.rollback()
            for case_id in created:
                case = await session.get(Case, case_id)
                if case is not None:
                    await session.delete(case)
            await session.commit()
    await engine.dispose()


async def _sheet(db: AsyncSession) -> Sheet:
    case = Case(name="wavefront test", owner_id=uuid.uuid4())
    db.add(case)
    await db.flush()
    db.info["cases"].append(case.id)
    sheet = Sheet(
        case_id=case.id, name="Тендери", kind=SheetKind.source, grain_label="lot"
    )
    db.add(sheet)
    await db.flush()
    return sheet


async def _row(db: AsyncSession, sheet: Sheet, *, depth: int = 0, **kw: Any) -> Row:
    row = Row(
        case_id=sheet.case_id,
        sheet_id=sheet.id,
        origin=RowOrigin.connector,
        provenance_jsonb={"tenderID": f"UA-{uuid.uuid4().hex[:8]}", "lotID": "lot-1"},
        depth=depth,
        # 0002's `row_depth_implies_parent`: an expanded child carries its index
        # in the source list; a depth-0 row must not.
        ordinal=None if depth == 0 else 0,
        **kw,
    )
    db.add(row)
    await db.flush()
    return row


async def _column(
    db: AsyncSession, sheet: Sheet, name: str, *, target_depth: int = 0
) -> Column:
    column = Column(
        case_id=sheet.case_id,
        sheet_id=sheet.id,
        name=name,
        value_type="text",
        target_depth=target_depth,
    )
    db.add(column)
    await db.flush()
    return column


async def _edge(db: AsyncSession, downstream: Column, upstream: Column) -> None:
    db.add(ColumnInput(column_id=downstream.id, input_column_id=upstream.id))
    await db.flush()


async def _cell(
    db: AsyncSession, row: Row, column: Column, status: CellStatus, value: Any = None
) -> Cell:
    cell = Cell(row_id=row.id, column_id=column.id, status=status, value_jsonb=value)
    db.add(cell)
    await db.flush()
    return cell


async def _status(db: AsyncSession, row: Row, column: Column) -> CellStatus | None:
    cell = await db.get(Cell, (row.id, column.id))
    return None if cell is None else cell.status


# =====================================================================
# Grain (§2a)
# =====================================================================


@requires_db
async def test_off_grain_rows_get_no_cell_at_all(db, spy):
    """§2a — the two grains of an inline-expanded sheet never cross."""
    sheet = await _sheet(db)
    lot = await _row(db, sheet, depth=0)
    participant = await _row(db, sheet, depth=1)
    column = await _column(db, sheet, "YouControl", target_depth=1)

    plan = await dispatch_column(db, column, enqueue=spy)

    assert plan.off_grain == 1
    assert await _status(db, participant, column) is CellStatus.pending
    assert await _status(db, lot, column) is None, (
        "a depth-0 row got a cell from a target_depth=1 column — the grains crossed"
    )
    cells = (
        (await db.execute(select(Cell).where(Cell.column_id == column.id)))
        .scalars()
        .all()
    )
    assert [c.row_id for c in cells] == [participant.id]
    assert spy.pairs() == {(participant.id, column.id)}


@requires_db
async def test_dormant_rows_are_skipped(db, spy):
    """§4 step 5 — `row.state != 'active'` is skipped (dormant axis, P0)."""
    sheet = await _sheet(db)
    active = await _row(db, sheet)
    merged = await _row(db, sheet, state=RowState.merged)
    column = await _column(db, sheet, "Winner")

    plan = await dispatch_column(db, column, enqueue=spy)

    assert plan.dormant == 1
    assert await _status(db, merged, column) is None
    assert spy.pairs() == {(active.id, column.id)}


# =====================================================================
# Readiness gate
# =====================================================================


@requires_db
async def test_a_cell_with_a_non_terminal_input_is_never_enqueued(db, spy):
    """The Verify line, asserted on the queue seam rather than on the status."""
    sheet = await _sheet(db)
    row = await _row(db, sheet)
    upstream = await _column(db, sheet, "Participants")
    downstream = await _column(db, sheet, "Owner")
    await _edge(db, downstream, upstream)
    await _cell(db, row, upstream, CellStatus.running)

    plan = await dispatch_column(db, downstream, enqueue=spy)

    assert spy.calls == [], "a job was deferred for a cell whose input is still running"
    assert plan.enqueued == []
    assert await _status(db, row, downstream) is CellStatus.blocked


@requires_db
async def test_a_missing_input_cell_also_blocks(db, spy):
    """No cell at all is not an answer — it must not read as ready."""
    sheet = await _sheet(db)
    row = await _row(db, sheet)
    upstream = await _column(db, sheet, "Participants")
    downstream = await _column(db, sheet, "Owner")
    await _edge(db, downstream, upstream)

    await dispatch_column(db, downstream, enqueue=spy)

    assert spy.calls == []
    assert await _status(db, row, downstream) is CellStatus.blocked


@requires_db
async def test_rows_whose_inputs_are_terminal_are_enqueued_now(db, spy):
    sheet = await _sheet(db)
    ready_row = await _row(db, sheet)
    waiting_row = await _row(db, sheet)
    upstream = await _column(db, sheet, "Participants")
    downstream = await _column(db, sheet, "Owner")
    await _edge(db, downstream, upstream)
    await _cell(db, ready_row, upstream, CellStatus.Answered, ["1234"])
    await _cell(db, waiting_row, upstream, CellStatus.pending)

    plan = await dispatch_column(db, downstream, enqueue=spy)

    assert spy.pairs() == {(ready_row.id, downstream.id)}
    assert plan.blocked == [(waiting_row.id, downstream.id)]
    assert await _status(db, ready_row, downstream) is CellStatus.pending
    assert await _status(db, waiting_row, downstream) is CellStatus.blocked


@requires_db
async def test_dispatch_does_not_discard_an_answer_already_on_the_grid(db, spy):
    """Re-dispatching a column must not blank a cell the journalist is reading.

    (Re-running one deliberately is `invalidate_cell` — see `test_cache_key.py`.)
    """
    sheet = await _sheet(db)
    row = await _row(db, sheet)
    column = await _column(db, sheet, "Winner")
    await _cell(db, row, column, CellStatus.Answered, "31200334")

    await dispatch_column(db, column, enqueue=spy)

    cell = await db.get(Cell, (row.id, column.id))
    assert cell.status is CellStatus.Answered
    assert cell.value_jsonb == "31200334"


# =====================================================================
# The wake-up
# =====================================================================


@requires_db
async def test_a_terminal_cell_promotes_blocked_dependents_in_its_own_row_only(db, spy):
    """§4 step 5 — re-check `blocked` cells in the *same* row."""
    sheet = await _sheet(db)
    finished_row = await _row(db, sheet)
    other_row = await _row(db, sheet)
    upstream = await _column(db, sheet, "Participants")
    downstream = await _column(db, sheet, "Owner")
    await _edge(db, downstream, upstream)
    for row in (finished_row, other_row):
        await _cell(db, row, upstream, CellStatus.pending)
        await _cell(db, row, downstream, CellStatus.blocked)

    # the upstream cell of ONE row lands terminal
    finished = await db.get(Cell, (finished_row.id, upstream.id))
    finished.status = CellStatus.Answered
    await db.commit()

    plan = await on_cell_terminal(db, finished_row.id, upstream.id, enqueue=spy)

    assert plan.enqueued == [(finished_row.id, downstream.id)]
    assert spy.pairs() == {(finished_row.id, downstream.id)}
    assert await _status(db, finished_row, downstream) is CellStatus.pending
    assert await _status(db, other_row, downstream) is CellStatus.blocked


@requires_db
async def test_a_dependent_still_missing_another_input_stays_blocked(db, spy):
    """Two inputs, one finishes: the diamond's second leg must still gate it."""
    sheet = await _sheet(db)
    row = await _row(db, sheet)
    first = await _column(db, sheet, "Participants")
    second = await _column(db, sheet, "Amount")
    downstream = await _column(db, sheet, "Owner")
    await _edge(db, downstream, first)
    await _edge(db, downstream, second)
    await _cell(db, row, first, CellStatus.Answered, ["1234"])
    await _cell(db, row, second, CellStatus.running)
    await _cell(db, row, downstream, CellStatus.blocked)
    await db.commit()

    plan = await on_cell_terminal(db, row.id, first.id, enqueue=spy)

    assert spy.calls == []
    assert plan.blocked == [(row.id, downstream.id)]
    assert await _status(db, row, downstream) is CellStatus.blocked


@requires_db
async def test_the_wake_up_never_re_enqueues_a_cell_that_is_not_blocked(db, spy):
    """A `pending`/`running`/terminal dependent is already someone's job.

    Re-deferring it here is how a paid cell gets run twice.
    """
    sheet = await _sheet(db)
    row = await _row(db, sheet)
    upstream = await _column(db, sheet, "Participants")
    downstream = await _column(db, sheet, "Owner")
    await _edge(db, downstream, upstream)
    await _cell(db, row, upstream, CellStatus.Answered, ["1234"])
    await _cell(db, row, downstream, CellStatus.running)
    await db.commit()

    await on_cell_terminal(db, row.id, upstream.id, enqueue=spy)

    assert spy.calls == []
    assert await _status(db, row, downstream) is CellStatus.running


@requires_db
async def test_the_wake_up_skips_a_dependent_on_the_wrong_grain(db, spy):
    """A depth-1 dependent of a depth-0 column has no cell to promote (§2a)."""
    sheet = await _sheet(db)
    lot = await _row(db, sheet, depth=0)
    upstream = await _column(db, sheet, "Participants", target_depth=0)
    downstream = await _column(db, sheet, "Owner", target_depth=1)
    await _edge(db, downstream, upstream)
    await _cell(db, lot, upstream, CellStatus.Answered, ["1234"])
    await db.commit()

    plan = await on_cell_terminal(db, lot.id, upstream.id, enqueue=spy)

    assert spy.calls == []
    assert plan.off_grain == 1
    assert await _status(db, lot, downstream) is None
