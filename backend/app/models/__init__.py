"""ORM mirror of the locked schema (`_docs/migrations/0001` + `0002`).

The migrations are the contract — these models follow them, never the reverse
(CLAUDE.md §5). Adding a field here that the migrations don't have is a bug.
"""

from app.models.case import Case, CaseMember
from app.models.cell import Cell, CellFeedback, cell_version_seq
from app.models.column import Column, ColumnInput
from app.models.cross_row import CrossRowResult
from app.models.document import Chunk, Document
from app.models.enums import (
    NEEDS_HUMAN,
    STRUCTURALLY_VOID,
    TERMINAL,
    TERMINAL_EMPTY,
    CaseRole,
    CellStatus,
    ColumnStatus,
    InputConsumption,
    RecipeExecType,
    RecipeShape,
    RowLinkRelation,
    RowOrigin,
    RowState,
    SheetKind,
    TerminalScope,
)
from app.models.recipe import Recipe, Run
from app.models.sheet import Row, RowLink, Sheet

__all__ = [
    "Case",
    "CaseMember",
    "Cell",
    "CellFeedback",
    "cell_version_seq",
    "Chunk",
    "Column",
    "ColumnInput",
    "CrossRowResult",
    "Document",
    "Recipe",
    "Row",
    "RowLink",
    "Run",
    "Sheet",
    # enums
    "CaseRole",
    "CellStatus",
    "ColumnStatus",
    "InputConsumption",
    "RecipeExecType",
    "RecipeShape",
    "RowLinkRelation",
    "RowOrigin",
    "RowState",
    "SheetKind",
    "TerminalScope",
    # status groupings (§5)
    "NEEDS_HUMAN",
    "STRUCTURALLY_VOID",
    "TERMINAL",
    "TERMINAL_EMPTY",
]
