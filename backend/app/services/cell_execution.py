"""One cell, executed. The body of the Procrastinate task (§4).

Split from `app/tasks/` on purpose (backend/CLAUDE.md layout): `tasks/` is the
transport — which worker picks the job up — and this is what running the job
actually means. A route that wants to run a cell synchronously (Preview, §4
step 4) calls the same function; it does not get a second, subtly different
execution path.

**`cell.status` is not a lock here.** The flip to `running` is a display write
for the grid, done *after* Procrastinate has already handed this worker the job
under `SKIP LOCKED`. Nothing in this module reads `cell.status` to decide
whether it may proceed, and nothing takes a row lock on `cell` — that is the
"two queues fighting" failure §4 names.

Transaction boundaries are owned here, and there are two on purpose: the claim
commits so the grid can show `running` while a slow recipe is in flight, and
the result commits at the end. A crash between them leaves the cell `running`
and the Procrastinate job retryable — the job, not the cell, is the truth.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any, Mapping

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dag.invariants import check_cell_placement
from app.models import Cell, Column, ColumnInput, Row, Run, cell_version_seq
from app.models.enums import TERMINAL, CellStatus
from app.recipes.base import CellResult, InputCell, Recipe, RowContext
from app.recipes.registry import ensure_registered, recipe_class

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ExecutionOutcome:
    """What one cell job did — returned to the task for the run log."""

    row_id: uuid.UUID
    column_id: uuid.UUID
    status: CellStatus | None
    run_id: uuid.UUID | None = None
    #: set when the job was a no-op (row/column deleted before the worker ran)
    skipped_reason: str | None = None

    @property
    def is_terminal(self) -> bool:
        return self.status is not None and self.status in TERMINAL

    def as_log(self) -> dict[str, Any]:
        return {
            "row_id": str(self.row_id),
            "column_id": str(self.column_id),
            "status": self.status.value if self.status else None,
            "run_id": str(self.run_id) if self.run_id else None,
            "skipped_reason": self.skipped_reason,
        }


async def execute_cell(
    session: AsyncSession,
    row_id: uuid.UUID,
    column_id: uuid.UUID,
    *,
    cache_bust: bool = False,
) -> ExecutionOutcome:
    """Claim → assemble `row_context` → run the recipe → write the cell.

    Commits. Never raises for a data problem: every failure mode becomes a typed
    terminal status on the cell, because a partial failure has to stay visible
    per cell rather than take the worker down (§4 step 7, §5).
    """
    row = await session.get(Row, row_id)
    column = await session.get(Column, column_id)
    if row is None or column is None:
        # The column was dropped (or the row merged) between enqueue and pick.
        # Not an error: the job is simply stale.
        return ExecutionOutcome(
            row_id, column_id, None, skipped_reason="row or column no longer exists"
        )

    # Assertion, not a user-facing rejection: the wavefront must never have
    # created this cell off-grain (§2a, invariants 2+3).
    check_cell_placement(row, column)

    cell = await _claim(session, row, column)

    recipe_cls = _resolve_recipe(column)
    if recipe_cls is None:
        return await _fail(
            session,
            cell,
            f"column {column.name!r} has no runnable recipe "
            f"({column.recipe_id}, v{column.recipe_version}) — nothing to dispatch",
        )

    row_context = await _assemble_row_context(session, row, column)
    run = await _open_run(session, recipe_cls, column, cache_bust=cache_bust)

    results = await recipe_cls().run(row_context, dict(column.params_jsonb or {}))
    result = _result_for_slot(results, column.output_slot)
    if result is None:
        return await _fail(
            session,
            cell,
            f"{recipe_cls.name} produced no value for output_slot "
            f"{column.output_slot!r} — the column and the recipe disagree (§4 step6)",
            run_id=run.id,
        )

    _write(cell, result, run.id)
    await session.commit()
    return ExecutionOutcome(row_id, column_id, cell.status, run_id=run.id)


# ---------------------------------------------------------------------
# Claim / write
# ---------------------------------------------------------------------


async def _claim(session: AsyncSession, row: Row, column: Column) -> Cell:
    """Flip the cell to `running` — display only, no lock, no `FOR UPDATE`.

    The cell may not exist yet (a Preview path can run a cell the wavefront
    never inserted), so this creates it rather than requiring one.
    """
    cell = await session.get(Cell, (row.id, column.id))
    if cell is None:
        cell = Cell(row_id=row.id, column_id=column.id)
        session.add(cell)
    cell.status = CellStatus.running
    cell.version = cell_version_seq.next_value()
    await session.commit()
    return cell


def _write(cell: Cell, result: CellResult, run_id: uuid.UUID | None) -> None:
    """§4: on finish, Procrastinate's task writes value + status + citation + run_id."""
    cell.value_jsonb = result.value
    cell.status = result.status
    cell.citation_jsonb = result.citation_jsonb()
    cell.run_id = run_id
    # §4 step 7 — every write advances the version the reconnect endpoint pages on.
    cell.version = cell_version_seq.next_value()
    # cache_key stays NULL: §4 step 6 is the *next* task's, and a NULL key means
    # "not hittable", which is the safe default until it is computed.


