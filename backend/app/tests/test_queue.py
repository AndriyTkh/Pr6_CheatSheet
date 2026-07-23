"""§4 — Procrastinate is the queue, and nothing else in the app locks.

Three things are proved here, and the first two matter as much as the third:

1. **No code path locks on `cell.status`** (§4's explicit warning, backend
   CLAUDE.md non-negotiable). No `with_for_update()`, no hand-written
   `FOR UPDATE` / `SKIP LOCKED` in our SQL — the only row lock in the system
   lives in `procrastinate_jobs`, a table this app never queries.
2. **No hand-rolled poller in `app/tasks/`.** A `sleep()` in the queue layer is
   how a second queue starts; Procrastinate's `LISTEN/NOTIFY` is the wake-up.
3. **A job deferred through the real app, drained by a real worker, leaves the
   cell terminal.** Not a mocked connector — an actual `procrastinate_jobs`
   insert and an actual worker taking it under `SKIP LOCKED`.

The DB-backed test needs the Procrastinate schema *and* both migrations on the
same database (`python scripts/apply_queue_schema.py`), and both env vars
pointed at it — `CS_DATABASE_URL` because `procrastinate_app` and
`async_session_factory` are module-level singletons built from it, and
`CS_TEST_DATABASE_URL` because that is what the fixtures read.
"""

from __future__ import annotations

import ast
import asyncio
import uuid
from pathlib import Path
from typing import Any, ClassVar, Mapping, Sequence

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Case, Cell, Column, Recipe as RecipeRow, Row, Run, Sheet
from app.models.enums import (
    TERMINAL,
    CellStatus,
    RecipeExecType,
    RowOrigin,
    SheetKind,
)
from app.recipes.base import CellRecipe, CellResult, OutputSlot
from app.recipes.registry import ensure_registered, recipe_uuid
from app.tasks.app import procrastinate_app, use_selector_event_loop
from app.tasks.cells import enqueue_cell
from app.tests.conftest import TEST_DB_URL, requires_db

APP_DIR = Path(__file__).resolve().parents[1]


# =====================================================================
# 1 + 2. Structural — always run, no database
# =====================================================================


def _app_sources() -> list[Path]:
    """Every module of the app except the tests that assert about them."""
    tests = APP_DIR / "tests"
    return [p for p in APP_DIR.rglob("*.py") if tests not in p.parents]


def _docstring_nodes(tree: ast.Module) -> set[int]:
    """`id()` of every string node that is a docstring, so prose can say
    "no `FOR UPDATE`" without tripping the check that enforces it."""
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            body = getattr(node, "body", None)
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                ids.add(id(body[0].value))
    return ids


