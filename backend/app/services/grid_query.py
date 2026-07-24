"""Read queries behind the grid routes — the one place sheet scoping is written.

Every listing here takes a `sheet_id` and filters on it. That is deliberate and
structural: a case has ≥1 sheet (§2a), so "the rows of a case" is not a question
with one answer, and a helper that answered it anyway would let one-grid-per-case
back into the API through the side door.

Cells are scoped through **both** ends — `row.sheet_id` and `column.sheet_id` —
because invariant 2 (§2, app-side) says the two must agree, and a query that
trusts only one end silently returns the violation instead of hiding it.
"""

import uuid

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Case, Cell, Column, ColumnInput, Document, Row, Sheet


async def count_of(db: AsyncSession, stmt: Select) -> int:
    """Total rows a listing would return, ignoring limit/offset."""
    return await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0


async def get_case(db: AsyncSession, case_id: uuid.UUID) -> Case | None:
    return await db.get(Case, case_id)


async def get_sheet(db: AsyncSession, sheet_id: uuid.UUID) -> Sheet | None:
    return await db.get(Sheet, sheet_id)


def sheets_of_case(case_id: uuid.UUID) -> Select:
    return (
        select(Sheet).where(Sheet.case_id == case_id).order_by(Sheet.position, Sheet.name)
    )


def rows_of_sheet(sheet_id: uuid.UUID, depth: int | None = None) -> Select:
    """Rows of one sheet, in grid order.

    `depth` filters to one grain: an inline-expanded sheet holds parents
    (depth 0) and their children (depth 1) in the same sheet (§2a), and a
    caller rendering one grain wants exactly one of them.

    Order is `(position, ordinal)` so an expanded child band stays under its
    parent and in source-array order — `ordinal` is what carries the item's
    citation, so re-sorting it away loses the link to the evidence.
    """
    stmt = select(Row).where(Row.sheet_id == sheet_id)
    if depth is not None:
        stmt = stmt.where(Row.depth == depth)
    return stmt.order_by(Row.position, Row.ordinal.nulls_first(), Row.created_at)


def columns_of_sheet(sheet_id: uuid.UUID, target_depth: int | None = None) -> Select:
    stmt = select(Column).where(Column.sheet_id == sheet_id)
    if target_depth is not None:
        stmt = stmt.where(Column.target_depth == target_depth)
    return stmt.order_by(Column.position, Column.created_at)


def cells_of_sheet(sheet_id: uuid.UUID) -> Select:
    """Cells whose row *and* column both live on this sheet."""
    return (
        select(Cell)
        .join(Row, Row.id == Cell.row_id)
        .join(Column, Column.id == Cell.column_id)
        .where(Row.sheet_id == sheet_id, Column.sheet_id == sheet_id)
        .order_by(Cell.version)
    )


def inputs_of_column(column_id: uuid.UUID) -> Select:
    """The DAG edges feeding one column (§4)."""
    return select(ColumnInput).where(ColumnInput.column_id == column_id)


def documents_of_case(case_id: uuid.UUID) -> Select:
    return select(Document).where(Document.case_id == case_id).order_by(
        Document.created_at
    )


def documents_of_row(row_id: uuid.UUID) -> Select:
    return select(Document).where(Document.row_id == row_id).order_by(Document.created_at)
