"""§4 "Staleness" — editing an upstream column greys its dependents, reruns nothing.

What the task file (`role-2.md`, week 2) names is proved here, all against a real
DB because the walk *is* the §4 recursive CTE:

1. **Dependents get marked `stale`** — direct and transitive — while the edited
   column itself does not (only downstream greys).
2. **Nothing is re-executed.** A downstream cell holding an `Answered` value +
   citation keeps all three (value, citation, `version`) after the walk; §5 —
   `cell.status` is the per-operation truth and stays put, only the
   `column.status` rollup greys. The service has no queue import and writes no
   cell, so a rerun structurally cannot happen.
3. **The walk crosses a sheet boundary** (§2a) — a source-sheet column feeding a
   derived-sheet column chain greys the derived columns by the same walk.

Plus the two termination guarantees §4 calls out for `UNION` (not `UNION ALL`):
a diamond visits its sink once, and an accidental cycle does not loop forever.

The service does not commit (the caller owns the transaction), so these tests use
the shared rolled-back `session` fixture and leave nothing behind.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Cell, Column, ColumnInput, Row, Sheet
from app.models.enums import CellStatus, ColumnStatus, RowOrigin, SheetKind
from app.services.staleness import mark_downstream_stale
from app.tests.conftest import requires_db

# ---------------------------------------------------------------------
# Helpers on the shared (rolled-back) session
# ---------------------------------------------------------------------


async def _edge(session: AsyncSession, downstream: Column, upstream: Column) -> None:
    """`upstream` feeds `downstream` — one `column_input` DAG edge."""
    session.add(ColumnInput(column_id=downstream.id, input_column_id=upstream.id))
    await session.flush()


async def _row(session: AsyncSession, sheet: Sheet) -> Row:
    row = Row(
        case_id=sheet.case_id,
        sheet_id=sheet.id,
        origin=RowOrigin.connector,
        provenance_jsonb={"tenderID": f"UA-{uuid.uuid4().hex[:8]}", "lotID": "lot-1"},
        depth=0,
        ordinal=None,
    )
    session.add(row)
    await session.flush()
    return row


async def _cell(
    session: AsyncSession,
    row: Row,
    column: Column,
    status: CellStatus,
    value=None,
    citation=None,
) -> Cell:
    cell = Cell(
        row_id=row.id,
        column_id=column.id,
        status=status,
        value_jsonb=value,
        citation_jsonb=citation or [],
    )
    session.add(cell)
    await session.flush()
    return cell


async def _derived_sheet(session: AsyncSession, source: Sheet) -> Sheet:
    """A second sheet on the same case — where an Expand `new_table` lands (§2a)."""
    sheet = Sheet(
        case_id=source.case_id,
        name="Companies",
        kind=SheetKind.derived,
        grain_label="company",
        # constraint `sheet_parent_iff_derived`: a derived sheet MUST name its parent.
        parent_sheet_id=source.id,
    )
    session.add(sheet)
    await session.flush()
    return sheet


async def _set_status(session: AsyncSession, *columns: Column) -> None:
    """Put columns in a settled (non-stale) state so the flip to `stale` is real."""
    for column in columns:
        column.status = ColumnStatus.done
    await session.flush()


async def _status(session: AsyncSession, column: Column) -> ColumnStatus:
    fetched = await session.get(Column, column.id)
    return fetched.status


# ---------------------------------------------------------------------
# 1 — dependents grey, the edited column does not
# ---------------------------------------------------------------------


@requires_db
async def test_direct_and_transitive_dependents_are_marked_stale(session, make_column):
    """A → B → C. Editing A greys B and C; A itself is left alone."""
    a = await make_column("A")
    b = await make_column("B")
    c = await make_column("C")
    await _edge(session, b, a)
    await _edge(session, c, b)
    await _set_status(session, a, b, c)

    result = await mark_downstream_stale(session, a.id)

    assert set(result.stale_column_ids) == {b.id, c.id}
    assert result.new_version_available is True
    assert await _status(session, b) is ColumnStatus.stale
    assert await _status(session, c) is ColumnStatus.stale
    # Only *dependents* grey — the column the user edited is not stale-to-itself.
    assert await _status(session, a) is ColumnStatus.done
    assert a.id not in result.stale_column_ids


@requires_db
async def test_a_leaf_edit_surfaces_no_prompt(session, make_column):
    """A column nothing depends on has no downstream — no 'new version' prompt."""
    leaf = await make_column("leaf")
    await _set_status(session, leaf)

    result = await mark_downstream_stale(session, leaf.id)

    assert result.stale_column_ids == []
    assert result.new_version_available is False


# ---------------------------------------------------------------------
# 2 — nothing is re-executed
# ---------------------------------------------------------------------


@requires_db
async def test_greying_a_column_does_not_touch_its_cells(
    session, make_column, source_sheet
):
    """§5 — cells keep their old value + citation + version; only the rollup greys.

    The strongest available proof that nothing re-ran: an `Answered` cell with a
    real value and citation is byte-for-byte unchanged after the walk. The
    service imports no queue and writes no cell, so a rerun cannot happen.
    """
    upstream = await make_column("participants")
    downstream = await make_column("owner")
    await _edge(session, downstream, upstream)
    await _set_status(session, upstream, downstream)

    row = await _row(session, source_sheet)
    cell = await _cell(
        session,
        row,
        downstream,
        CellStatus.Answered,
        value="Іван Іванов",
        citation=[{"quote": "директор Іван Іванов", "doc": "usr-1"}],
    )
    await session.flush()
    before_version = cell.version

    result = await mark_downstream_stale(session, upstream.id)

    assert downstream.id in result.stale_column_ids
    assert await _status(session, downstream) is ColumnStatus.stale
    # The cell is untouched — value, citation, status, and stream version.
    kept = await session.get(Cell, (row.id, downstream.id))
    assert kept.status is CellStatus.Answered
    assert kept.value_jsonb == "Іван Іванов"
    assert kept.citation_jsonb == [{"quote": "директор Іван Іванов", "doc": "usr-1"}]
    assert kept.version == before_version


# ---------------------------------------------------------------------
# 3 — the walk crosses the sheet boundary (§2a)
# ---------------------------------------------------------------------


@requires_db
async def test_walk_crosses_the_sheet_boundary(session, make_column, source_sheet):
    """§2a — re-running a source column greys the derived sheet's columns.

    `@participants` (source) feeds an Expand producer node whose output columns
    live on the derived Companies sheet. Editing `@participants` must grey the
    derived columns — 'the DAG spans sheets at the sheet boundary only', and the
    walk follows `column_input`, never `sheet_id`.
    """
    derived = await _derived_sheet(session, source_sheet)

    participants = await make_column("participants")  # source sheet
    expand = await make_column("companies_expand")  # producer node
    owner = await make_column("owner", sheet=derived)  # derived sheet column
    creation = await make_column("creation_date", sheet=derived)  # derived, deeper
    await _edge(session, expand, participants)
    await _edge(session, owner, expand)
    await _edge(session, creation, owner)
    await _set_status(session, participants, expand, owner, creation)

    result = await mark_downstream_stale(session, participants.id)

    assert set(result.stale_column_ids) == {expand.id, owner.id, creation.id}
    # The proof it crossed: the greyed columns actually live on the derived sheet.
    greyed_owner = await session.get(Column, owner.id)
    greyed_creation = await session.get(Column, creation.id)
    assert greyed_owner.sheet_id == derived.id
    assert greyed_creation.sheet_id == derived.id
    assert greyed_owner.status is ColumnStatus.stale
    assert greyed_creation.status is ColumnStatus.stale


# ---------------------------------------------------------------------
# 4 — UNION (not UNION ALL): diamonds and accidental cycles terminate
# ---------------------------------------------------------------------


@requires_db
async def test_a_diamond_visits_its_sink_once(session, make_column):
    """A → B, A → C, B → D, C → D. D is reachable two ways; it greys once."""
    a = await make_column("A")
    b = await make_column("B")
    c = await make_column("C")
    d = await make_column("D")
    await _edge(session, b, a)
    await _edge(session, c, a)
    await _edge(session, d, b)
    await _edge(session, d, c)
    await _set_status(session, a, b, c, d)

    result = await mark_downstream_stale(session, a.id)

    assert set(result.stale_column_ids) == {b.id, c.id, d.id}
    assert result.stale_column_ids.count(d.id) == 1, "UNION ALL would double-count D"


@requires_db
async def test_an_accidental_cycle_terminates(session, make_column):
    """A → B, B → C, C → B. The B↔C back-edge must not loop the walk forever.

    The edge-add validation (§4 step 2) rejects cycles, but the DB has no such
    constraint — `UNION` is the backstop that keeps a stray cycle from hanging
    the recursive CTE. Inserted directly here to exercise exactly that backstop.
    """
    a = await make_column("A")
    b = await make_column("B")
    c = await make_column("C")
    await _edge(session, b, a)
    await _edge(session, c, b)
    await _edge(session, b, c)  # the accidental back-edge, bypassing validation
    await _set_status(session, a, b, c)

    result = await mark_downstream_stale(session, a.id)

    # Terminates (the test would hang under UNION ALL) and greys the reachable set.
    assert set(result.stale_column_ids) == {b.id, c.id}
