"""§7 document modes, §9 citations, §11 the external gate."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from app.db.base import Base
from app.models.types import uuid_pk


class Document(Base):
    __tablename__ = "document"

    id: Mapped[uuid.UUID] = uuid_pk()
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("case.id", ondelete="CASCADE"), nullable=False
    )
    #: package docs live under their row (§6)
    row_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("row.id", ondelete="CASCADE")
    )
    url: Mapped[str | None] = mapped_column(Text)
    doc_type: Mapped[str | None] = mapped_column(Text)
    format: Mapped[str | None] = mapped_column(Text)
    #: Cloudflare R2 (§15)
    storage_key: Mapped[str | None] = mapped_column(Text)
    has_text_layer: Mapped[bool | None] = mapped_column(Boolean)
    #: null | pending | ok | failed (§7)
    ocr_status: Mapped[str | None] = mapped_column(Text)
    #: citations stay in the source language (§9)
    source_lang: Mapped[str | None] = mapped_column(Text)
    #: §11 HARD GATE — connector=true, upload=false until attested. Every recipe
    #: dispatch checks this on every source document in `row_context`.
    external_ok: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Chunk(Base):
    __tablename__ = "chunk"

    id: Mapped[uuid.UUID] = uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document.id", ondelete="CASCADE"), nullable=False
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    page: Mapped[int | None] = mapped_column(Integer)
    char_start: Mapped[int | None] = mapped_column(Integer)
    char_end: Mapped[int | None] = mapped_column(Integer)
    #: dim PINNED to embed_model_id (§10)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024))
    #: §10 — retrieval compares only same-model vectors
    embed_model_id: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
