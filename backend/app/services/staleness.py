"""§4 "Staleness" — an upstream column edit greys its downstream dependents.

Editing a column does **not** recompute anything. It walks the DAG *downstream*
and marks every reachable column `stale` (the §5 rollup), then surfaces a
"new version available" prompt the user must confirm before a single cell is
re-run (§4: *"Do not auto-rerun — surface 'new version available', user
confirms."*). Cells keep their old values and citations until that confirmed
rerun: `cell.status` is the per-operation truth and is untouched here; only the
`column.status` rollup greys (§5).

The walk is the recursive CTE §4 spells out, with **`UNION` (not `UNION ALL`)**
so a diamond or an accidental cycle terminates instead of looping forever.

It is **sheet-agnostic on purpose.** A `column_input` edge crosses the sheet
boundary at an Expand / Pair-builder producer node (§2a: *"the DAG spans sheets
at the sheet boundary only"*), so the very same walk greys a derived sheet's
columns when their source-sheet input is re-run — no sheet-specific code path.

Nothing here enqueues a job or writes a cell: there is no import of the queue
layer and no `cell` write, so "mark stale" structurally cannot re-execute. A
confirmed rerun is a separate, user-initiated step (`invalidate_cell` /
`dispatch_column`, §4 step 6). The caller owns the transaction — this function
mutates and returns, it does not commit.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy import text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Column
from app.models.enums import ColumnStatus

#: The §4 staleness walk. `UNION` dedupes the frontier so a diamond (A→B, A→C,
#: B→D, C→D) visits D once and an accidental back-edge cannot loop. Sheet-agnostic:
#: the join is over `column_input` edges, never `sheet_id`, so it crosses the sheet
#: boundary at an Expand/Pair node (§2a). Kept as the *walk* only; the greying is a
#: separate ORM update so the session's view stays coherent with the DB.
_STALE_WALK = text(
    """
    WITH RECURSIVE stale AS (
        SELECT column_id
          FROM column_input
         WHERE input_column_id = :changed
      UNION
        SELECT ci.column_id
          FROM column_input ci
          JOIN stale s ON ci.input_column_id = s.column_id
    )
    SELECT column_id FROM stale
    """
)


@dataclass(slots=True)
class StalenessResult:
    """The "new version available" prompt (§4 "never auto-rerun").

    `stale_column_ids` are the downstream columns greyed by this edit — the set a
    confirmed rerun would cover. Nothing in producing this result re-ran them;
    the changed column itself is deliberately absent (only *dependents* grey).
    """

    changed_column_id: uuid.UUID
    stale_column_ids: list[uuid.UUID] = field(default_factory=list)

    @property
    def new_version_available(self) -> bool:
        """True when at least one dependent was greyed — show the prompt."""
        return bool(self.stale_column_ids)


async def mark_downstream_stale(
    session: AsyncSession, changed_column_id: uuid.UUID
) -> StalenessResult:
    """Walk downstream of `changed_column_id`, mark every reachable column stale.

    Returns the greyed columns so the caller can surface the confirm prompt. Does
    not touch any cell and does not enqueue — greying is column-level only (§5).
    The caller commits.
    """
    walked = await session.execute(_STALE_WALK, {"changed": changed_column_id})
    stale_ids = [row[0] for row in walked.all()]
    if stale_ids:
        # `synchronize_session="fetch"` updates the greyed columns *in the identity
        # map too*, so a caller re-reading `column.status` through this session sees
        # `stale` — without expiring unrelated objects. Nothing else is written:
        # cells keep their value/citation/version (§5), and nothing is enqueued.
        await session.execute(
            update(Column)
            .where(Column.id.in_(stale_ids))
            .values(status=ColumnStatus.stale)
            .execution_options(synchronize_session="fetch")
        )
    return StalenessResult(changed_column_id, stale_ids)
