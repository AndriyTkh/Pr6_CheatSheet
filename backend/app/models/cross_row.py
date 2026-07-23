"""§8, §16 #6 — cross-row signals live outside the column DAG.

Keeping them out of the grid is what preserves recipe isolation: a cross-row
recipe declares its input row set explicitly instead of reaching across rows.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.types import uuid_pk


class CrossRowResult(Base):
    __tablename__ = "cross_row_result"
    __table_args__ = (
        ForeignKeyConstraint(
            ["recipe_id", "recipe_version"], ["recipe.id", "recipe.version"]
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("case.id", ondelete="CASCADE"), nullable=False
    )
    recipe_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    recipe_version: Mapped[int] = mapped_column(Integer, nullable=False)
    #: explicit user-declared input set (§8)
    row_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False
    )
    column_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False
    )
    signal: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    #: shared attribute + BOTH source records — no naked assertion (§8)
    evidence_jsonb: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    #: for is_stale; never auto-rerun (§4)
    input_versions_jsonb: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    is_stale: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("run.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
