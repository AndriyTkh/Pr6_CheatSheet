import uuid
from datetime import datetime
from typing import Optional

from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Run(Base):
    __tablename__ = "run"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    recipe_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    recipe_version: Mapped[int] = mapped_column(Integer, nullable=False)
    model_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    provider_endpoint: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    prompt_hash: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    params_jsonb: Mapped[dict] = mapped_column(JSONB, nullable=False, default={})
    used_fallback: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cache_bust: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cost_usd: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 6), nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="ok")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["recipe_id", "recipe_version"],
            ["recipe.id", "recipe.version"],
        ),
    )
