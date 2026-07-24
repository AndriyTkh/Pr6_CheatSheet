"""Reconcile-on-reconnect query (§4 step 7).

The live SSE stream (`realtime/`) has **no replay of its own** and deliberately
drops updates for a slow or disconnected client (broker overflow, SSE handoff).
This is the recovery path: given the last `cell.version` a client saw, return
every terminal cell in the case that has advanced past it, ordered by that same
monotonic version the stream pages on. The two share one number line — a cell
that filled during a multi-minute disconnect is caught here, never silently lost.

Scope: the whole case, across every sheet (`§2a` — a case holds ≥1 sheet). The
grid routes scope by `sheet_id`; a reconnect catches the whole case up in one
fetch, so each returned cell carries its own `sheet_id` (via `row.sheet_id`) for
the client to route it to the right grid — including a sheet an Expand `new_table`
created while the client was away.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Cell, Row
from app.models.enums import TERMINAL


@dataclass(frozen=True, slots=True)
class ReconciledCell:
    """One terminal cell to replay on reconnect.

    A superset of the SSE `CellUpdate` wire shape: same `(row_id, column_id,
    version, status)` the grid applies in place, plus `sheet_id` so a client can
    route a cell that filled on a sheet it had not loaded before the disconnect.
    """

    sheet_id: uuid.UUID
    row_id: uuid.UUID
    column_id: uuid.UUID
    #: `cell.version` — the reconcile cursor, strictly monotonic, never decreases.
    version: int
    #: the §5 terminal status as its enum value (`"Answered"`, `"NotFound"`, …)
    status: str

    def as_dict(self) -> dict[str, str | int]:
        return {
            "sheet_id": str(self.sheet_id),
            "row_id": str(self.row_id),
            "column_id": str(self.column_id),
            "version": self.version,
            "status": self.status,
        }


async def fetch_cells_since(
    session: AsyncSession, case_id: uuid.UUID, since: int
) -> list[ReconciledCell]:
    """Every terminal cell in `case_id` with `version > since`, ordered by version.

    Scoped to the case through `row.case_id`. **Terminal cells only** — the live
    stream carries nothing else, so the reconcile fetch and the stream page the
    exact same monotonic sequence and never disagree about what a client has seen.
    Ascending version so the client's cursor only ever advances.
    """
    stmt = (
        select(Row.sheet_id, Cell.row_id, Cell.column_id, Cell.version, Cell.status)
        .join(Row, Cell.row_id == Row.id)
        .where(
            Row.case_id == case_id,
            Cell.version > since,
            Cell.status.in_(TERMINAL),
        )
        .order_by(Cell.version)
    )
    result = await session.execute(stmt)
    return [
        ReconciledCell(
            sheet_id=sheet_id,
            row_id=row_id,
            column_id=column_id,
            version=version,
            status=status.value,
        )
        for sheet_id, row_id, column_id, version, status in result.all()
    ]
