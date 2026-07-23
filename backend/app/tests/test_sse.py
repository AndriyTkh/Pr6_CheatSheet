"""§4 step 7 — SSE streaming with batched flush.

The task's risk is **update rate**, not row count: a wavefront run turns a whole
sheet's cells terminal in a burst, and one SSE message per cell re-renders the
grid thousands of times. So the load-bearing assertion, named in the Verify line,
is `test_burst_of_updates_arrives_as_one_message`: N cell updates inside one flush
window arrive as **one** message, not N. Everything else guards the corners of
that guarantee — coalescing to the latest version, the size cap, case scoping, and
the monotonic version the reconcile task pages on.

Layered so most of it runs with no database:

* the batcher and its SSE encoding are pure (timing only) — the core proof;
* the broker fan-out is pure (in-process queues);
* only `_resolve_update` (the listener's DB re-read) needs Postgres, behind
  `requires_db`.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Case, Cell, Column, Row, Sheet
from app.models.enums import CellStatus, RowOrigin, SheetKind
from app.realtime import broker as broker_module
from app.realtime.batcher import CellBatcher
from app.realtime.broker import Broker
from app.realtime.events import CellUpdate
from app.realtime.listener import _resolve_update
from app.realtime.routes import _encode_batch
from app.tests.conftest import TEST_DB_URL, requires_db


# =====================================================================
# Helpers
# =====================================================================


def _update(
    case_id: uuid.UUID,
    version: int,
    *,
    row_id: uuid.UUID | None = None,
    column_id: uuid.UUID | None = None,
    status: str = "Answered",
) -> CellUpdate:
    return CellUpdate(
        case_id=case_id,
        row_id=row_id or uuid.uuid4(),
        column_id=column_id or uuid.uuid4(),
        version=version,
        status=status,
    )


def _queue_of(updates: list[CellUpdate]) -> asyncio.Queue[CellUpdate]:
    """A pre-filled source queue — the whole burst is available before draining."""
    queue: asyncio.Queue[CellUpdate] = asyncio.Queue()
    for update in updates:
        queue.put_nowait(update)
    return queue


async def _collect(batcher: CellBatcher, *, seconds: float) -> list[list[CellUpdate]]:
    """Run the batcher for a fixed wall-clock span and return every batch it flushed."""
    batches: list[list[CellUpdate]] = []

    async def _run() -> None:
        async for batch in batcher.batches():
            batches.append(batch)

    task = asyncio.create_task(_run())
    await asyncio.sleep(seconds)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    return batches


# =====================================================================
# The Verify assertion — N in one window arrive as ONE message
# =====================================================================


async def test_burst_of_updates_arrives_as_one_message():
    """50 distinct cells finishing inside one window → a single batch of 50.

    Not 50 batches of 1. This is the whole task: the grid gets one re-render for
    the burst, not fifty.
    """
    case_id = uuid.uuid4()
    updates = [_update(case_id, version=v) for v in range(50)]
    batcher = CellBatcher(_queue_of(updates), window_seconds=0.1, max_cells=1000)

    batches = await _collect(batcher, seconds=0.35)

    assert len(batches) == 1, f"expected one coalesced flush, got {len(batches)}"
    assert len(batches[0]) == 50


async def test_one_flush_encodes_to_one_sse_event():
    """The route emits one `cells` event per batch — 50 updates ride in its data."""
    case_id = uuid.uuid4()
    batch = [_update(case_id, version=v) for v in range(50)]

    event = _encode_batch(batch)

    assert event["event"] == "cells"
    import json

    payload = json.loads(event["data"])
    assert len(payload["updates"]) == 50


# =====================================================================
# Coalescing, the size cap, and idleness
# =====================================================================


async def test_repeated_cell_coalesces_to_latest_version():
    """The same cell flipping several times in a window ships once, at max version."""
    case_id = uuid.uuid4()
    row, col = uuid.uuid4(), uuid.uuid4()
    # Out-of-order on purpose: the version is the tiebreaker, never arrival order.
    versions = [10, 12, 11, 9, 12]
    updates = [
        _update(case_id, version=v, row_id=row, column_id=col) for v in versions
    ]
    batcher = CellBatcher(_queue_of(updates), window_seconds=0.1, max_cells=1000)

    batches = await _collect(batcher, seconds=0.3)

    assert len(batches) == 1
    assert len(batches[0]) == 1
    assert batches[0][0].version == 12


async def test_max_cells_flushes_before_the_window_closes():
    """A burst denser than `max_cells` flushes early — one message never grows unbounded."""
    case_id = uuid.uuid4()
    updates = [_update(case_id, version=v) for v in range(25)]
    # Window long enough that only the size cap can trigger this flush.
    batcher = CellBatcher(_queue_of(updates), window_seconds=5.0, max_cells=10)

    batches = await _collect(batcher, seconds=0.2)

    assert batches, "the size cap should have flushed well inside the window"
    assert len(batches[0]) == 10
    assert all(len(b) <= 10 for b in batches)


async def test_idle_stream_yields_no_empty_flushes():
    """No updates → no batches. The window clock starts on the first update only."""
    batcher = CellBatcher(asyncio.Queue(), window_seconds=0.05, max_cells=10)

    batches = await _collect(batcher, seconds=0.25)

    assert batches == []


async def test_encoded_event_id_is_the_batch_high_water_version():
    """`id:` is the batch's max version — the client's `Last-Event-ID` reconnect cursor."""
    case_id = uuid.uuid4()
    batch = [
        _update(case_id, version=7),
        _update(case_id, version=42),
        _update(case_id, version=13),
    ]

    event = _encode_batch(batch)

    assert event["id"] == "42"
    import json

    assert json.loads(event["data"])["max_version"] == 42


# =====================================================================
# Broker fan-out — in-process, pure
# =====================================================================


async def test_broker_fans_out_to_every_subscriber_of_a_case():
    broker = Broker()
    case_id = uuid.uuid4()
    with broker.subscribe(case_id) as q1, broker.subscribe(case_id) as q2:
        update = _update(case_id, version=1)
        broker.publish(update)
        assert q1.get_nowait() is update
        assert q2.get_nowait() is update


async def test_broker_scopes_by_case():
    """A connection on case A never sees case B's cells."""
    broker = Broker()
    case_a, case_b = uuid.uuid4(), uuid.uuid4()
    with broker.subscribe(case_a) as qa, broker.subscribe(case_b) as qb:
        broker.publish(_update(case_a, version=1))
        assert qa.qsize() == 1
        assert qb.qsize() == 0


