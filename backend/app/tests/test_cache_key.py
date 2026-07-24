"""§4 step 6 — the memo key, and what a hit is allowed to skip.

Two halves, and they prove different things:

1. **The key is a pure function of its five terms.** Identical inputs → identical
   key; changing any one term → a different key. `output_slot` gets its own case
   because dropping that term is the failure that is *invisible* in a 1→1 test —
   every column of a 1→M recipe would read the first slot's value.
2. **A hit skips the provider, not just the write.** Asserted with a spy on the
   recipe's `exec()`, so "two rows, one paid call" is proved on the seam where
   the money moves. Asserting the second cell merely *has* a value would pass
   even if the recipe had run twice.

The DB half owns committed data (`execute_cell` commits) and cleans up after
itself: a `case` cascades sheet/row/column/cell, but `run` and `recipe` do not —
they are deleted explicitly, `run` only after the cells that FK at it are gone.
"""

from __future__ import annotations

import uuid
from typing import Any, ClassVar, Mapping, Sequence

import pytest
import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Case, Cell, Column, ColumnInput, Recipe as RecipeRow, Row, Run, Sheet
from app.models.enums import CellStatus, RecipeExecType, RowOrigin, SheetKind
from app.recipes.base import CellRecipe, CellResult, Citation, InputSpec, OutputSlot
from app.recipes.registry import ensure_registered, recipe_uuid
from app.services.cache_key import (
    compute_cache_key,
    input_hash,
    provenance_hash,
    resolve_input_hashes,
    resolve_model_id,
)
from app.services.cell_execution import execute_cell
from app.services.wavefront import invalidate_cell
from app.tests.conftest import TEST_DB_URL, requires_db

# =====================================================================
# The key is pure — no database
# =====================================================================

_TERMS: dict[str, Any] = {
    "recipe_version": 1,
    "input_hashes": [input_hash(uuid.UUID(int=1), CellStatus.Answered, "31200334")],
    "params": {"rubric": "beneficial owner"},
    "model_id": "claude-sonnet-5",
    "output_slot": "owner",
}


def _key(**overrides: Any) -> str:
    return compute_cache_key(**{**_TERMS, **overrides})


def test_identical_inputs_give_an_identical_key():
    assert _key() == _key()


@pytest.mark.parametrize(
    "term,other",
    [
        ("recipe_version", 2),
        ("params", {"rubric": "ultimate owner"}),
        ("model_id", "claude-opus-4-8"),
        ("output_slot", "owner_name"),
    ],
)
def test_changing_any_term_changes_the_key(term, other):
    assert _key(**{term: other}) != _key()


def test_output_slot_is_what_stops_a_1_to_m_recipe_colliding():
    """The M columns of one recipe share every other term — only the slot differs.

    Drop `output_slot` from the hash and all M columns read the first slot's
    memoized value, silently and identically wrong.
    """
    keys = {_key(output_slot=slot) for slot in ("owner", "owner_country", "risk")}
    assert len(keys) == 3


def test_a_different_input_value_changes_the_key():
    other = input_hash(uuid.UUID(int=1), CellStatus.Answered, "40075815")
    assert _key(input_hashes=[other]) != _key()


def test_the_input_status_is_part_of_the_hash():
    """`NotFound` and `Answered: null` are different answers (§5), not one memo."""
    answered = input_hash(uuid.UUID(int=1), CellStatus.Answered, None)
    not_found = input_hash(uuid.UUID(int=1), CellStatus.NotFound, None)
    assert answered != not_found


def test_the_input_column_is_part_of_the_hash():
    """Same value from a different column is a different resolved input."""
    assert input_hash(uuid.UUID(int=1), CellStatus.Answered, "x") != input_hash(
        uuid.UUID(int=2), CellStatus.Answered, "x"
    )


def test_edge_order_is_not_data():
    a = input_hash(uuid.UUID(int=1), CellStatus.Answered, "a")
    b = input_hash(uuid.UUID(int=2), CellStatus.Answered, "b")
    assert _key(input_hashes=[a, b]) == _key(input_hashes=[b, a])


