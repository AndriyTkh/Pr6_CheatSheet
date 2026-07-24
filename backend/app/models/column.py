"""§4 — the DAG: columns are nodes, `column_input` rows are edges.

Acyclicity, the §2a list gate, and the sheet/grain invariants are enforced
app-side at edge-add (`app/dag/`) — the schema deliberately does not encode them.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
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
from app.models.types import COLUMN_STATUS, INPUT_CONSUMPTION, uuid_pk


class Column(Base):
    __tablename__ = "column"
    __table_args__ = (
        ForeignKeyConstraint(
            ["recipe_id", "recipe_version"], ["recipe.id", "recipe.version"]
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("case.id", ondelete="CASCADE"), nullable=False
    )
    sheet_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sheet.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    #: display/type hint aligned to the recipe's output_schema slot; 'list' opts
    #: the column into the §2a list rules
    value_type: Mapped[str] = mapped_column(Text, nullable=False)
    #: set ONLY when value_type='list' and the list is typed (untyped = NULL)
    item_type: Mapped[str | None] = mapped_column(Text)
    #: NULL for source/seed (connector/upload) columns
    recipe_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    recipe_version: Mapped[int | None] = mapped_column(Integer)
    #: §4 step6 — which output of a 1→M recipe (keeps cache keys from colliding)
    output_slot: Mapped[str] = mapped_column(Text, nullable=False, default="0")
    params_jsonb: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    output_lang: Mapped[str | None] = mapped_column(Text)
    #: §5 rollup derived from cells, not a second source of truth
    status: Mapped[enums.ColumnStatus] = mapped_column(
        COLUMN_STATUS, nullable=False, default=enums.ColumnStatus.pending
    )
    #: §2a — a column runs on ONE grain; the wavefront creates cells only for
    #: rows at this depth
    target_depth: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    sheet: Mapped["Sheet"] = relationship(back_populates="columns")  # noqa: F821

    @property
    def is_list(self) -> bool:
        """§2a — whether this column's cells may hold a typed/untyped list."""
        return self.value_type == "list"


class ColumnInput(Base):
    """One DAG edge: `input_column_id` feeds `column_id`."""

    __tablename__ = "column_input"

    column_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("column.id", ondelete="CASCADE"), primary_key=True
    )
    input_column_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("column.id", ondelete="CASCADE"), primary_key=True
    )
    #: §6 dead-end lock fires when ANY *required* input is terminal-empty
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    #: §2a expansion gate — per edge, because one recipe may take one column
    #: whole and another per-item
    consumes: Mapped[enums.InputConsumption] = mapped_column(
        INPUT_CONSUMPTION, nullable=False, default=enums.InputConsumption.whole_list
    )