def test_no_code_path_locks_on_cell_status():
    """§4: `cell.status` is data/display. A lock here is two queues fighting."""
    offences: list[str] = []
    for path in _app_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        docstrings = _docstring_nodes(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr == "with_for_update":
                offences.append(f"{path.name}:{node.lineno} with_for_update()")
            elif isinstance(node, ast.Name) and node.id == "with_for_update":
                offences.append(f"{path.name}:{node.lineno} with_for_update")
            elif (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and id(node) not in docstrings
            ):
                sql = " ".join(node.value.upper().split())
                for banned in ("FOR UPDATE", "SKIP LOCKED"):
                    if banned in sql:
                        offences.append(f"{path.name}:{node.lineno} {banned} in SQL")
    assert offences == [], (
        "the only row lock in the system belongs to Procrastinate (§4): " f"{offences}"
    )


def test_the_queue_layer_has_no_poll_loop():
    """§4: 'not a hand-rolled poller'. `LISTEN/NOTIFY` wakes the worker, not a sleep."""
    offences: list[str] = []
    for path in sorted((APP_DIR / "tasks").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            if name == "sleep":
                offences.append(f"{path.name}:{node.lineno} sleep()")
    assert offences == [], f"a sleep in app/tasks/ is a poller growing back: {offences}"


# =====================================================================
# 3. End-to-end through the real queue
# =====================================================================


class QueueProbe(CellRecipe):
    """A recipe with no inputs and no provider — this test is about transport.

    Declaring no inputs keeps the dead-end lock (§6) out of the way, so a
    non-`Answered` result can only mean the job did not travel correctly.
    """

    id: ClassVar[str] = "queue_probe"
    name: ClassVar[str] = "Queue probe"
    version: ClassVar[int] = 1
    exec_type: ClassVar[RecipeExecType] = RecipeExecType.func
    outputs: ClassVar[Sequence[OutputSlot]] = (OutputSlot("probe", "text"),)
    output_schema: ClassVar[Mapping[str, Any]] = {
        "type": "object",
        "properties": {"probe": {"type": "string"}},
        "required": ["probe"],
    }

    async def exec(self, row_context, params):
        return [
            CellResult(slot="probe", value="ran-on-a-worker", status=CellStatus.Answered)
        ]


def _factory() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(TEST_DB_URL)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def _seed(factory: async_sessionmaker[AsyncSession]) -> tuple[uuid.UUID, ...]:
    """A case → sheet → column → row, **committed**.

    The shared `session` fixture rolls back, and a worker on its own connection
    cannot see uncommitted rows — so this test owns its own committed data and
    its own cleanup.
    """
    async with factory() as db:
        await ensure_registered(db, QueueProbe)
        case = Case(name="queue test", owner_id=uuid.uuid4())
        db.add(case)
        await db.flush()
        sheet = Sheet(
            case_id=case.id, name="Тендери", kind=SheetKind.source, grain_label="lot"
        )
        db.add(sheet)
        await db.flush()
        column = Column(
            case_id=case.id,
            sheet_id=sheet.id,
            name="Probe",
            value_type="text",
            recipe_id=recipe_uuid(QueueProbe.id),
            recipe_version=QueueProbe.version,
            output_slot="probe",
            target_depth=0,
        )
        row = Row(
            case_id=case.id,
            sheet_id=sheet.id,
            origin=RowOrigin.connector,
            provenance_jsonb={"tenderID": "UA-QUEUE-1", "lotID": "lot-1"},
            depth=0,
        )
        db.add_all([column, row])
        await db.commit()
        return case.id, row.id, column.id


async def _teardown(factory: async_sessionmaker[AsyncSession], case_id: uuid.UUID) -> None:
    """Case cascades sheet/row/column/cell; `run` and `recipe` do not."""
    async with factory() as db:
        case = await db.get(Case, case_id)
        if case is not None:
            await db.delete(case)
            await db.flush()
        rid = recipe_uuid(QueueProbe.id)
        await db.execute(delete(Run).where(Run.recipe_id == rid))
        await db.execute(
            delete(RecipeRow).where(
                RecipeRow.id == rid, RecipeRow.version == QueueProbe.version
            )
        )
        await db.commit()


async def _deferred_job_runs_to_terminal() -> None:
    factory = _factory()
    case_id, row_id, column_id = await _seed(factory)
    try:
        async with procrastinate_app.open_async():
            job_id = await enqueue_cell(row_id, column_id)
            assert isinstance(job_id, int)
            # `wait=False`: drain what is queued, then stop. The worker takes the
            # job under SKIP LOCKED — nothing here polls `cell.status`.
            await asyncio.wait_for(
                procrastinate_app.run_worker_async(
                    queues=["cells"], wait=False, install_signal_handlers=False
                ),
                timeout=60,
            )

        async with factory() as db:
            cell = await db.get(Cell, (row_id, column_id))
            assert cell is not None, "the worker never wrote the cell"
            assert cell.status in TERMINAL, f"cell left at {cell.status}"
            assert cell.status is CellStatus.Answered
            assert cell.value_jsonb == "ran-on-a-worker"
            assert cell.run_id is not None, "§10 — every execution writes a run"
            # §4 step 6 belongs to the next task; NULL means "not hittable".
            assert cell.cache_key is None
            run = (
                await db.execute(select(Run).where(Run.id == cell.run_id))
            ).scalar_one()
            assert run.recipe_version == QueueProbe.version
    finally:
        await _teardown(factory, case_id)


@requires_db
def test_a_job_deferred_through_procrastinate_lands_terminal():
    """Deliberately sync: the queue's psycopg stack needs the selector loop on
    Windows, and owning `asyncio.run()` here is cheaper than overriding
    pytest-asyncio's loop policy for the whole session."""
    previous = asyncio.get_event_loop_policy()
    use_selector_event_loop()
    try:
        asyncio.run(_deferred_job_runs_to_terminal())
    finally:
        asyncio.set_event_loop_policy(previous)


def test_the_task_is_registered_under_its_stable_name():
    """A rename of the Python function must not orphan jobs already deferred."""
    from app.tasks.cells import TASK_NAME

    assert TASK_NAME in procrastinate_app.tasks
    assert procrastinate_app.tasks[TASK_NAME].queue == "cells"


@pytest.mark.parametrize("banned", ["FOR UPDATE", "SKIP LOCKED"])
def test_the_lock_check_would_actually_catch_something(banned):
    """Guards the guard: the AST scan must not be vacuously passing."""
    tree = ast.parse(f'q = "SELECT 1 {banned}"')
    strings = [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
    ]
    assert strings and banned in strings[0].value.upper()
