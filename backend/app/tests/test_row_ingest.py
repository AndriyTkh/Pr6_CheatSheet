"""The week-1 gate path (§14): produce() → rows + cells on the source sheet.

DB-backed — skips without `CS_TEST_DATABASE_URL`. The connector is stubbed with
the recorded payload from `test_prozorro_connector.py`; nothing here hits the
network, so what is under test is purely the persistence half: the lot-grain
key, the §2 invariants at cell-write time, and idempotency on re-run.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models import Cell, Column, Row, Run
from app.models.enums import CellStatus, RowOrigin
from app.recipes.registry import get_registered, recipe_uuid
from app.recipes.row_producing.prozorro_lots import (
    SLOT_AMOUNT,
    SLOT_PARTICIPANTS,
    SLOT_TENDER,
    SLOT_WINNER,
    ProzorroLots,
)
from app.services import ingest_prozorro_lots
from app.tests.conftest import requires_db
from app.tests.test_prozorro_connector import TENDER_WITH_LOTS, TENDER_WITHOUT_LOTS

pytestmark = requires_db

PARAMS = {"tender_ids": ["UA-2026-01-01-000001"]}


class StubClient:
    """`lot_rows()` is the whole surface `ProzorroLots.produce()` touches."""

    def __init__(self, *tenders):
        self._tenders = tenders

    async def lot_rows(self, tender_id):
        from app.connectors.prozorro import extract_lot_rows

        rows = []
        for tender in self._tenders:
            rows.extend(extract_lot_rows(tender))
        return rows

    async def aclose(self):  # pragma: no cover - the recipe owns no stub client
        pass


@pytest.fixture
def recipe():
    return ProzorroLots(client=StubClient(TENDER_WITH_LOTS))


async def test_one_row_per_lot_lands_on_the_sheet(session, source_sheet, recipe):
    """§16 #3 — two lots in, two rows out, keyed on `(tenderID, lotID)`."""
    result = await ingest_prozorro_lots(session, source_sheet, PARAMS, recipe=recipe)

    assert len(result.rows_created) == 2
    assert not result.rows_updated
    assert sorted(r.lot_id for r in result.rows_created) == ["lot-1", "lot-2"]
    assert {r.tender_id for r in result.rows_created} == {"UA-2026-01-01-000001"}
    assert all(r.origin is RowOrigin.connector for r in result.rows_created)
    assert all(r.depth == 0 for r in result.rows_created)
    assert all(r.sheet_id == source_sheet.id for r in result.rows_created)


async def test_generated_lot_columns_come_from_the_provenance(
    session, source_sheet, recipe
):
    """`tender_id`/`lot_id` are GENERATED — the ORM writes provenance only."""
    result = await ingest_prozorro_lots(session, source_sheet, PARAMS, recipe=recipe)
    row = result.rows_created[0]
    await session.refresh(row)
    assert row.tender_id == row.provenance_jsonb["tenderID"]
    assert row.lot_id == row.provenance_jsonb["lotID"]


async def test_a_column_is_created_per_output_slot(session, source_sheet, recipe):
    result = await ingest_prozorro_lots(session, source_sheet, PARAMS, recipe=recipe)

    assert set(result.columns) == {o.slot for o in ProzorroLots.outputs}
    participants = result.columns[SLOT_PARTICIPANTS]
    assert participants.value_type == "list"
    assert participants.item_type == "identifier"
    assert participants.is_list
    assert all(c.target_depth == 0 for c in result.columns.values())
    assert all(c.sheet_id == source_sheet.id for c in result.columns.values())


async def test_the_recipe_version_is_registered_and_linked(
    session, source_sheet, recipe
):
    """§10 — the run and every column point at the exact recipe version."""
    result = await ingest_prozorro_lots(session, source_sheet, PARAMS, recipe=recipe)

    registered = await get_registered(session, ProzorroLots.id, ProzorroLots.version)
    assert registered is not None
    assert registered.id == recipe_uuid(ProzorroLots.id)

    run = await session.get(Run, result.run_id)
    assert run.recipe_id == registered.id
    assert run.recipe_version == ProzorroLots.version
    assert run.params_jsonb == PARAMS
    assert all(c.recipe_id == registered.id for c in result.columns.values())


