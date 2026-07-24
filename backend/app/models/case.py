"""§11 — case + membership. Private by default."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models import enums
from app.models.types import CASE_ROLE, uuid_pk


class Case(Base):
    __tablename__ = "case"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(Text, nullable=False)
    # fastapi-users owns the user table (§15) — no FK across that boundary.
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    is_private: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    members: Mapped[list["CaseMember"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )
    sheets: Mapped[list["Sheet"]] = relationship(  # noqa: F821
        back_populates="case", cascade="all, delete-orphan"
    )


class CaseMember(Base):
    __tablename__ = "case_member"

    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("case.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    role: Mapped[enums.CaseRole] = mapped_column(CASE_ROLE, nullable=False)

    case: Mapped[Case] = relationship(back_populates="members")
