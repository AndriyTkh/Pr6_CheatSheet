"""§3 recipe registry + §10 run log.

`(recipe_id, version)` is the identity — a shipped version is never mutated, so
old results stay linked to the exact version that produced them.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models import enums
from app.models.types import RECIPE_EXEC_TYPE, RECIPE_SHAPE, uuid_pk


class Recipe(Base):
    __tablename__ = "recipe"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        default=uuid.uuid4,
    )
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    exec_type: Mapped[enums.RecipeExecType] = mapped_column(
        RECIPE_EXEC_TYPE, nullable=False
    )
    shape: Mapped[enums.RecipeShape] = mapped_column(RECIPE_SHAPE, nullable=False)
    # §4 step6 — agent/web/LLM never re-query on identical inputs without a bust.
    volatile: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    params_schema: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    # §3 — enforced server-side at the model edge, not just declared.
    output_schema: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    cite_spec: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    eval_spec: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Run(Base):
    """§10 provenance — one row per dispatched execution."""

    __tablename__ = "run"
    __table_args__ = (
        ForeignKeyConstraint(
            ["recipe_id", "recipe_version"], ["recipe.id", "recipe.version"]
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    recipe_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    recipe_version: Mapped[int] = mapped_column(Integer, nullable=False)
    # §10 — a pinned concrete id, never a floating auto/latest alias.
    model_id: Mapped[str | None] = mapped_column(Text)
    provider_endpoint: Mapped[str | None] = mapped_column(Text)
    prompt_hash: Mapped[str | None] = mapped_column(Text)
    params_jsonb: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    # §10 — fallback cells are NOT cached; their cell.cache_key stays NULL.
    used_fallback: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cache_bust: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cost_usd: Mapped[float | None] = mapped_column(Numeric(12, 6))
    status: Mapped[str] = mapped_column(Text, nullable=False, default="ok")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
