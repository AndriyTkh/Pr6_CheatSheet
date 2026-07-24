"""§2a — sheets, rows, and the two lineage mechanisms.

`row.parent_row_id` is the 1:1 TREE (grain, sort order, inline rendering);
`row_link` is the N-ary GRAPH (evidence, dedup, pairs). Every expanded child
writes BOTH so downstream code walks one path (§16 #2).
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Computed,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    SmallInteger,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models import enums
from app.models.types import ROW_LINK_RELATION, ROW_ORIGIN, ROW_STATE, SHEET_KIND, uuid_pk


class Sheet(Base):
    __tablename__ = "sheet"

    id: Mapped[uuid.UUID] = uuid_pk()
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("case.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[enums.SheetKind] = mapped_column(SHEET_KIND, nullable=False)
    #: 'lot' | 'company' | 'pair' | 'document'
    grain_label: Mapped[str] = mapped_column(Text, nullable=False)
    # A source sheet has no parent; a derived sheet must have one — the DAG spans
    # sheets at the sheet boundary, so the boundary is recorded here.
    parent_sheet_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sheet.id", ondelete="CASCADE")
    )
    produced_by_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("run.id"))
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    case: Mapped["Case"] = relationship(back_populates="sheets")  # noqa: F821
    rows: Mapped[list["Row"]] = relationship(
        back_populates="sheet", cascade="all, delete-orphan"
    )
    columns: Mapped[list["Column"]] = relationship(  # noqa: F821
        back_populates="sheet", cascade="all, delete-orphan"
    )


class Row(Base):
    """§16 #3 — one row = one Prozorro tender **lot**."""

    __tablename__ = "row"

    id: Mapped[uuid.UUID] = uuid_pk()
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("case.id", ondelete="CASCADE"), nullable=False
    )
    sheet_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sheet.id", ondelete="CASCADE"), nullable=False
    )
    origin: Mapped[enums.RowOrigin] = mapped_column(ROW_ORIGIN, nullable=False)
    #: keyed `(tenderID, lotID)` for connector rows (§16 #3)
    provenance_jsonb: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    #: §16 #7 — set iff origin='generated'
    generated_by_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("run.id"))
    state: Mapped[enums.RowState] = mapped_column(
        ROW_STATE, nullable=False, default=enums.RowState.active
    )
    merged_into_row_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("row.id"))

    # --- expansion (§2a) ---
    parent_row_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("row.id", ondelete="CASCADE")
    )
    #: 0 = source grain, 1 = expanded child
    depth: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    #: index in the source list; NULL at depth 0
    ordinal: Mapped[int | None] = mapped_column(Integer)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # --- lot grain (§16 #3) ---
    # GENERATED ALWAYS ... STORED in 0002 — Computed() keeps the ORM from ever
    # emitting them in INSERT/UPDATE. Write `provenance_jsonb`, read these.
    tender_id: Mapped[str | None] = mapped_column(
        Text, Computed("provenance_jsonb ->> 'tenderID'", persisted=True)
    )
    lot_id: Mapped[str | None] = mapped_column(
        Text, Computed("provenance_jsonb ->> 'lotID'", persisted=True)
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    sheet: Mapped[Sheet] = relationship(back_populates="rows")


class RowLink(Base):
    """§2a — N-ary lineage back to parents (dedup, pairs, expand)."""

    __tablename__ = "row_link"
    __table_args__ = (
        ForeignKeyConstraint(
            ["source_cell_row_id", "source_cell_column_id"],
            ["cell.row_id", "cell.column_id"],
            ondelete="SET NULL",
        ),
    )

    child_row_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("row.id", ondelete="CASCADE"), primary_key=True
    )
    parent_row_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("row.id", ondelete="CASCADE"), primary_key=True
    )
    relation: Mapped[enums.RowLinkRelation] = mapped_column(
        ROW_LINK_RELATION, primary_key=True
    )
    source_cell_row_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    source_cell_column_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    #: index into the source cell's value_jsonb array — and into citation_jsonb,
    #: which is how an item's citation reaches the child row (§9)
    source_ordinal: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