def test_two_rows_with_different_provenance_do_not_share_a_key():
    """Gap 1 — the input-less column's stand-in resolved input (module docstring)."""
    first = provenance_hash({"tenderID": "UA-2024-01", "lotID": "lot-1"})
    second = provenance_hash({"tenderID": "UA-2024-02", "lotID": "lot-1"})
    assert first != second
    assert _key(input_hashes=[first]) != _key(input_hashes=[second])


def test_provenance_key_order_does_not_matter():
    assert provenance_hash({"a": 1, "b": 2}) == provenance_hash({"b": 2, "a": 1})


# --- gap 2: which model this run pins -------------------------------


class _Pinned:
    model_id = "claude-sonnet-5"


class _Unpinned:
    pass


def test_params_pin_the_model_over_the_recipe_declaration():
    assert resolve_model_id(_Pinned, {"model_id": "claude-opus-4-8"}) == "claude-opus-4-8"


def test_the_recipe_declaration_is_the_fallback():
    assert resolve_model_id(_Pinned, {}) == "claude-sonnet-5"
    assert resolve_model_id(_Pinned, None) == "claude-sonnet-5"


def test_a_deterministic_recipe_pins_no_model():
    """A `func` recipe has no model at all — `None`, not an invented default."""
    assert resolve_model_id(_Unpinned, {}) is None


# =====================================================================
# The recipe under test + fixtures
# =====================================================================


