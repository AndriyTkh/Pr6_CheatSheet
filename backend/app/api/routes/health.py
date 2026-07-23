"""Health + readiness. Reports config *presence*, never a secret value (§11)."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness — no dependencies touched."""
    return {"status": "ok"}


@router.get("/health/ready")
async def ready(db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    """Readiness — the DB answers and both migrations are applied.

    `NotApplicable` is the marker for 0002: it is the enum value that migration
    adds, so its presence is a cheap, exact check that the schema the models
    mirror is the schema actually in the database.
    """
    await db.execute(text("SELECT 1"))
    has_0002 = await db.scalar(
        text(
            "SELECT EXISTS (SELECT 1 FROM pg_enum e "
            "JOIN pg_type t ON t.oid = e.enumtypid "
            "WHERE t.typname = 'cell_status' AND e.enumlabel = 'NotApplicable')"
        )
    )
    return {
        "status": "ok",
        "database": "ok",
        "migration_0002_applied": bool(has_0002),
        "config": settings.masked(),
    }
