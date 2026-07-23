"""Cells — the values, scoped through both ends to one sheet (§4, §5, §9)."""

import uuid

from fastapi import APIRouter, HTTPException

from app.api.deps import DbSession, Paging, ScopedSheet
from app.models import Cell, Column, Row
from app.schemas import CellOut, Page
from app.services import grid_query

router = APIRouter(prefix="/sheets/{sheet_id}/cells", tags=["cells"])


@router.get("", response_model=Page[CellOut], summary="List a sheet's cells")
async def list_cells(db: DbSession, sheet: ScopedSheet, paging: Paging) -> Page[CellOut]:
    """Ordered by `version`, the same monotonic counter the live stream uses,
    so a page boundary and a stream resume point mean the same thing."""
    stmt = grid_query.cells_of_sheet(sheet.id)
    total = await grid_query.count_of(db, stmt)
    result = await db.scalars(stmt.limit(paging.limit).offset(paging.offset))
    return Page[CellOut](
        items=[CellOut.model_validate(c) for c in result],
        total=total,
        limit=paging.limit,
        offset=paging.offset,
    )


@router.get(
    "/{row_id}/{column_id}",
    response_model=CellOut,
    summary="Get one cell on this sheet",
)
async def get_cell(
    db: DbSession, sheet: ScopedSheet, row_id: uuid.UUID, column_id: uuid.UUID
) -> CellOut:
    """404 also covers the legal-but-empty case: off-grain intersections have no
    cell at all (§2a), which is a fact about the grid, not a missing result."""
    cell = await db.get(Cell, (row_id, column_id))
    if cell is None:
        raise HTTPException(
            status_code=404, detail=f"No cell ({row_id}, {column_id}) on sheet {sheet.id}"
        )
    # Both ends must be on this sheet — invariant 2 (§2) says they agree, and a
    # check on only one end would serve a violation instead of surfacing it.
    row = await db.get(Row, row_id)
    column = await db.get(Column, column_id)
    if (
        row is None
        or column is None
        or row.sheet_id != sheet.id
        or column.sheet_id != sheet.id
    ):
        raise HTTPException(
            status_code=404, detail=f"No cell ({row_id}, {column_id}) on sheet {sheet.id}"
        )
    return CellOut.model_validate(cell)
