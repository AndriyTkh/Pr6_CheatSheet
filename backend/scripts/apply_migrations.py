"""Apply the numbered migrations in order, tracking what's already applied.

Not Alembic: the migrations are hand-written SQL and are the contract
(CLAUDE.md §5) — this only runs them and records which ones ran. A new schema
change is a *new numbered file*, never an edit to an applied one.

    python scripts/apply_migrations.py            # apply pending
    python scripts/apply_migrations.py --status   # show what's applied
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

import asyncpg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings  # noqa: E402

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "_docs" / "migrations"

TRACKING_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migration (
  name       text PRIMARY KEY,
  applied_at timestamptz NOT NULL DEFAULT now()
)
"""


def dsn() -> str:
    """asyncpg wants a plain postgres:// DSN, not SQLAlchemy's +asyncpg form."""
    return settings.database_url.replace("postgresql+asyncpg://", "postgresql://")


def migration_files() -> list[Path]:
    return sorted(MIGRATIONS_DIR.glob("[0-9][0-9][0-9][0-9]_*.sql"))


async def main(status_only: bool) -> int:
    conn = await asyncpg.connect(dsn())
    try:
        await conn.execute(TRACKING_TABLE)
        applied = {r["name"] for r in await conn.fetch("SELECT name FROM schema_migration")}

        for path in migration_files():
            if path.name in applied:
                print(f"  applied  {path.name}")
                continue
            if status_only:
                print(f"  PENDING  {path.name}")
                continue
            print(f"  applying {path.name} …")
            # Run the file as-is, NOT wrapped in a transaction of ours: 0002
            # opens its own BEGIN/COMMIT, and nesting would commit it early.
            # A multi-statement execute is already implicitly atomic in PG.
            await conn.execute(path.read_text(encoding="utf-8"))
            await conn.execute(
                "INSERT INTO schema_migration (name) VALUES ($1)", path.name
            )
            print(f"  ok       {path.name}")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status", action="store_true", help="show state, apply nothing")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.status)))
