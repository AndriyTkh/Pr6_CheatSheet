"""§4 step 7 — reconcile-on-reconnect (`GET /case/:id/cells?since=<version>`).

The live SSE stream has no replay of its own and drops updates for a disconnected
client. This endpoint is what makes that safe: on reconnect the client pages every
terminal cell that advanced past the last version it saw. So the load-bearing
assertion, named in the Verify line, is
`test_since_returns_every_cell_written_while_disconnected`: cells that filled
during the disconnect are **all** returned by `?since=`, none silently lost.

Everything else guards the corners of that guarantee — the same monotonic version
the stream pages on, terminal-only (the stream carries nothing else), case
scoping across sheets, and the ordered response the handler shapes.

Layered like `test_sse.py`: the route-registration check is pure; the query and
handler behaviour need Postgres, behind `requires_db`.
"""

from __future__ import annotations

import uuid

import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.routes.reconcile import reconcile_cells
from app.models import Case, Cell, Column, Row, Sheet
from app.models.cell import cell_version_seq
from app.models.enums import CellStatus, RowOrigin, SheetKind
from app.services.reconcile import fetch_cells_since
from app.tests.conftest import TEST_DB_URL, requires_db


# =====================================================================
# Route wiring — pure, no database
# =====================================================================


def test_reconcile_route_is_registered():
    """The endpoint is in the OpenAPI paths Role 5 generates the client half from."""
    from app.main import app

    assert "/case/{case_id}/cells" in app.openapi()["paths"]


# =====================================================================
# DB-backed fixtures + seeding
# =====================================================================


@pytest_asyncio.fixture
async def db() -> AsyncSession:
    """A committing session; every case it creates is deleted on the way out."""
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


async def _make_case(db: AsyncSession) -> tuple[Case, Sheet]:
    case = Case(name="reconcile test", owner_id=uuid.uuid4())
    db.add(case)
    await db.flush()
    db.info["cases"].append(case.id)
    sheet = Sheet(
        case_id=case.id, name="Тендери", kind=SheetKind.source, grain_label="lot"
    )
    db.add(sheet)
    await db.flush()
    return case, sheet


async def _terminal_cell(
    db: AsyncSession,
    case: Case,
    sheet: Sheet,
    *,
    status: CellStatus = CellStatus.Answered,
) -> Cell:
    """A fresh (row, column, terminal cell) on `sheet`. Cell gets the next seq version."""
    row = Row(
        case_id=case.id,
        sheet_id=sheet.id,
        origin=RowOrigin.connector,
        provenance_jsonb={"tenderID": uuid.uuid4().hex, "lotID": "lot-1"},
        depth=0,
    )
    column = Column(
        case_id=case.id,
        sheet_id=sheet.id,
        name="winner",
        value_type="text",
        target_depth=0,
    )
    db.add_all([row, column])
    await db.flush()
    cell = Cell(row_id=row.id, column_id=column.id, status=status)
    db.add(cell)
    await db.flush()
    await db.refresh(cell, ["version"])  # server-default seq value, read it back
    return cell


async def _rewrite_cell(db: AsyncSession, cell: Cell, status: CellStatus) -> None:
    """Simulate a fresh terminal write to an existing cell: new status, new version.

    Mirrors what the wavefront does on a re-run — bump `cell_version_seq` so the
    cell re-enters the stream's number line above anything the client has seen.
    """
    cell.status = status
    cell.version = await db.scalar(select(cell_version_seq.next_value()))
    await db.flush()


# =====================================================================
# The Verify assertion — ALL disconnect-window writes are returned
# =====================================================================


@requires_db
async def test_since_returns_every_cell_written_while_disconnected(db: AsyncSession):
    """Cells that fill during a disconnect are all caught by one `?since=` fetch.

    Nothing silently lost across the gap — the whole point of the endpoint.
    """
    case, sheet = await _make_case(db)

    # Cells the client saw before it dropped. Its cursor is the max version seen.
    seen = [await _terminal_cell(db, case, sheet) for _ in range(3)]
    cursor = max(cell.version for cell in seen)

    # ---- client is disconnected here (broker dropped its live updates) ----
    filled = [await _terminal_cell(db, case, sheet) for _ in range(5)]
    # ...and one already-seen cell is re-run to a new terminal status + version.
    await _rewrite_cell(db, seen[0], CellStatus.NotFound)

    # ---- client reconnects: exactly one reconcile fetch on its cursor ----
    replayed = await fetch_cells_since(db, case.id, cursor)

    replayed_keys = {(c.row_id, c.column_id) for c in replayed}
    expected_keys = {(c.row_id, c.column_id) for c in filled}
    expected_keys.add((seen[0].row_id, seen[0].column_id))  # the re-run cell

    assert replayed_keys == expected_keys, "a disconnect-window write was lost"
    assert len(replayed) == len(expected_keys)  # each cell once, no duplicates
    # cursor only advances — every replayed version is strictly past it
    assert all(c.version > cursor for c in replayed)
    # ...and the untouched already-seen cells are NOT replayed
    assert seen[1].version <= cursor and seen[2].version <= cursor


