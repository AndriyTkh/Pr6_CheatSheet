"""Shared route dependencies.

`resolve_sheet` is the important one: a grid route takes `sheet_id` from the
path and gets back the real sheet or a 404. Nesting rows/columns/cells under it
means "which sheet" is answered by the URL, not by a query parameter a client
can forget (§2a — a case has ≥1 sheet).
"""

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, Path, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import Sheet
from app.services import grid_query

DbSession = Annotated[AsyncSession, Depends(get_db)]


class Pagination(BaseModel):
    limit: int
    offset: int


def pagination(
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Pagination:
    return Pagination(limit=limit, offset=offset)


Paging = Annotated[Pagination, Depends(pagination)]


async def resolve_sheet(
    db: DbSession,
    sheet_id: Annotated[uuid.UUID, Path(description="The sheet the grid belongs to")],
) -> Sheet:
    sheet = await grid_query.get_sheet(db, sheet_id)
    if sheet is None:
        raise HTTPException(status_code=404, detail=f"No sheet {sheet_id}")
    return sheet


ScopedSheet = Annotated[Sheet, Depends(resolve_sheet)]
