"""§2a — sheets and their rows.

A case is a set of sheets, not one grid, so `sheet_id` is on the wire for every
row: a client that renders rows without knowing their sheet is the exact bug
this task exists to prevent.
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models.enums import RowLinkRelation, RowOrigin, RowState, SheetKind


class SheetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    case_id: uuid.UUID
    name: str
    kind: SheetKind
    #: 'lot' | 'company' | 'pair' | 'document' — the grain, in words
    grain_label: str
    #: set on derived sheets; the DAG spans sheets at this boundary only (§2a)
    parent_sheet_id: uuid.UUID | None
    produced_by_run_id: uuid.UUID | None
    position: int
    created_at: datetime


class RowOut(BaseModel):
    """One lot / company / pair, depending on the sheet's grain."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    case_id: uuid.UUID
    sheet_id: uuid.UUID
    origin: RowOrigin
    provenance_jsonb: dict[str, Any]
    generated_by_run_id: uuid.UUID | None
    state: RowState
    merged_into_row_id: uuid.UUID | None
    # --- inline expansion (§2a): the band of children under a parent ---
    parent_row_id: uuid.UUID | None
    #: 0 = source grain, 1 = expanded child. A column only has cells on rows at
    #: its own `target_depth`, so the grid must group by this, not flatten it.
    depth: int
    ordinal: int | None
    position: int
    # --- lot grain (§16 #3), generated from provenance_jsonb, read-only ---
    tender_id: str | None
    lot_id: str | None
    created_at: datetime


class RowLinkOut(BaseModel):
    """§2a N-ary lineage — a deduplicated company links to every lot it bid on."""

    model_config = ConfigDict(from_attributes=True)

    child_row_id: uuid.UUID
    parent_row_id: uuid.UUID
    relation: RowLinkRelation
    source_cell_row_id: uuid.UUID | None
    source_cell_column_id: uuid.UUID | None
    #: index into the source cell's value/citation arrays (§9)
    source_ordinal: int | None
    created_at: datetime
