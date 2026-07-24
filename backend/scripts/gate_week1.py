"""Week-1 gate, end to end on real data — no fixture substitution (§14).

Pulls a **live** tender from the public Prozorro API, runs the row-producing
recipe through `services.row_ingest`, commits, then re-reads the rows and cells
back out of Postgres and prints them. Re-runnable: the same tender ids land on
the same `(tenderID, lotID)` rows (§16 #3), so a second run updates rather than
duplicates.

    docker compose up -d
    python scripts/apply_migrations.py
    python scripts/gate_week1.py                       # scan the feed for a lot
    python scripts/gate_week1.py --tender-id <uuid>    # a specific tender

`--tender-id` is what the gate record should cite: a named tender anyone can
re-pull. The scan mode is the convenience path for finding one.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Everything printed here is Ukrainian; a Windows console defaults to cp1252 and
# would raise on the first sheet name rather than show the result.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402

from app.connectors.prozorro import ProzorroClient  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.models import Case, Cell, Column, Row, Sheet  # noqa: E402
from app.models.enums import SheetKind  # noqa: E402
from app.services.row_ingest import ingest_prozorro_lots  # noqa: E402

CASE_NAME = "Week-1 gate — live Prozorro pull"


async def find_awarded_tender(client: ProzorroClient, scan_limit: int) -> str | None:
    """A recent tender with a lot, an active award and real bidders.

    Newest-first: the ascending feed starts in 2015, where the early records are
    mostly `unsuccessful` with no awards at all. A no-award tender still produces
    a valid row (`NotFound` amount, §5), but it exercises far less of the
    extraction — the gate wants the shape with a winner and `@participants`.
    """
    scanned = 0
    fallback: str | None = None
    async for batch, _offset in client.feed(limit=100, descending=True):
        for entry in batch:
            tender_id = entry.get("id")
            if not tender_id:
                continue
            scanned += 1
            if scanned > scan_limit:
                return fallback
            tender = await client.tender(tender_id)
            awarded = any(
                a.get("status") == "active" for a in (tender.get("awards") or [])
            )
            if not awarded:
                continue
            if tender.get("lots") and tender.get("bids"):
                print(f"  lot tender with bidders after {scanned} fetches: {tender_id}")
                return tender_id
            fallback = fallback or tender_id
    return fallback


async def ensure_case_and_sheet(session: AsyncSession) -> Sheet:
    """The case + its implicit source `@tenders` sheet (§2a), created once."""
    existing = (
        await session.execute(
            select(Sheet).join(Case, Case.id == Sheet.case_id).where(Case.name == CASE_NAME)
        )
    ).scalars().first()
    if existing is not None:
        return existing

    case = Case(name=CASE_NAME, owner_id=uuid.uuid4())
    session.add(case)
    await session.flush()
    sheet = Sheet(
        case_id=case.id, name="Тендери", kind=SheetKind.source, grain_label="lot"
    )
    session.add(sheet)
    await session.flush()
    return sheet


async def dump(session: AsyncSession, sheet: Sheet) -> None:
    """Read the result back out of Postgres — the proof it persisted, not just ran."""
    columns = (
        (await session.execute(select(Column).where(Column.sheet_id == sheet.id).order_by(Column.position)))
        .scalars()
        .all()
    )
    rows = (
        (await session.execute(select(Row).where(Row.sheet_id == sheet.id).order_by(Row.position)))
        .scalars()
        .all()
    )
    print(f"\n  sheet {sheet.name!r} ({sheet.kind.value}, grain={sheet.grain_label})")
    print(f"  columns: {', '.join(f'{c.output_slot}:{c.value_type}' for c in columns)}")

    for row in rows:
        print(
            f"\n  row depth={row.depth} tender={row.tender_id} lot={row.lot_id}"
            f"\n    provenance: {row.provenance_jsonb}"
        )
        for column in columns:
            cell = await session.get(Cell, (row.id, column.id))
            if cell is None:
                print(f"    {column.output_slot:<14} — no cell (off grain)")
                continue
            cites = len(cell.citation_jsonb or [])
            print(
                f"    {column.output_slot:<14} {cell.status.value:<16} "
                f"v{cell.version} cites={cites} {_short(cell.value_jsonb)}"
            )


def _short(value: Any, width: int = 70) -> str:
    text = repr(value)
    return text if len(text) <= width else text[: width - 1] + "…"


async def main(tender_ids: Sequence[str], scan_limit: int) -> int:
    async with ProzorroClient() as client:
        if not tender_ids:
            print("no --tender-id given; scanning the feed for an awarded tender …")
            found = await find_awarded_tender(client, scan_limit)
            if found is None:
                print(f"no awarded tender in the first {scan_limit} feed entries")
                return 1
            tender_ids = [found]

    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as session:
            sheet = await ensure_case_and_sheet(session)
            print(f"\ningesting {len(tender_ids)} tender(s) live …")
            result = await ingest_prozorro_lots(
                session, sheet, {"tender_ids": list(tender_ids)}
            )
            await session.commit()
            print(
                f"  run {result.run_id}: {len(result.rows_created)} row(s) created, "
                f"{len(result.rows_updated)} updated, {result.cells_written} cell(s) "
                f"written, {result.cells_skipped_off_grain} skipped off-grain"
            )

        # A fresh session: what follows is read back from Postgres, not from the
        # identity map of the session that wrote it.
        async with factory() as session:
            sheet = await ensure_case_and_sheet(session)
            await dump(session, sheet)
        return 0
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tender-id", action="append", default=[], help="tender id (repeatable)"
    )
    parser.add_argument(
        "--scan-limit", type=int, default=40, help="tenders to fetch while scanning"
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.tender_id, args.scan_limit)))
