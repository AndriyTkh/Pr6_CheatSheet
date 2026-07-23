import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, SmallInteger, String, Text, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Row(Base):
    __tablename__ = "row"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("case.id", ondelete="CASCADE"), nullable=False
    )
    sheet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sheet.id", ondelete="CASCADE"), nullable=False
    )
    origin: Mapped[str] = mapped_column(String, nullable=False)  # row_origin enum
    provenance_jsonb: Mapped[dict] = mapped_column(JSONB, nullable=False, default={})
    generated_by_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("run.id"), nullable=True
    )
    state: Mapped[str] = mapped_column(
        String, nullable=False, default="active"
    )  # row_state enum
    merged_into_row_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("row.id"), nullable=True
    )
    parent_row_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("row.id", ondelete="CASCADE"), nullable=True
    )
    depth: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    ordinal: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # GENERATED ALWAYS columns — Postgres computes these from provenance_jsonb
    tender_id: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, insert=False, update=False
    )
    lot_id: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, insert=False, update=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