class CacheProbe(CellRecipe):
    """Counts its own `exec()` calls — the seam where a provider would be paid."""

    id: ClassVar[str] = "cache_probe"
    name: ClassVar[str] = "Cache probe"
    version: ClassVar[int] = 1
    exec_type: ClassVar[RecipeExecType] = RecipeExecType.func
    inputs: ClassVar[Sequence[InputSpec]] = (InputSpec("Code"),)
    outputs: ClassVar[Sequence[OutputSlot]] = (OutputSlot("owner", "text"),)
    output_schema: ClassVar[Mapping[str, Any]] = {
        "type": "object",
        "properties": {"owner": {"type": "string"}},
        "required": ["owner"],
    }
    #: every row_id `exec()` was actually called for, in order
    calls: ClassVar[list[uuid.UUID]] = []

    async def exec(self, row_context, params):
        CacheProbe.calls.append(row_context.row_id)
        return [
            CellResult(
                slot="owner",
                value="ТОВ Приклад",
                status=CellStatus.Answered,
                citations=[
                    Citation(
                        source_type="api",
                        quote="ТОВ Приклад",
                        api_path="/company/31200334",
                    )
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


@pytest.fixture
def spy() -> EnqueueSpy:
    return EnqueueSpy()


@pytest.fixture(autouse=True)
def reset_probe():
    CacheProbe.calls.clear()
    yield
    CacheProbe.calls.clear()


@pytest_asyncio.fixture
async def db() -> AsyncSession:
    """A committing session. `run`/`recipe` do not cascade from `case` — deleted here.

    Order matters: the case goes first so its cells (which FK at `run`) are gone
    before the runs they point at.
    """
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
            rid = recipe_uuid(CacheProbe.id)
            await session.execute(delete(Run).where(Run.recipe_id == rid))
            await session.execute(
                delete(RecipeRow).where(
                    RecipeRow.id == rid, RecipeRow.version == CacheProbe.version
                )
            )
            await session.commit()
    await engine.dispose()


async def _sheet(db: AsyncSession) -> Sheet:
    # `column.recipe_id/version` FKs at `recipe`, so the catalog row has to exist
    # before a column can point at it (0001).
    await ensure_registered(db, CacheProbe)
    case = Case(name="cache key test", owner_id=uuid.uuid4())
    db.add(case)
    await db.flush()
    db.info["cases"].append(case.id)
    sheet = Sheet(
        case_id=case.id, name="Тендери", kind=SheetKind.source, grain_label="lot"
    )
    db.add(sheet)
    await db.flush()
    return sheet


async def _row(db: AsyncSession, sheet: Sheet, tender: str) -> Row:
    row = Row(
        case_id=sheet.case_id,
        sheet_id=sheet.id,
        origin=RowOrigin.connector,
        provenance_jsonb={"tenderID": tender, "lotID": "lot-1"},
        depth=0,
    )
    db.add(row)
    await db.flush()
    return row


async def _column(
    db: AsyncSession, sheet: Sheet, name: str, *, recipe: bool = False
) -> Column:
    column = Column(
        case_id=sheet.case_id,
        sheet_id=sheet.id,
        name=name,
        value_type="text",
        target_depth=0,
        recipe_id=recipe_uuid(CacheProbe.id) if recipe else None,
        recipe_version=CacheProbe.version if recipe else None,
        output_slot="owner" if recipe else None,
    )
    db.add(column)
    await db.flush()
    return column


async def _answered(db: AsyncSession, row: Row, column: Column, value: Any) -> Cell:
    cell = Cell(
        row_id=row.id,
        column_id=column.id,
        status=CellStatus.Answered,
        value_jsonb=value,
    )
    db.add(cell)
    await db.flush()
    return cell


async def _two_rows_same_input(db: AsyncSession, value: str = "31200334"):
    """Two rows, different provenance, **identical input value** — the §2a saving."""
    sheet = await _sheet(db)
    first = await _row(db, sheet, "UA-2024-01")
    second = await _row(db, sheet, "UA-2024-02")
    upstream = await _column(db, sheet, "Code")
    downstream = await _column(db, sheet, "Owner", recipe=True)
    db.add(ColumnInput(column_id=downstream.id, input_column_id=upstream.id))
    await _answered(db, first, upstream, value)
    await _answered(db, second, upstream, value)
    await db.commit()
    return first, second, downstream


# =====================================================================
# Resolving the inputs (gap 1)
# =====================================================================


@requires_db
async def test_an_input_less_column_keys_on_the_rows_provenance(db):
    """Without the stand-in, every row on the sheet shares one key and row 2
    cache-hits row 1's value — the bug gap 1 exists to close."""
    sheet = await _sheet(db)
    first = await _row(db, sheet, "UA-2024-01")
    second = await _row(db, sheet, "UA-2024-02")
    column = await _column(db, sheet, "Winner")
    await db.commit()

    a = await resolve_input_hashes(db, first, column)
    b = await resolve_input_hashes(db, second, column)

    assert a == [provenance_hash(first.provenance_jsonb)]
    assert a != b, "two rows of an input-less column would share one memo"


@requires_db
async def test_a_column_with_edges_ignores_provenance(db):
    """With ≥1 edge the edges *are* the row's data — including provenance here
    would defeat the cross-row hit the saving depends on."""
    first, second, downstream = await _two_rows_same_input(db)

    assert await resolve_input_hashes(db, first, downstream) == await resolve_input_hashes(
        db, second, downstream
    )


# =====================================================================
# A hit spends nothing
# =====================================================================


@requires_db
async def test_two_rows_with_identical_inputs_run_the_recipe_once(db, spy):
    """The §2a saving, asserted on the provider seam rather than on the value."""
    first, second, downstream = await _two_rows_same_input(db)

    ran = await execute_cell(db, first.id, downstream.id, enqueue=spy)
    hit = await execute_cell(db, second.id, downstream.id, enqueue=spy)

    assert CacheProbe.calls == [first.id], "the second row paid for the same question"
    assert ran.cache_hit is False
    assert hit.cache_hit is True
    assert hit.cache_key == ran.cache_key

    cell = await db.get(Cell, (second.id, downstream.id))
    await db.refresh(cell)
    assert cell.status is CellStatus.Answered
    assert cell.value_jsonb == "ТОВ Приклад"
    assert cell.citation_jsonb and cell.citation_jsonb[0]["quote"] == "ТОВ Приклад"
    # Lineage points at the run that actually produced the value (§10).
    assert cell.run_id == ran.run_id
    assert cell.cache_key == ran.cache_key

    runs = (await db.execute(select(Run).where(Run.id == ran.run_id))).scalars().all()
    assert len(runs) == 1, "a hit must not open a run for work that never happened"


@requires_db
async def test_a_different_input_value_is_a_miss(db, spy):
    """The guard on the test above: the spy would also read '1 call' if the
    second execution had simply crashed."""
    sheet = await _sheet(db)
    first = await _row(db, sheet, "UA-2024-01")
    second = await _row(db, sheet, "UA-2024-02")
    upstream = await _column(db, sheet, "Code")
    downstream = await _column(db, sheet, "Owner", recipe=True)
    db.add(ColumnInput(column_id=downstream.id, input_column_id=upstream.id))
    await _answered(db, first, upstream, "31200334")
    await _answered(db, second, upstream, "40075815")
    await db.commit()

    a = await execute_cell(db, first.id, downstream.id, enqueue=spy)
    b = await execute_cell(db, second.id, downstream.id, enqueue=spy)

    assert CacheProbe.calls == [first.id, second.id]
    assert b.cache_hit is False
    assert a.cache_key != b.cache_key


@requires_db
async def test_confirming_a_previewed_cell_hits_its_own_memo(db, spy):
    """§4 step 4 — Preview ran this very cell; confirm must not pay again.

    This is why the cache check precedes the claim: claiming would flip the cell
    to `running` and destroy the terminal status the hit looks for.
    """
    first, _second, downstream = await _two_rows_same_input(db)

    previewed = await execute_cell(db, first.id, downstream.id, enqueue=spy)
    confirmed = await execute_cell(db, first.id, downstream.id, enqueue=spy)

    assert CacheProbe.calls == [first.id]
    assert confirmed.cache_hit is True
    assert confirmed.run_id == previewed.run_id
    cell = await db.get(Cell, (first.id, downstream.id))
    await db.refresh(cell)
    assert cell.status is CellStatus.Answered


# =====================================================================
# Force refresh (cache_bust)
# =====================================================================


@requires_db
async def test_cache_bust_re_runs_and_keeps_the_old_run(db, spy):
    """§4 step 6 + Principle 5 — history is append-only, so the superseded run
    row is never touched."""
    first, _second, downstream = await _two_rows_same_input(db)
    original = await execute_cell(db, first.id, downstream.id, enqueue=spy)

    busted = await execute_cell(db, first.id, downstream.id, cache_bust=True, enqueue=spy)

    assert CacheProbe.calls == [first.id, first.id], "cache_bust did not bypass the memo"
    assert busted.cache_hit is False
    assert busted.run_id is not None and busted.run_id != original.run_id

    runs = (
        (
            await db.execute(
                select(Run).where(Run.recipe_id == recipe_uuid(CacheProbe.id))
            )
        )
        .scalars()
        .all()
    )
    assert {r.id for r in runs} == {original.run_id, busted.run_id}
    assert [r.cache_bust for r in runs if r.id == original.run_id] == [False]
    assert [r.cache_bust for r in runs if r.id == busted.run_id] == [True]

    cell = await db.get(Cell, (first.id, downstream.id))
    await db.refresh(cell)
    assert cell.run_id == busted.run_id, "the cell points at the run that just wrote it"


@requires_db
async def test_invalidate_cell_defers_with_cache_bust(db, spy):
    """The user's force-refresh: `pending` + a job that will bypass the memo."""
    first, _second, downstream = await _two_rows_same_input(db)
    await execute_cell(db, first.id, downstream.id, enqueue=spy)
    spy.calls.clear()

    assert await invalidate_cell(db, first.id, downstream.id, enqueue=spy) is True

    assert spy.calls == [(first.id, downstream.id, True)]
    cell = await db.get(Cell, (first.id, downstream.id))
    await db.refresh(cell)
    assert cell.status is CellStatus.pending
    # The grid keeps showing the old answer until the new run overwrites it.
    assert cell.value_jsonb == "ТОВ Приклад"


@requires_db
async def test_invalidating_a_cell_that_does_not_exist_defers_nothing(db, spy):
    sheet = await _sheet(db)
    row = await _row(db, sheet, "UA-2024-01")
    column = await _column(db, sheet, "Owner", recipe=True)
    await db.commit()

    assert await invalidate_cell(db, row.id, column.id, enqueue=spy) is False
    assert spy.calls == []