async def _fail(
    session: AsyncSession,
    cell: Cell,
    message: str,
    *,
    run_id: uuid.UUID | None = None,
) -> ExecutionOutcome:
    """An engine-side problem becomes `Error` on the cell, never a dead worker."""
    logger.error("cell(%s, %s): %s", cell.row_id, cell.column_id, message)
    _write(
        cell,
        CellResult(slot="", value=None, status=CellStatus.Error, message=message),
        run_id,
    )
    await session.commit()
    return ExecutionOutcome(cell.row_id, cell.column_id, CellStatus.Error, run_id=run_id)


# ---------------------------------------------------------------------
# Context assembly
# ---------------------------------------------------------------------


async def _assemble_row_context(
    session: AsyncSession, row: Row, column: Column
) -> RowContext:
    """Everything the recipe may see, and nothing else (§3 isolation, §11).

    Inputs are keyed by the input column's **name**, because `column_input`
    records the edge but not which declared `InputSpec` it satisfies — see the
    handoff note; if that binding ever gets a column, this is where it lands.
    """
    edge_stmt = (
        select(Column, ColumnInput.is_required)
        .join(ColumnInput, ColumnInput.input_column_id == Column.id)
        .where(ColumnInput.column_id == column.id)
    )
    inputs: dict[str, InputCell] = {}
    for input_column, _is_required in (await session.execute(edge_stmt)).all():
        cell = await session.get(Cell, (row.id, input_column.id))
        inputs[input_column.name] = InputCell(
            column_name=input_column.name,
            value=None if cell is None else cell.value_jsonb,
            # No cell at all reads as `InsufficientData` — a missing input is
            # terminal-empty, which is exactly what the dead-end lock wants (§6).
            status=CellStatus.InsufficientData if cell is None else cell.status,
            citations=[] if cell is None else list(cell.citation_jsonb or []),
        )
        # `output_slot` alias, when it doesn't shadow a real column name — lets a
        # recipe declare inputs by slot instead of by the journalist's rename.
        slot = input_column.output_slot
        if slot and slot not in inputs:
            inputs[slot] = inputs[input_column.name]

    return RowContext(
        row_id=row.id,
        sheet_id=row.sheet_id,
        depth=row.depth,
        provenance=dict(row.provenance_jsonb or {}),
        inputs=inputs,
        documents=(),  # §11 `external_ok` gating is a week-4 task; nothing passes yet
    )


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------


def _resolve_recipe(column: Column) -> type[Recipe] | None:
    if column.recipe_id is None or column.recipe_version is None:
        return None
    return recipe_class(column.recipe_id, column.recipe_version)


async def _open_run(
    session: AsyncSession,
    recipe_cls: type[Recipe],
    column: Column,
    *,
    cache_bust: bool,
) -> Run:
    """§10 — one `run` row per dispatched execution, before the recipe touches anything."""
    await ensure_registered(session, recipe_cls)
    run = Run(
        recipe_id=_recipe_id(column, recipe_cls),
        recipe_version=recipe_cls.version,
        params_jsonb=dict(column.params_jsonb or {}),
        cache_bust=cache_bust,
    )
    session.add(run)
    await session.flush()
    return run


def _recipe_id(column: Column, recipe_cls: type[Recipe]) -> uuid.UUID:
    from app.recipes.registry import recipe_uuid

    return column.recipe_id or recipe_uuid(recipe_cls.id)


def _result_for_slot(
    results: Mapping[str, CellResult] | list[CellResult], slot: str
) -> CellResult | None:
    """A 1→M recipe returns M results; this column owns exactly one of them.

    The other slots belong to *other* columns with their own cells and their own
    cache keys (`output_slot` is a cache-key term precisely so they don't
    collide, §4 step 6) — so this deliberately does not fan out and write them.
    """
    for result in results:  # type: ignore[union-attr]
        if result.slot == slot:
            return result
    return None
