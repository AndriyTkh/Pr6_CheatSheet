"""Row-producing recipe → persisted rows + cells. The week-1 gate path (§14).

`ProzorroLots.produce()` returns `ProducedRow`s that know nothing about the DB —
that is the §3 isolation rule. This module is the other half: it owns the
session, creates the connector columns, upserts the lot rows on their
`(tenderID, lotID)` provenance key (§16 #3), and writes one cell per slot —
**only where the §2 invariants say a cell may exist**.

Idempotent by design: re-running the same tender ids updates the same rows and
cells rather than duplicating them, which is what `row_lot_grain_uq` expects.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dag.invariants import cell_is_placeable
from app.models import Cell, Column, Row, Run, Sheet, cell_version_seq
from app.models.enums import RowOrigin
from app.recipes.base import ProducedRow, RowProducingRecipe
from app.recipes.registry import ensure_registered, recipe_uuid
from app.recipes.row_producing.prozorro_lots import ProzorroLots


@dataclass(slots=True)
class IngestResult:
    """What one row-producing run actually landed."""

    run_id: uuid.UUID
    columns: dict[str, Column] = field(default_factory=dict)
    rows_created: list[Row] = field(default_factory=list)
    rows_updated: list[Row] = field(default_factory=list)
    cells_written: int = 0
    #: (row, slot) pairs skipped because row.depth != column.target_depth — the
    #: §2a off-grain case. Not an error: an off-grain row simply has no cell.
    cells_skipped_off_grain: int = 0

    @property
    def rows(self) -> list[Row]:
        return [*self.rows_created, *self.rows_updated]


async def ensure_slot_columns(
    session: AsyncSession,
    sheet: Sheet,
    recipe: type[RowProducingRecipe] | RowProducingRecipe,
    *,
    target_depth: int = 0,
) -> dict[str, Column]:
    """One column per declared output slot, created once per sheet.

    Matched on `(sheet_id, recipe_id, output_slot)` rather than on the display
    name — the name is the journalist's to rename, `output_slot` is the cache-key
    term and the stable identity (§4 step 6).
    """
    cls = recipe if isinstance(recipe, type) else type(recipe)
    await ensure_registered(session, cls)
    rid = recipe_uuid(cls.id)

    existing_stmt = select(Column).where(
        Column.sheet_id == sheet.id,
        Column.recipe_id == rid,
        Column.recipe_version == cls.version,
    )
    by_slot = {
        c.output_slot: c
        for c in (await session.execute(existing_stmt)).scalars().all()
    }

    for position, out in enumerate(cls.outputs):
        if out.slot in by_slot:
            continue
        column = Column(
            case_id=sheet.case_id,
            sheet_id=sheet.id,
            name=out.description or out.slot,
            value_type=out.value_type,
            item_type=out.item_type,
            recipe_id=rid,
            recipe_version=cls.version,
            output_slot=out.slot,
            target_depth=target_depth,
            position=position,
        )
        session.add(column)
        by_slot[out.slot] = column

    await session.flush()
    return by_slot


async def ingest_produced_rows(
    session: AsyncSession,
    sheet: Sheet,
    recipe: type[RowProducingRecipe] | RowProducingRecipe,
    produced: Sequence[ProducedRow],
    *,
    run: Run | None = None,
    params: Mapping[str, Any] | None = None,
    origin: RowOrigin = RowOrigin.connector,
) -> IngestResult:
    """Persist `produced` onto `sheet`, cells included. Recipe-agnostic."""
    cls = recipe if isinstance(recipe, type) else type(recipe)
    columns = await ensure_slot_columns(session, sheet, cls)

    if run is None:
        run = Run(
            recipe_id=recipe_uuid(cls.id),
            recipe_version=cls.version,
            params_jsonb=dict(params or {}),
        )
        session.add(run)
        await session.flush()

    result = IngestResult(run_id=run.id, columns=columns)
    existing = await _rows_by_lot_key(session, sheet.id)

    for position, produced_row in enumerate(produced):
        key = _lot_key(produced_row.provenance)
        row = existing.get(key) if key is not None else None
        if row is None:
            row = Row(
                case_id=sheet.case_id,
                sheet_id=sheet.id,
                origin=origin,
                provenance_jsonb=dict(produced_row.provenance),
                parent_row_id=produced_row.parent_row_id,
                depth=produced_row.depth,
                ordinal=produced_row.ordinal,
                position=position,
            )
            session.add(row)
            await session.flush()
            if key is not None:
                existing[key] = row
            result.rows_created.append(row)
        else:
            # Re-sync of a tender we already hold: the key is stable, the values
            # are what may have moved (`dateModified` sync, §6a).
            row.provenance_jsonb = dict(produced_row.provenance)
            result.rows_updated.append(row)

        for slot, cell_result in produced_row.values.items():
            column = columns.get(slot)
            if column is None:
                continue  # a slot with no column on this sheet produces no cell
            if not cell_is_placeable(row, column):
                result.cells_skipped_off_grain += 1
                continue
            await _upsert_cell(session, row, column, cell_result, run.id)
            result.cells_written += 1

    await session.flush()
    return result


async def ingest_prozorro_lots(
    session: AsyncSession,
    sheet: Sheet,
    params: Mapping[str, Any],
    *,
    recipe: ProzorroLots | None = None,
) -> IngestResult:
    """The week-1 gate: Prozorro → lot rows on `@tenders`, cells filled (§14).

    Synchronous on purpose for week 1 — Procrastinate wiring is week 2, and the
    gate is about the loop existing end to end, not about where it runs.
    """
    recipe = recipe or ProzorroLots()
    produced = await recipe.produce(sheet.case_id, sheet.id, params)
    return await ingest_produced_rows(
        session, sheet, recipe, produced, params=params
    )


# ---------------------------------------------------------------------


def _lot_key(provenance: Mapping[str, Any]) -> tuple[str, str | None] | None:
    """The `row_lot_grain_uq` key, or None for rows that carry no `tenderID`."""
    tender_id = provenance.get("tenderID")
    if not tender_id:
        return None
    return (str(tender_id), provenance.get("lotID"))


async def _rows_by_lot_key(
    session: AsyncSession, sheet_id: uuid.UUID
) -> dict[tuple[str, str | None], Row]:
    stmt = select(Row).where(Row.sheet_id == sheet_id, Row.tender_id.is_not(None))
    rows = (await session.execute(stmt)).scalars().all()
    return {(row.tender_id, row.lot_id): row for row in rows}  # type: ignore[misc]


async def _upsert_cell(
    session: AsyncSession,
    row: Row,
    column: Column,
    cell_result: Any,
    run_id: uuid.UUID,
) -> Cell:
    cell = await session.get(Cell, (row.id, column.id))
    if cell is None:
        cell = Cell(row_id=row.id, column_id=column.id)
        session.add(cell)
    cell.value_jsonb = cell_result.value
    cell.status = cell_result.status
    cell.citation_jsonb = cell_result.citation_jsonb()
    cell.run_id = run_id
    # §4 step 7 — every write advances the stream version the reconnect
    # endpoint (`?since=`) pages on.
    cell.version = cell_version_seq.next_value()
    await session.flush()
    return cell
