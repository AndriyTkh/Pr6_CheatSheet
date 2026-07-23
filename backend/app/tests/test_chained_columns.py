"""§4 + §6 — a recipe consuming an already-derived column, chained N deep.

The pilot workflow stacks recipes: Web Search → Summarize → Classify, each column
reading the one before it (§6). Nothing new is built for that — the DAG edge
(`column_input`) and the memo key (§4 step6) are already per-column — so this file
is the *proof* that a chain resolves correctly, plus the assertions that pin the
two properties the chain depends on:

1. **Topo order holds under the wavefront gate.** A link is `blocked` until its
   input cell is terminal, and `on_cell_terminal` is the only thing that promotes
   it. So a 3-deep chain runs strictly L1 → L2 → L3 no matter what order the
   columns were dispatched in — the order lives in the data, not in when the job
   was enqueued (§4 step5). Proved by draining a real worker loop over the enqueue
   seam and by the recipe recording, in order, the input value each link saw.

2. **Every link gets its own distinct `cache_key`.** The chain shares every other
   key term — same recipe, same version, same params, same `model_id`, **same
   `output_slot`** — so the *only* term that separates the links is
   `resolved_input_hashes` (§4 step6). Each link's input is a different column's
   cell carrying a different value, so the three keys are distinct and a deep link
   can never cache-hit a shallower one's value. That is the term the task names,
   and this file isolates it by holding all the others constant.

DB-owned: `dispatch_column`/`execute_cell` commit, so the shared rolled-back
`session` fixture would leak. This file carries its own committing `db` fixture
that deletes its case (cascading sheet/row/column/cell) and then the `run`/`recipe`
rows, which do not cascade from `case` — `run` only after the cells that FK at it.
"""

from __future__ import annotations

import uuid
from typing import Any, ClassVar, Mapping, Sequence

import pytest
import pytest_asyncio
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import (
    Case,
    Cell,
    Column,
    ColumnInput,
    Recipe as RecipeRow,
    Row,
    Run,
    Sheet,
)
from app.models.enums import CellStatus, RecipeExecType, RowOrigin, SheetKind
from app.recipes.base import CellRecipe, CellResult, Citation, InputSpec, OutputSlot
from app.recipes.registry import ensure_registered, recipe_uuid
from app.services.cache_key import compute_cache_key, resolve_input_hashes, resolve_model_id
from app.services.cell_execution import execute_cell
from app.services.wavefront import dispatch_column
from app.tests.conftest import TEST_DB_URL, requires_db

#: Every column in the chain outputs this slot, so `output_slot` is held constant
#: across links — leaving `resolved_input_hashes` as the only distinguishing term.
SLOT = "step"
#: What one link appends. Fixed, so the value only grows by chaining — not because
#: the recipe or its params differ from link to link.
MARK = ">"


class ChainStep(CellRecipe):
    """Reads its single upstream cell (by slot), appends one mark, passes it on.

    Declares its input by the `output_slot` alias `_assemble_row_context` exposes,
    not by a column name — the input column is a different name at every link
    (`L1`, `L2`, …), but they all output `SLOT`, so one declaration resolves the
    required input at every depth. Records the input value it saw, in call order,
    which is what makes the topo order assertable.
    """

    id: ClassVar[str] = "chain_step"
    name: ClassVar[str] = "Chain step"
    version: ClassVar[int] = 1
    exec_type: ClassVar[RecipeExecType] = RecipeExecType.func
    inputs: ClassVar[Sequence[InputSpec]] = (InputSpec(SLOT),)
    outputs: ClassVar[Sequence[OutputSlot]] = (OutputSlot(SLOT, "text"),)
    output_schema: ClassVar[Mapping[str, Any]] = {
        "type": "object",
        "properties": {SLOT: {"type": "string"}},
        "required": [SLOT],
    }
    #: the upstream value each `exec()` actually saw, in call order
    seen: ClassVar[list[str]] = []

    async def exec(self, row_context, params):
        upstream = row_context.value(SLOT)
        ChainStep.seen.append(upstream)
        produced = f"{upstream}{MARK}"
        return [
            CellResult(
                slot=SLOT,
                value=produced,
                status=CellStatus.Answered,
                citations=[
                    Citation(source_type="api", quote=str(upstream), api_path="/chain")
                ],
            )
        ]


