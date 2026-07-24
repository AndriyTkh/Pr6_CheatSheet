"""Rows — always addressed under their sheet (§2a).

There is no `/rows/{row_id}`. A row id is unique, so such a route would work,
and that is precisely the problem: it would let a client hold rows without
holding the sheet they belong to, which is how one-grid-per-case comes back.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import or_, select

from app.api.deps import DbSession, Paging, ScopedSheet
from app.models import Row, RowLink, Sheet
from app.schemas import DocumentOut, Page, RowLinkOut, RowOut
from app.services import grid_query

router = APIRouter(prefix="/sheets/{sheet_id}/rows", tags=["rows"])


async def _row_on_sheet(db: DbSession, sheet: Sheet, row_id: uuid.UUID) -> Row:
    """A row, or a 404 — including when it exists on a *different* sheet."""
    row = await db.get(Row, row_id)
    if row is None or row.sheet_id != sheet.id:
        raise HTTPException(status_code=404, detail=f"No row {row_id} on sheet {sheet.id}")
    return row


@router.get("", response_model=Page[RowOut], summary="List a sheet's rows")
async def list_rows(
    db: DbSession,
    sheet: ScopedSheet,
    paging: Paging,
    depth: Annotated[
        int | None,
        Query(description="Restrict to one grain: 0 = source rows, 1 = expanded children"),
    ] = None,
) -> Page[RowOut]:
    stmt = grid_query.rows_of_sheet(sheet.id, depth=depth)
    total = await grid_query.count_of(db, stmt)
    result = await db.scalars(stmt.limit(paging.limit).offset(paging.offset))
    return Page[RowOut](
        items=[RowOut.model_validate(r) for r in result],
        total=total,
        limit=paging.limit,
        offset=paging.offset,
    )


@router.get("/{row_id}", response_model=RowOut, summary="Get one row on this sheet")
async def get_row(db: DbSession, sheet: ScopedSheet, row_id: uuid.UUID) -> RowOut:
    return RowOut.model_validate(await _row_on_sheet(db, sheet, row_id))


@router.get(
    "/{row_id}/links",
    response_model=list[RowLinkOut],
    summary="Lineage links touching this row",
)
async def list_row_links(
    db: DbSession, sheet: ScopedSheet, row_id: uuid.UUID
) -> list[RowLinkOut]:
    """§2a N-ary lineage, both directions.

    Both ends are returned because the interesting question differs by sheet: on
    a Companies sheet you ask "which lots did this company bid on" (the row is
    the child); on `@tenders` you ask "which companies came out of this lot"
    (the row is the parent). One route answers both.
    """
    await _row_on_sheet(db, sheet, row_id)
    stmt = select(RowLink).where(
        or_(RowLink.child_row_id == row_id, RowLink.parent_row_id == row_id)
    )
    result = await db.scalars(stmt)
    return [RowLinkOut.model_validate(link) for link in result]


@router.get(
    "/{row_id}/documents",
    response_model=list[DocumentOut],
    summary="Source documents attached to this row",
)
async def list_row_documents(
    db: DbSession, sheet: ScopedSheet, row_id: uuid.UUID
) -> list[DocumentOut]:
    await _row_on_sheet(db, sheet, row_id)
    result = await db.scalars(grid_query.documents_of_row(row_id))
    return [DocumentOut.model_validate(d) for d in result]
