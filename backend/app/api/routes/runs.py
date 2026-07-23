"""§10 provenance log — what produced a value, at what cost, with which model.

`run` has no `case_id` column, so "the runs of a case" is not a query the schema
supports. It is reachable per sheet instead, through the cells the runs filled —
which is also the question the journalist actually asks ("what produced this
grid"). Widening that would need a migration, not a route (CLAUDE.md §5).
"""

import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.deps import DbSession, Paging, ScopedSheet
from app.models import Cell, Column, Row, Run
from app.schemas import Page, RunOut
from app.services import grid_query

router = APIRouter(tags=["runs"])


@router.get(
    "/sheets/{sheet_id}/runs",
    response_model=Page[RunOut],
    summary="Runs that produced cells on this sheet",
)
async def list_sheet_runs(
    db: DbSession, sheet: ScopedSheet, paging: Paging
) -> Page[RunOut]:
    stmt = (
        select(Run)
        .join(Cell, Cell.run_id == Run.id)
        .join(Row, Row.id == Cell.row_id)
        .join(Column, Column.id == Cell.column_id)
        .where(Row.sheet_id == sheet.id, Column.sheet_id == sheet.id)
        .distinct()
        .order_by(Run.created_at.desc())
    )
    total = await grid_query.count_of(db, stmt)
    result = await db.scalars(stmt.limit(paging.limit).offset(paging.offset))
    return Page[RunOut](
        items=[RunOut.model_validate(r) for r in result],
        total=total,
        limit=paging.limit,
        offset=paging.offset,
    )


@router.get("/runs/{run_id}", response_model=RunOut, summary="Get one run")
async def get_run(db: DbSession, run_id: uuid.UUID) -> RunOut:
    run = await db.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"No run {run_id}")
    return RunOut.model_validate(run)