class EnqueueSpy:
    """Stands in for `app.tasks.cells.enqueue_cell` — records, never defers."""

    def __init__(self) -> None:
        self.calls: list[tuple[uuid.UUID, uuid.UUID, bool]] = []

    async def __call__(
        self, row_id: uuid.UUID, column_id: uuid.UUID, *, cache_bust: bool = False
    ) -> int:
        self.calls.append((row_id, column_id, cache_bust))
        return len(self.calls)

    def pairs(self) -> set[tuple[uuid.UUID, uuid.UUID]]:
        return {(r, c) for r, c, _ in self.calls}


@pytest.fixture
def spy() -> EnqueueSpy:
    return EnqueueSpy()


@pytest.fixture(autouse=True)
def reset_seen():
    ChainStep.seen.clear()
    yield
    ChainStep.seen.clear()


@pytest_asyncio.fixture
async def db() -> AsyncSession:
    """A committing session. `run`/`recipe` do not cascade from `case` — deleted here."""
    engine = create_async_engine(TEST_DB_URL)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    created: list[uuid.UUID] = []
    async with factory() as session:
        session.info["cases"] = created
        try:
            yield session
        finally:
            await session.rollback()
            for case_id in created:
                case = await session.get(Case, case_id)
                if case is not None:
                    await session.delete(case)
            await session.flush()
            rid = recipe_uuid(ChainStep.id)
            await session.execute(delete(Run).where(Run.recipe_id == rid))
            await session.execute(
                delete(RecipeRow).where(
                    RecipeRow.id == rid, RecipeRow.version == ChainStep.version
                )
            )
            await session.commit()
    await engine.dispose()


# ---------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------


async def _sheet(db: AsyncSession) -> Sheet:
    await ensure_registered(db, ChainStep)  # column.recipe_id FKs at `recipe` (0001)
    case = Case(name="chained columns test", owner_id=uuid.uuid4())
    db.add(case)
    await db.flush()
    db.info["cases"].append(case.id)
    sheet = Sheet(
        case_id=case.id, name="Тендери", kind=SheetKind.source, grain_label="lot"
    )
    db.add(sheet)
    await db.flush()
    return sheet


async def _row(db: AsyncSession, sheet: Sheet) -> Row:
    row = Row(
        case_id=sheet.case_id,
        sheet_id=sheet.id,
        origin=RowOrigin.connector,
        provenance_jsonb={"tenderID": "UA-2024-01", "lotID": "lot-1"},
        depth=0,
    )
    db.add(row)
    await db.flush()
    return row


async def _column(db: AsyncSession, sheet: Sheet, name: str, *, recipe: bool) -> Column:
    """A column that outputs `SLOT`. Recipe columns run `ChainStep`; the seed does not.

    Every column shares `output_slot=SLOT` on purpose: it is a cache-key term, so
    holding it constant is what leaves `resolved_input_hashes` as the only thing
    separating the links' keys.
    """
    column = Column(
        case_id=sheet.case_id,
        sheet_id=sheet.id,
        name=name,
        value_type="text",
        target_depth=0,
        output_slot=SLOT,
        recipe_id=recipe_uuid(ChainStep.id) if recipe else None,
        recipe_version=ChainStep.version if recipe else None,
    )
    db.add(column)
    await db.flush()
    return column


async def _edge(db: AsyncSession, downstream: Column, upstream: Column) -> None:
    db.add(ColumnInput(column_id=downstream.id, input_column_id=upstream.id))
    await db.flush()


async def _chain(db: AsyncSession):
    """seed → L1 → L2 → L3 on one row. The seed cell is `Answered`; L1..L3 run.

    Returns (row, seed, [L1, L2, L3]). Three recipe links = a 3-deep chain.
    """
    sheet = await _sheet(db)
    row = await _row(db, sheet)
    seed = await _column(db, sheet, "Seed", recipe=False)
    links = [await _column(db, sheet, f"L{i}", recipe=True) for i in (1, 2, 3)]
    await _edge(db, links[0], seed)
    await _edge(db, links[1], links[0])
    await _edge(db, links[2], links[1])
    db.add(Cell(row_id=row.id, column_id=seed.id, status=CellStatus.Answered,
                value_jsonb="SEED"))
    await db.commit()
    return row, seed, links


async def _status(db: AsyncSession, row: Row, column: Column) -> CellStatus | None:
    cell = await db.get(Cell, (row.id, column.id))
    return None if cell is None else cell.status


# ---------------------------------------------------------------------
# 1. The gate holds across the chain
# ---------------------------------------------------------------------


