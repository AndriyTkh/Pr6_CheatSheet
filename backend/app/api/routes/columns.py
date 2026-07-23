"""Columns — the DAG nodes of one sheet (§4, §2a).

Sheet-scoped for the same reason as rows: a column belongs to exactly one
sheet's DAG, and the boundary between sheets is a real edge in the graph, not a
detail the client can flatten away.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import DbSession, Paging, ScopedSheet
from app.models import Column, Sheet
from app.schemas import ColumnInputOut, ColumnOut, Page
from app.services import grid_query

router = APIRouter(prefix="/sheets/{sheet_id}/columns", tags=["columns"])


async def _column_on_sheet(db: DbSession, sheet: Sheet, column_id: uuid.UUID) -> Column:
    column = await db.get(Column, column_id)
    if column is None or column.sheet_id != sheet.id:
        raise HTTPException(
            status_code=404, detail=f"No column {column_id} on sheet {sheet.id}"
        )
    return column


@router.get("", response_model=Page[ColumnOut], summary="List a sheet's columns")
async def list_columns(
    db: DbSession,
    sheet: ScopedSheet,
    paging: Paging,
    target_depth: Annotated[
        int | None, Query(description="Only columns that run on this grain (§2a)")
    ] = None,
) -> Page[ColumnOut]:
    stmt = grid_query.columns_of_sheet(sheet.id, target_depth=target_depth)
    total = await grid_query.count_of(db, stmt)
    result = await db.scalars(stmt.limit(paging.limit).offset(paging.offset))
    return Page[ColumnOut](
        items=[ColumnOut.model_validate(c) for c in result],
        total=total,
        limit=paging.limit,
        offset=paging.offset,
    )


@router.get(
    "/{column_id}", response_model=ColumnOut, summary="Get one column on this sheet"
)
async def get_column(
    db: DbSession, sheet: ScopedSheet, column_id: uuid.UUID
) -> ColumnOut:
    return ColumnOut.model_validate(await _column_on_sheet(db, sheet, column_id))


@router.get(
    "/{column_id}/inputs",
    response_model=list[ColumnInputOut],
    summary="The DAG edges feeding this column",
)
async def list_column_inputs(
    db: DbSession, sheet: ScopedSheet, column_id: uuid.UUID
) -> list[ColumnInputOut]:
    """Input columns may live on a parent sheet — the DAG spans the sheet
    boundary (§2a), so an edge's `input_column_id` is not guaranteed to be on
    this sheet. Only the *dependent* column is scoped here."""
    await _column_on_sheet(db, sheet, column_id)
    result = await db.scalars(grid_query.inputs_of_column(column_id))
    return [ColumnInputOut.model_validate(edge) for edge in result]