@requires_db
async def test_since_returns_cells_ordered_by_version(db: AsyncSession):
    """The stream pages by version, so reconcile must too — ascending, monotonic."""
    case, sheet = await _make_case(db)
    for _ in range(6):
        await _terminal_cell(db, case, sheet)

    replayed = await fetch_cells_since(db, case.id, 0)

    versions = [c.version for c in replayed]
    assert versions == sorted(versions)
    assert len(set(versions)) == len(versions)  # strictly increasing, no ties


@requires_db
async def test_since_zero_returns_the_whole_case(db: AsyncSession):
    """A client with no prior cursor (`since=0`) catches up on every terminal cell."""
    case, sheet = await _make_case(db)
    cells = [await _terminal_cell(db, case, sheet) for _ in range(4)]

    replayed = await fetch_cells_since(db, case.id, 0)

    assert {(c.row_id, c.column_id) for c in replayed} == {
        (c.row_id, c.column_id) for c in cells
    }


# =====================================================================
# The corners: terminal-only, case scoping, sheet routing
# =====================================================================


@requires_db
async def test_non_terminal_cells_are_not_replayed(db: AsyncSession):
    """A `blocked`/`running` cell is not on the stream, so reconcile must skip it.

    Otherwise the client would apply an update the live stream never sends, and the
    two would disagree about the number line.
    """
    case, sheet = await _make_case(db)
    answered = await _terminal_cell(db, case, sheet, status=CellStatus.Answered)
    await _terminal_cell(db, case, sheet, status=CellStatus.blocked)
    await _terminal_cell(db, case, sheet, status=CellStatus.running)

    replayed = await fetch_cells_since(db, case.id, 0)

    assert [(c.row_id, c.column_id) for c in replayed] == [
        (answered.row_id, answered.column_id)
    ]


@requires_db
async def test_reconcile_is_scoped_to_the_case(db: AsyncSession):
    """A cell in another case never leaks into this case's catch-up."""
    case_a, sheet_a = await _make_case(db)
    case_b, sheet_b = await _make_case(db)
    mine = await _terminal_cell(db, case_a, sheet_a)
    await _terminal_cell(db, case_b, sheet_b)

    replayed = await fetch_cells_since(db, case_a.id, 0)

    assert [(c.row_id, c.column_id) for c in replayed] == [
        (mine.row_id, mine.column_id)
    ]


@requires_db
async def test_replayed_cell_carries_its_sheet_id(db: AsyncSession):
    """Each entry names its sheet, so the client routes it to the right grid — even
    a sheet created (Expand `new_table`) while it was disconnected."""
    case, sheet = await _make_case(db)
    await _terminal_cell(db, case, sheet)

    (replayed,) = await fetch_cells_since(db, case.id, 0)

    assert replayed.sheet_id == sheet.id
    assert replayed.as_dict()["sheet_id"] == str(sheet.id)


# =====================================================================
# The HTTP handler — response shape + cursor advance
# =====================================================================


@requires_db
async def test_handler_returns_updates_and_advances_the_cursor(db: AsyncSession):
    """The route returns the SSE-compatible envelope; `max_version` is the new cursor."""
    case, sheet = await _make_case(db)
    cells = [await _terminal_cell(db, case, sheet) for _ in range(3)]
    top = max(c.version for c in cells)

    payload = await reconcile_cells(case_id=case.id, since=0, session=db)

    assert payload["since"] == 0
    assert payload["max_version"] == top
    assert len(payload["updates"]) == 3
    assert {u["row_id"] for u in payload["updates"]} == {str(c.row_id) for c in cells}
    # every update carries the full wire shape the grid applies in place
    first = payload["updates"][0]
    assert set(first) == {"sheet_id", "row_id", "column_id", "version", "status"}


@requires_db
async def test_handler_holds_the_cursor_when_nothing_advanced(db: AsyncSession):
    """An empty catch-up returns `max_version == since` — the cursor never rewinds."""
    case, _ = await _make_case(db)

    payload = await reconcile_cells(case_id=case.id, since=999_999, session=db)

    assert payload["updates"] == []
    assert payload["max_version"] == 999_999