async def test_broker_unsubscribes_on_context_exit():
    broker = Broker()
    case_id = uuid.uuid4()
    with broker.subscribe(case_id):
        assert broker.subscriber_count(case_id) == 1
    assert broker.subscriber_count(case_id) == 0


async def test_broker_drops_overflow_without_blocking(monkeypatch: pytest.MonkeyPatch):
    """A slow subscriber's overflow is dropped, not blocked — reconcile covers it."""
    monkeypatch.setattr(broker_module, "SUBSCRIBER_QUEUE_MAX", 3)
    broker = Broker()
    case_id = uuid.uuid4()
    with broker.subscribe(case_id) as q:
        for v in range(10):  # ten into a queue of three
            broker.publish(_update(case_id, version=v))
        assert q.qsize() == 3  # capped, and no exception raised


# =====================================================================
# Route wiring
# =====================================================================


def test_stream_route_is_registered():
    from app.main import app

    # This FastAPI keeps included routers unflattened in `app.routes`, so read the
    # OpenAPI paths (which is also what Role 5 generates types from) instead.
    assert "/case/{case_id}/stream" in app.openapi()["paths"]


# =====================================================================
# Listener DB re-read — the only DB-backed part (§4 step 7)
# =====================================================================


@pytest_asyncio.fixture
async def db() -> AsyncSession:
    """A committing session; the case it created is deleted on the way out."""
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
            await session.commit()
    await engine.dispose()


async def _seed_cell(db: AsyncSession, status: CellStatus) -> tuple[Row, Column]:
    case = Case(name="sse test", owner_id=uuid.uuid4())
    db.add(case)
    await db.flush()
    db.info["cases"].append(case.id)
    sheet = Sheet(
        case_id=case.id, name="Тендери", kind=SheetKind.source, grain_label="lot"
    )
    db.add(sheet)
    await db.flush()
    row = Row(
        case_id=case.id,
        sheet_id=sheet.id,
        origin=RowOrigin.connector,
        provenance_jsonb={"tenderID": f"UA-{uuid.uuid4().hex[:8]}", "lotID": "lot-1"},
        depth=0,
    )
    column = Column(
        case_id=case.id, sheet_id=sheet.id, name="winner", value_type="text",
        target_depth=0,
    )
    db.add_all([row, column])
    await db.flush()
    cell = Cell(row_id=row.id, column_id=column.id, status=status)
    db.add(cell)
    await db.commit()
    return row, column


@requires_db
async def test_resolve_update_reads_a_committed_terminal_cell(db: AsyncSession):
    """The re-read carries the authoritative version, case, and status — not the payload."""
    row, column = await _seed_cell(db, CellStatus.Answered)
    cell = await db.get(Cell, (row.id, column.id))

    update = await _resolve_update(db, row.id, column.id)

    assert update is not None
    assert update.case_id == row.case_id
    assert update.row_id == row.id
    assert update.column_id == column.id
    assert update.version == cell.version  # monotonic seq value, addressable
    assert update.status == "Answered"


@requires_db
async def test_resolve_update_drops_a_non_terminal_cell(db: AsyncSession):
    """A `running` NOTIFY (should never fire) is dropped: the read is the authority."""
    row, column = await _seed_cell(db, CellStatus.running)

    assert await _resolve_update(db, row.id, column.id) is None


@requires_db
async def test_resolve_update_drops_a_vanished_cell(db: AsyncSession):
    """Row/column deleted between NOTIFY and read → nothing to publish."""
    assert await _resolve_update(db, uuid.uuid4(), uuid.uuid4()) is None
