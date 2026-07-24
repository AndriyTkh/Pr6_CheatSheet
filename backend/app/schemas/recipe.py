"""§3 recipe registry + §10 run log."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models.enums import RecipeExecType, RecipeShape


class RecipeOut(BaseModel):
    """Identity is `(id, version)` — a shipped version is never mutated."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version: int
    name: str
    exec_type: RecipeExecType
    shape: RecipeShape
    volatile: bool
    params_schema: dict[str, Any]
    output_schema: dict[str, Any]
    cite_spec: dict[str, Any]
    eval_spec: dict[str, Any]
    created_at: datetime


class RunOut(BaseModel):
    """§10 provenance. No prompt text, no key — `prompt_hash` and nothing more."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    recipe_id: uuid.UUID
    recipe_version: int
    #: a pinned concrete model id, never a floating alias
    model_id: str | None
    provider_endpoint: str | None
    prompt_hash: str | None
    params_jsonb: dict[str, Any]
    used_fallback: bool
    cache_bust: bool
    cost_usd: Decimal | None
    status: str
    created_at: datetime
