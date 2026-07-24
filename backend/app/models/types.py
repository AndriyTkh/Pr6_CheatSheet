"""Shared column helpers for the ORM mirror.

The Postgres enum types are created by the migrations, so every ORM enum is
declared with `create_type=False` — SQLAlchemy must never try to own them.
"""

import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID
from sqlalchemy.orm import mapped_column

from app.models import enums


def pg_enum(python_enum: type, name: str) -> ENUM:
    """A Postgres enum owned by the migration, mirrored (not created) here."""
    return ENUM(
        python_enum,
        name=name,
        create_type=False,
        values_callable=lambda e: [m.value for m in e],
    )


def uuid_pk():
    """`uuid PRIMARY KEY DEFAULT gen_random_uuid()` (pgcrypto, 0001)."""
    return mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        default=uuid.uuid4,
    )


def jsonb(default: Any = None, nullable: bool = False, server_default: str | None = None):
    kwargs: dict[str, Any] = {"nullable": nullable}
    if server_default is not None:
        kwargs["server_default"] = text(f"'{server_default}'::jsonb")
    if default is not None:
        kwargs["default"] = default
    return mapped_column(JSONB, **kwargs)


CELL_STATUS = pg_enum(enums.CellStatus, "cell_status")
COLUMN_STATUS = pg_enum(enums.ColumnStatus, "column_status")
RECIPE_EXEC_TYPE = pg_enum(enums.RecipeExecType, "recipe_exec_type")
RECIPE_SHAPE = pg_enum(enums.RecipeShape, "recipe_shape")
ROW_ORIGIN = pg_enum(enums.RowOrigin, "row_origin")
ROW_STATE = pg_enum(enums.RowState, "row_state")
TERMINAL_SCOPE = pg_enum(enums.TerminalScope, "terminal_scope")
CASE_ROLE = pg_enum(enums.CaseRole, "case_role")
SHEET_KIND = pg_enum(enums.SheetKind, "sheet_kind")
ROW_LINK_RELATION = pg_enum(enums.RowLinkRelation, "row_link_relation")
INPUT_CONSUMPTION = pg_enum(enums.InputConsumption, "input_consumption")
