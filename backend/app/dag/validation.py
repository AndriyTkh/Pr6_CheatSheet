"""Edge-add validation — §4 step 2, run app-side on the add-column action.

Three checks, one place, one failure mode: the action is rejected and nothing
exists afterwards. The schema deliberately does not encode any of them (see the
"APP-SIDE INVARIANTS" block at the foot of migration 0002).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dag.errors import CycleRejected, GrainRejected, ListGateRejected
from app.dag.graph import Edge, closes_cycle, topo_sort
from app.models import Column, ColumnInput
from app.models.enums import InputConsumption


@dataclass(frozen=True, slots=True)
class ProposedEdge:
    """An edge the user is about to create by adding a column."""

    input_column_id: uuid.UUID
    is_required: bool = True
    consumes: InputConsumption = InputConsumption.whole_list


async def load_edges(session: AsyncSession, case_id: uuid.UUID) -> list[Edge]:
    """All DAG edges in a case.

    Case-scoped, not sheet-scoped: the DAG spans sheets at the sheet boundary
    (§2a), so a cycle can run through a derived sheet and back.
    """
    stmt = (
        select(ColumnInput.input_column_id, ColumnInput.column_id)
        .join(Column, Column.id == ColumnInput.column_id)
        .where(Column.case_id == case_id)
    )
    result = await session.execute(stmt)
    return [(src, dst) for src, dst in result.all()]


async def validate_new_column(
    session: AsyncSession,
    *,
    case_id: uuid.UUID,
    sheet_id: uuid.UUID,
    target_depth: int,
    new_column_id: uuid.UUID,
    proposed: Sequence[ProposedEdge],
) -> None:
    """Reject the add-column action, or return silently.

    Raises `ListGateRejected`, `CycleRejected`, or `GrainRejected` — all
    `EdgeRejected`, all carrying a message the UI shows verbatim.

    `new_column_id` may be a not-yet-persisted uuid: the checks run against the
    proposed graph, which is the point (§4 step 2 — "reject before anything
    exists").
    """
    if not proposed:
        return

    input_ids = [p.input_column_id for p in proposed]
    inputs = (
        (await session.execute(select(Column).where(Column.id.in_(input_ids))))
        .scalars()
        .all()
    )
    by_id = {c.id: c for c in inputs}

    missing = set(input_ids) - by_id.keys()
    if missing:
        raise GrainRejected(
            f"Вхідні колонки не знайдено: {', '.join(str(m) for m in sorted(missing, key=str))}"
        )

    for edge in proposed:
        column = by_id[edge.input_column_id]

        # --- §2a list gate. Checked first: it is the one the journalist can act
        # on, and its message offers the fix (the two Expand modes).
        if edge.consumes is InputConsumption.per_item and column.is_list:
            raise ListGateRejected(column.id, column.name)

        # --- §2a grain. A column runs on one grain; the wavefront creates cells
        # only where row.depth == column.target_depth, so a cross-grain edge
        # could never produce a cell at all.
        if column.sheet_id != sheet_id:
            raise GrainRejected(
                f"Колонка «{column.name}» належить іншому аркушу. Дані між "
                f"аркушами передаються лише рецептом, що створює похідний "
                f"аркуш (Expand / Pair builder)."
            )
        if column.target_depth != target_depth:
            raise GrainRejected(
                f"Колонка «{column.name}» працює на іншій зернистості "
                f"(рівень {column.target_depth}, а не {target_depth})."
            )

    # --- §4 step 2 cycle check, over the whole case graph.
    existing = await load_edges(session, case_id)
    names = {c.id: c.name for c in inputs}
    for edge in proposed:
        cycle = closes_cycle(existing, (edge.input_column_id, new_column_id))
        if cycle is not None:
            # `names` only knows the directly-proposed inputs; a multi-hop
            # cycle walks through other columns too — fetch those so the
            # message never falls back to a raw uuid (§6 journalist-readable).
            unresolved = [n for n in cycle if n not in names]
            if unresolved:
                extra = (
                    (await session.execute(select(Column).where(Column.id.in_(unresolved))))
                    .scalars()
                    .all()
                )
                names.update({c.id: c.name for c in extra})
            raise CycleRejected([names.get(n, str(n)) for n in cycle])
        existing.append((edge.input_column_id, new_column_id))


async def affected_subgraph(
    session: AsyncSession, case_id: uuid.UUID, changed_column_id: uuid.UUID
) -> list[uuid.UUID]:
    """§4 step 3 — topo-sorted order of `changed` plus everything downstream.

    Enqueue order, not execution order: under parallel workers, execution order
    is enforced by the wavefront (data), never by queue insertion (§4 step 5).
    """
    from app.dag.graph import downstream  # local: keeps graph.py import-light

    edges = await load_edges(session, case_id)
    nodes = downstream(edges, changed_column_id, include_start=True)
    ordered_nodes = [changed_column_id, *sorted(nodes - {changed_column_id}, key=str)]
    return topo_sort(ordered_nodes, edges)
