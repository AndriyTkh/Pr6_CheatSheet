"""Test fixtures.

The DB-backed tests skip unless `CS_TEST_DATABASE_URL` points at a Postgres 15+
with both migrations applied:

    docker compose up -d
    python scripts/apply_migrations.py
    CS_TEST_DATABASE_URL=postgresql+asyncpg://cheatsheet:cheatsheet@localhost/cheatsheet pytest
"""

import os
import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Case, Column, Sheet
from app.models.enums import SheetKind

TEST_DB_URL = os.environ.get("CS_TEST_DATABASE_URL")
requires_db = pytest.mark.skipif(
    not TEST_DB_URL, reason="set CS_TEST_DATABASE_URL to run DB-backed tests"
)


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    """A session rolled back at the end — tests never leave rows behind."""
    engine = create_async_engine(TEST_DB_URL)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as db:
        try:
            yield db
        finally:
            await db.rollback()
            await engine.dispose()


@pytest_asyncio.fixture
async def source_sheet(session: AsyncSession) -> Sheet:
    """A case with its implicit source sheet — the shape 0002 backfills."""
    case = Case(name="test case", owner_id=uuid.uuid4())
    session.add(case)
    await session.flush()
    sheet = Sheet(
        case_id=case.id, name="Тендери", kind=SheetKind.source, grain_label="lot"
    )
    session.add(sheet)
    await session.flush()
    return sheet


@pytest_asyncio.fixture
async def make_column(session: AsyncSession, source_sheet: Sheet):
    """Factory for a persisted column on the source sheet."""

    async def _make(
        name: str,
        value_type: str = "text",
        target_depth: int = 0,
        sheet: Sheet | None = None,
    ) -> Column:
        column = Column(
            case_id=source_sheet.case_id,
            sheet_id=(sheet or source_sheet).id,
            name=name,
            value_type=value_type,
            target_depth=target_depth,
        )
        session.add(column)
        await session.flush()
        return column

    return _make
