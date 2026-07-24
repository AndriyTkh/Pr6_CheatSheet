"""The row × column intersection — the memoized result (§4, §5, §9)."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Sequence,
    SmallInteger,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models import enums
from app.models.types import CELL_STATUS, TERMINAL_SCOPE, uuid_pk

#: §4 step7 — monotonic stream version backing `GET /case/:id/cells?since=`
cell_version_seq = Sequence("cell_version_seq")


class Cell(Base):
    __tablename__ = "cell"

    row_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("row.id", ondelete="CASCADE"), primary_key=True
    )
    column_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("column.id", ondelete="CASCADE"), primary_key=True
    )
    #: MAY be a list — the list-in-cell case (§2a, §16 #2)
    value_jsonb: Mapped[Any | None] = mapped_column(JSONB)
    status: Mapped[enums.CellStatus] = mapped_column(
        CELL_STATUS, nullable=False, default=enums.CellStatus.blocked
    )
    #: ARRAY aligned index-for-index to the value items (§9)
    citation_jsonb: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    terminal_scope: Mapped[enums.TerminalScope] = mapped_column(
        TERMINAL_SCOPE, nullable=False, default=enums.TerminalScope.cell
    )
    #: §4 step6. NULL = non-hittable (fallback runs, force-refresh). Terminal-empty
    #: results are NEGATIVE-cached on this key (dead-end lock, §6).
    cache_key: Mapped[str | None] = mapped_column(Text)
    run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("run.id"))
    #: app bumps on every write
    version: Mapped[int] = mapped_column(
        cell_version_seq,
        nullable=False,
        server_default=cell_version_seq.next_value(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    @property
    def is_terminal(self) -> bool:
        return self.status in enums.TERMINAL


class CellFeedback(Base):
    """§12 eval — Oksana's verdicts + the named backup judge's."""

    __tablename__ = "cell_feedback"
    __table_args__ = (
        ForeignKeyConstraint(
            ["row_id", "column_id"], ["cell.row_id", "cell.column_id"], ondelete="CASCADE"
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    row_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    column_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    #: correct | partial | incorrect | cannot_judge
    verdict: Mapped[str] = mapped_column(Text, nullable=False)
    #: 0..3
    relevance: Mapped[int | None] = mapped_column(SmallInteger)
    error_type: Mapped[str | None] = mapped_column(Text)
    correct_value: Mapped[Any | None] = mapped_column(JSONB)
    judge_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
