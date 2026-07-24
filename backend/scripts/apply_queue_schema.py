"""Apply Procrastinate's own schema — the queue tables (§4, §15).

Procrastinate ships and versions its schema itself, so it is deliberately NOT
one of our numbered migrations in `_docs/migrations/`: those are the locked data
contract (CLAUDE.md §5) and are ours to hand-write. This script is the
repeatable step that puts the queue tables in place next to them.

    python scripts/apply_queue_schema.py            # apply if absent
    python scripts/apply_queue_schema.py --status   # report, change nothing
    python scripts/apply_queue_schema.py --database-url postgresql+asyncpg://…

Idempotent by check-then-apply: `procrastinate_jobs` existing means the schema
is already there, and re-running the DDL would fail rather than no-op. To move
an existing installation across a Procrastinate version, use Procrastinate's own
`procrastinate schema --migrations-path` output — do not re-run this.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

import asyncpg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings  # noqa: E402
from app.tasks.app import build_app, queue_dsn, use_selector_event_loop  # noqa: E402

SENTINEL_TABLE = "procrastinate_jobs"


async def schema_present(dsn: str) -> bool:
    conn = await asyncpg.connect(dsn)
    try:
        return bool(await conn.fetchval("SELECT to_regclass($1)", SENTINEL_TABLE))
    finally:
        await conn.close()


async def main(database_url: str | None, status_only: bool) -> int:
    url = database_url or settings.database_url
    dsn = queue_dsn(url)
    present = await schema_present(dsn)

    if present:
        print(f"  applied  procrastinate schema ({SENTINEL_TABLE} exists)")
        return 0
    if status_only:
        print("  PENDING  procrastinate schema")
        return 0

    print("  applying procrastinate schema …")
    app = build_app(url)
    async with app.open_async():
        await app.schema_manager.apply_schema_async()
    print("  ok       procrastinate schema")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status", action="store_true", help="report, apply nothing")
    parser.add_argument(
        "--database-url",
        default=None,
        help="override CS_DATABASE_URL (SQLAlchemy or plain DSN form)",
    )
    args = parser.parse_args()
    use_selector_event_loop()
    raise SystemExit(asyncio.run(main(args.database_url, args.status)))