async def test_cells_are_written_with_status_and_citations(
    session, source_sheet, recipe
):
    result = await ingest_prozorro_lots(session, source_sheet, PARAMS, recipe=recipe)
    assert result.cells_written == len(result.rows_created) * len(ProzorroLots.outputs)
    assert result.cells_skipped_off_grain == 0

    lot1 = next(r for r in result.rows_created if r.lot_id == "lot-1")
    winner = await session.get(Cell, (lot1.id, result.columns[SLOT_WINNER].id))
    assert winner.status is CellStatus.Answered
    assert winner.value_jsonb == "12345678"
    assert winner.citation_jsonb and winner.citation_jsonb[0]["source_type"] == "api"
    assert winner.run_id == result.run_id
    assert winner.version is not None

    amount = await session.get(Cell, (lot1.id, result.columns[SLOT_AMOUNT].id))
    assert amount.value_jsonb == {"amount": 1000.0, "currency": "UAH"}


async def test_a_cancelled_award_is_not_found_not_answered(
    session, source_sheet, recipe
):
    """§5 — uncertainty is data. lot-2's only award is cancelled."""
    result = await ingest_prozorro_lots(session, source_sheet, PARAMS, recipe=recipe)
    lot2 = next(r for r in result.rows_created if r.lot_id == "lot-2")

    winner = await session.get(Cell, (lot2.id, result.columns[SLOT_WINNER].id))
    assert winner.status is CellStatus.NotFound
    assert winner.value_jsonb is None


async def test_an_out_of_scope_winner_is_not_applicable(session, source_sheet):
    """§16 #9 — a non-UA-EDR bidder is structurally void, never NotFound."""
    recipe = ProzorroLots(client=StubClient(TENDER_WITHOUT_LOTS))
    result = await ingest_prozorro_lots(session, source_sheet, PARAMS, recipe=recipe)

    [row] = result.rows_created
    assert row.lot_id is None  # a tender with no lots is still exactly one row
    winner = await session.get(Cell, (row.id, result.columns[SLOT_WINNER].id))
    assert winner.status is CellStatus.NotApplicable


async def test_an_empty_participant_list_is_an_answer(session, source_sheet):
    """§5/§2a — "we looked, there are none" is Answered with `[]`, not empty."""
    recipe = ProzorroLots(client=StubClient(TENDER_WITHOUT_LOTS))
    result = await ingest_prozorro_lots(session, source_sheet, PARAMS, recipe=recipe)

    [row] = result.rows_created
    cell = await session.get(Cell, (row.id, result.columns[SLOT_PARTICIPANTS].id))
    assert cell.status is CellStatus.Answered
    assert cell.value_jsonb == []


async def test_rerun_updates_in_place_and_bumps_the_version(
    session, source_sheet, recipe
):
    """Idempotent on the lot key — `row_lot_grain_uq` would reject a duplicate."""
    first = await ingest_prozorro_lots(session, source_sheet, PARAMS, recipe=recipe)
    lot1 = next(r for r in first.rows_created if r.lot_id == "lot-1")
    cell = await session.get(Cell, (lot1.id, first.columns[SLOT_TENDER].id))
    await session.refresh(cell)
    version_before = cell.version

    second = await ingest_prozorro_lots(
        session, source_sheet, PARAMS, recipe=ProzorroLots(StubClient(TENDER_WITH_LOTS))
    )
    assert not second.rows_created
    assert len(second.rows_updated) == 2
    assert set(second.columns) == set(first.columns)

    rows = (
        (await session.execute(select(Row).where(Row.sheet_id == source_sheet.id)))
        .scalars()
        .all()
    )
    assert len(rows) == 2

    # §4 step 7 — the reconnect endpoint pages on a strictly increasing version.
    await session.refresh(cell)
    assert cell.version > version_before


async def test_no_duplicate_columns_on_rerun(session, source_sheet, recipe):
    await ingest_prozorro_lots(session, source_sheet, PARAMS, recipe=recipe)
    await ingest_prozorro_lots(
        session, source_sheet, PARAMS, recipe=ProzorroLots(StubClient(TENDER_WITH_LOTS))
    )
    columns = (
        (await session.execute(select(Column).where(Column.sheet_id == source_sheet.id)))
        .scalars()
        .all()
    )
    assert len(columns) == len(ProzorroLots.outputs)


async def test_off_grain_rows_get_no_cell(session, source_sheet, recipe):
    """§2a invariant 3 — a depth-1 column produces no cell for a depth-0 row."""
    result = await ingest_prozorro_lots(session, source_sheet, PARAMS, recipe=recipe)
    for column in result.columns.values():
        column.target_depth = 1
    await session.flush()

    second = await ingest_prozorro_lots(
        session, source_sheet, PARAMS, recipe=ProzorroLots(StubClient(TENDER_WITH_LOTS))
    )
    # ensure_slot_columns matches on (sheet, recipe, slot), so the retargeted
    # columns are reused — and every cell is now off-grain.
    assert second.cells_written == 0
    assert second.cells_skipped_off_grain == len(result.rows_created) * len(
        ProzorroLots.outputs
    )
