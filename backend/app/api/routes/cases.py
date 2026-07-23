"""Cases and the sheets they hold (§2a, §11)."""

import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.deps import DbSession, Paging
from app.models import Case
from app.schemas import CaseOut, Page, SheetOut
from app.services import grid_query

router = APIRouter(prefix="/cases", tags=["cases"])


@router.get("", response_model=Page[CaseOut], summary="List cases")
async def list_cases(db: DbSession, paging: Paging) -> Page[CaseOut]:
    stmt = select(Case).order_by(Case.created_at.desc())
    total = await grid_query.count_of(db, stmt)
    result = await db.scalars(stmt.limit(paging.limit).offset(paging.offset))
    return Page[CaseOut](
        items=[CaseOut.model_validate(c) for c in result],
        total=total,
        limit=paging.limit,
        offset=paging.offset,
    )


@router.get("/{case_id}", response_model=CaseOut, summary="Get one case")
async def get_case(db: DbSession, case_id: uuid.UUID) -> CaseOut:
    case = await grid_query.get_case(db, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"No case {case_id}")
    return CaseOut.model_validate(case)


@router.get(
    "/{case_id}/sheets",
    response_model=list[SheetOut],
    summary="List the case's sheets",
)
async def list_sheets(db: DbSession, case_id: uuid.UUID) -> list[SheetOut]:
    """Every sheet in the case, in tab order.

    This is the entry point for the grid: a case is a *set* of sheets, so the
    client picks one here and then addresses rows/columns/cells under its id.
    Unpaginated on purpose — a case has a handful of sheets, not thousands.
    """
    if await grid_query.get_case(db, case_id) is None:
        raise HTTPException(status_code=404, detail=f"No case {case_id}")
    result = await db.scalars(grid_query.sheets_of_case(case_id))
    return [SheetOut.model_validate(s) for s in result]
