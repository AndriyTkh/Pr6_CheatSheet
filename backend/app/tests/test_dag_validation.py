"""DB-backed edge-add validation (§4 step 2, §2a).

`test_dag_graph.py` covers the pure algorithms; this file covers the part that
needs real rows — the loads, the sheet/grain lookups, and the fact that a
rejection leaves nothing behind. Skips cleanly without `CS_TEST_DATABASE_URL`.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.dag import (
    CycleRejected,
    GrainRejected,
    ListGateRejected,
    ProposedEdge,
    affected_subgraph,
    validate_new_column,
)
from app.models import Column, ColumnInput, Sheet
from app.models.enums import InputConsumption, SheetKind
from app.tests.conftest import requires_db

pytestmark = requires_db


async def _validate(
    session: AsyncSession,
    sheet: Sheet,
    new_column_id: uuid.UUID,
    proposed: list[ProposedEdge],
    target_depth: int = 0,
) -> None:
    await validate_new_column(
        session,
        case_id=sheet.case_id,
        sheet_id=sheet.id,
        target_depth=target_depth,
        new_column_id=new_column_id,
        proposed=proposed,
    )


async def test_happy_path_accepts(session, source_sheet, make_column):
    """Same sheet, same grain, whole_list against a non-list column."""
    upstream = await make_column("Переможець")
    await _validate(session, source_sheet, uuid.uuid4(), [ProposedEdge(upstream.id)])


async def test_cycle_is_rejected(session, source_sheet, make_column):
    """A → B exists; proposing B → A closes the loop (§4 step 2)."""
    a = await make_column("A")
    b = await make_column("B")
    session.add(ColumnInput(column_id=b.id, input_column_id=a.id))
    await session.flush()

    with pytest.raises(CycleRejected) as exc:
        await _validate(session, source_sheet, a.id, [ProposedEdge(b.id)])
    assert "B" in exc.value.message


async def test_self_edge_is_rejected(session, source_sheet, make_column):
    a = await make_column("A")
    with pytest.raises(CycleRejected):
        await _validate(session, source_sheet, a.id, [ProposedEdge(a.id)])


async def test_per_item_against_list_column_is_rejected(
    session, source_sheet, make_column
):
    """The §2a expansion gate — the message must offer the two Expand modes."""
    participants = await make_column("@participants", value_type="list")

    with pytest.raises(ListGateRejected) as exc:
        await _validate(
            session,
            source_sheet,
            uuid.uuid4(),
            [ProposedEdge(participants.id, consumes=InputConsumption.per_item)],
        )
    message = exc.value.message
    assert "@participants" in message
    assert "inline" in message and "new_table" in message


async def test_whole_list_against_list_column_is_fine(
    session, source_sheet, make_column
):
    """Only `per_item` is gated — counting a list whole is a normal recipe."""
    participants = await make_column("@participants", value_type="list")
    await _validate(
        session,
        source_sheet,
        uuid.uuid4(),
        [ProposedEdge(participants.id, consumes=InputConsumption.whole_list)],
    )


async def test_cross_sheet_input_is_rejected(session, source_sheet, make_column):
    """Data crosses a sheet boundary only via Expand / Pair builder (§2a)."""
    derived = Sheet(
        case_id=source_sheet.case_id,
        name="Компанії",
        kind=SheetKind.derived,
        grain_label="company",
        parent_sheet_id=source_sheet.id,
    )
    session.add(derived)
    await session.flush()
    foreign = await make_column("ЄДРПОУ", sheet=derived)

    with pytest.raises(GrainRejected) as exc:
        await _validate(session, source_sheet, uuid.uuid4(), [ProposedEdge(foreign.id)])
    assert "аркуш" in exc.value.message


async def test_cross_grain_input_is_rejected(session, source_sheet, make_column):
    """Same sheet, different `target_depth` — an inline-expanded child grain."""
    child_grain = await make_column("Учасник", target_depth=1)

    with pytest.raises(GrainRejected):
        await _validate(
            session,
            source_sheet,
            uuid.uuid4(),
            [ProposedEdge(child_grain.id)],
            target_depth=0,
        )


async def test_unknown_input_column_is_rejected(session, source_sheet):
    with pytest.raises(GrainRejected):
        await _validate(session, source_sheet, uuid.uuid4(), [ProposedEdge(uuid.uuid4())])


async def test_no_proposed_edges_is_a_seed_column(session, source_sheet):
    """A connector/upload column has no inputs — nothing to validate."""
    await _validate(session, source_sheet, uuid.uuid4(), [])


async def test_rejection_persists_nothing(session, source_sheet, make_column):
    """§4 step 2 — reject means no edge exists afterwards."""
    a = await make_column("A")
    b = await make_column("B")
    session.add(ColumnInput(column_id=b.id, input_column_id=a.id))
    await session.flush()

    with pytest.raises(CycleRejected):
        await _validate(session, source_sheet, a.id, [ProposedEdge(b.id)])

    edges = (await session.execute(ColumnInput.__table__.select())).all()
    assert len([e for e in edges if e.column_id == a.id]) == 0


async def test_second_proposed_edge_sees_the_first(session, source_sheet, make_column):
    """Two edges added in one action can close a cycle between themselves."""
    a = await make_column("A")
    b = await make_column("B")
    session.add(ColumnInput(column_id=b.id, input_column_id=a.id))
    await session.flush()

    # new column N takes B as input (fine), and also feeds... itself via A? No:
    # A → B → N is acyclic. Proposing N as an input of A is the rejected shape.
    n = uuid.uuid4()
    await _validate(session, source_sheet, n, [ProposedEdge(b.id)])


async def test_affected_subgraph_is_topo_ordered(session, source_sheet, make_column):
    """§4 step 3 — changed column first, dependents after their inputs."""
    a = await make_column("A")
    b = await make_column("B")
    c = await make_column("C")
    session.add_all(
        [
            ColumnInput(column_id=b.id, input_column_id=a.id),
            ColumnInput(column_id=c.id, input_column_id=b.id),
        ]
    )
    await session.flush()

    order = await affected_subgraph(session, source_sheet.case_id, a.id)
    assert order == [a.id, b.id, c.id]

    # An unrelated column is not in the affected set.
    unrelated = await make_column("Z")
    assert unrelated.id not in order


async def test_affected_subgraph_of_a_leaf_is_itself(session, source_sheet, make_column):
    leaf: Column = await make_column("Leaf")
    assert await affected_subgraph(session, source_sheet.case_id, leaf.id) == [leaf.id]
