"""The row × column intersection (§4, §5, §9).

`value_jsonb` is deliberately untyped on the wire: a cell may hold a scalar or a
typed list (§2a), and the column's `value_type`/`item_type` is what says which.
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models.enums import CellStatus


class CellOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    row_id: uuid.UUID
    column_id: uuid.UUID
    #: scalar or a JSON array (§2a list cell)
    value_jsonb: Any | None
    status: CellStatus
    #: array aligned index-for-index with a list value (§9)
    citation_jsonb: list[Any]
    cache_key: str | None
    run_id: uuid.UUID | None
    #: monotonic; backs the reconnect catch-up (§4 step 7)
    version: int
    updated_at: datetime


class CellFeedbackOut(BaseModel):
    """§12 — a human verdict on one cell."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    row_id: uuid.UUID
    column_id: uuid.UUID
    verdict: str
    relevance: int | None
    error_type: str | None
    correct_value: Any | None
    judge_id: uuid.UUID | None
    created_at: datetime
