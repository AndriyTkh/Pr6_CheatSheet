"""One sheet, and the composite payload that paints it (§2a)."""

from fastapi import APIRouter, Query
from typing import Annotated

from app.api.deps import DbSession, Paging, ScopedSheet
from app.schemas import CellOut, ColumnOut, GridOut, RowOut, SheetOut
from app.services import grid_query

router = APIRouter(prefix="/sheets", tags=["sheets"])


@router.get("/{sheet_id}", response_model=SheetOut, summary="Get one sheet")
async def get_sheet(sheet: ScopedSheet) -> SheetOut:
    return SheetOut.model_validate(sheet)


@router.get(
    "/{sheet_id}/grid",
    response_model=GridOut,
    summary="Get a sheet's columns, rows and cells in one payload",
)
async def get_grid(
    db: DbSession,
    sheet: ScopedSheet,
    paging: Paging,
    depth: Annotated[
        int | None,
        Query(description="Restrict to one grain: 0 = source rows, 1 = expanded children"),
    ] = None,
) -> GridOut:
    """Everything needed to render this sheet, consistent at one moment.

    `cells` is sparse: a cell exists only where `row.depth == column.target_depth`
    (§2a), so an inline-expanded sheet legitimately has holes where a column does
    not run on that grain. Absent ≠ pending.

    Cells are fetched for the whole sheet, not just the returned row page — the
    pilot's scale is ~10–15k cells per case and slicing them per page would make
    the client reassemble what the server already knows.
    """
    columns = list(await db.scalars(grid_query.columns_of_sheet(sheet.id)))
    rows_stmt = grid_query.rows_of_sheet(sheet.id, depth=depth)
    row_total = await grid_query.count_of(db, rows_stmt)
    rows = list(
        await db.scalars(rows_stmt.limit(paging.limit).offset(paging.offset))
    )
    cells = list(await db.scalars(grid_query.cells_of_sheet(sheet.id)))

    return GridOut(
        sheet=SheetOut.model_validate(sheet),
        columns=[ColumnOut.model_validate(c) for c in columns],
        rows=[RowOut.model_validate(r) for r in rows],
        cells=[CellOut.model_validate(c) for c in cells],
        as_of_version=max((c.version for c in cells), default=0),
        row_total=row_total,
        row_limit=paging.limit,
        row_offset=paging.offset,
    )
