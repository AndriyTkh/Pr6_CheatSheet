"""§4 DAG nodes and edges, as the grid sees them."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models.enums import ColumnStatus, InputConsumption


class ColumnOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    case_id: uuid.UUID
    sheet_id: uuid.UUID
    name: str
    #: 'list' opts the column into the §2a list rules
    value_type: str
    #: only meaningful when value_type='list'; NULL = untyped list
    item_type: str | None
    #: NULL on source/seed columns (connector, upload)
    recipe_id: uuid.UUID | None
    recipe_version: int | None
    output_slot: str
    params_jsonb: dict[str, Any]
    output_lang: str | None
    #: rollup over this column's cells (§5) — display only
    status: ColumnStatus
    #: §2a — the grain this column runs on; cells exist only where
    #: `row.depth == target_depth`
    target_depth: int
    position: int
    created_at: datetime


class ColumnInputOut(BaseModel):
    """One DAG edge. `consumes` is what the §2a expansion gate checks."""

    model_config = ConfigDict(from_attributes=True)

    column_id: uuid.UUID
    input_column_id: uuid.UUID
    is_required: bool
    consumes: InputConsumption