@requires_db
async def test_a_deep_link_stays_blocked_until_its_own_input_is_terminal(db, spy):
    """Dispatched in REVERSE, only the link whose input is ready enqueues.

    L2/L3 are `blocked` with no job at all — the wavefront gate, not enqueue
    order, is what holds the chain in topo order (§4 step5).
    """
    row, _seed, links = await _chain(db)
    l1, l2, l3 = links

    for column in (l3, l2, l1):  # reverse — order must not matter
        await dispatch_column(db, column, enqueue=spy)

    assert spy.pairs() == {(row.id, l1.id)}, "only L1's input (the seed) is terminal"
    assert await _status(db, row, l1) is CellStatus.pending
    assert await _status(db, row, l2) is CellStatus.blocked
    assert await _status(db, row, l3) is CellStatus.blocked


# ---------------------------------------------------------------------
# 2. The chain resolves in topo order, with a distinct key per link
# ---------------------------------------------------------------------


@requires_db
async def test_three_deep_chain_resolves_in_topo_order_with_distinct_keys(db, spy):
    """The Verify line. Drain a real worker loop over the enqueue seam and watch
    the wavefront carry the wave L1 → L2 → L3, each link keyed distinctly."""
    row, _seed, links = await _chain(db)
    l1, l2, l3 = links

    for column in (l3, l2, l1):  # dispatch order is deliberately not topo order
        await dispatch_column(db, column, enqueue=spy)

    # A worker loop: run each enqueued job; its terminal write wakes the next link,
    # which lands back on the queue. Nothing here imposes order — the gate does.
    order: list[uuid.UUID] = []
    queue = [(r, c) for r, c, _ in spy.calls]
    spy.calls.clear()
    while queue:
        r, c = queue.pop(0)
        await execute_cell(db, r, c, enqueue=spy)
        order.append(c)
        while spy.calls:
            wr, wc, _ = spy.calls.pop(0)
            queue.append((wr, wc))

    # Topo order, two independent witnesses: the completion order, and the value
    # each link saw on its input (L1 saw the seed, L2 saw L1's output, ...).
    assert order == [l1.id, l2.id, l3.id]
    assert ChainStep.seen == ["SEED", "SEED>", "SEED>>"]

    # Derivation actually flowed end to end: L3 carries all three marks.
    l3_cell = await db.get(Cell, (row.id, l3.id))
    await db.refresh(l3_cell)
    assert l3_cell.status is CellStatus.Answered
    assert l3_cell.value_jsonb == "SEED>>>"

    # A distinct cache_key per link — none NULL, all three different. If any two
    # collided, the deeper link would have cache-hit the shallower one's value and
    # `ChainStep` would have run fewer than three times.
    keys = []
    for link in links:
        cell = await db.get(Cell, (row.id, link.id))
        await db.refresh(cell)
        keys.append(cell.cache_key)
    assert all(k is not None for k in keys)
    assert len(set(keys)) == 3
    assert len(ChainStep.seen) == 3, "a link cache-hit a neighbour — keys collided"


@requires_db
async def test_resolved_input_hashes_is_the_term_that_separates_the_links(db, spy):
    """Names the mechanism: with every other key term held equal, the links differ
    only in `resolved_input_hashes`, and that alone yields distinct keys (§4 step6)."""
    row, _seed, links = await _chain(db)

    # Fill the chain so each link's input cell carries its terminal value.
    for column in (links[0], links[1], links[2]):
        await dispatch_column(db, column, enqueue=spy)
    order = [(r, c) for r, c, _ in spy.calls]
    spy.calls.clear()
    while order:
        r, c = order.pop(0)
        await execute_cell(db, r, c, enqueue=spy)
        while spy.calls:
            wr, wc, _ = spy.calls.pop(0)
            order.append((wr, wc))

    # The distinguishing term, computed directly, differs at every link...
    hashes = [await resolve_input_hashes(db, row, link) for link in links]
    assert len({tuple(h) for h in hashes}) == 3

    # ...and every *other* term is identical, so the whole keys differ only because
    # of it. Recompute each link's key from the same held-constant terms.
    keys = [
        compute_cache_key(
            recipe_version=ChainStep.version,
            input_hashes=h,
            params={},
            model_id=resolve_model_id(ChainStep, {}),
            output_slot=SLOT,
        )
        for h in hashes
    ]
    assert len(set(keys)) == 3
