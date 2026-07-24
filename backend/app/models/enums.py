"""Python mirrors of the Postgres enums in migrations 0001 + 0002.

Names and members must match the migrations exactly — the ORM mirrors the
schema, never the reverse (CLAUDE.md §5, ARCHITECTURE.md §2).
"""

from enum import Enum


class CellStatus(str, Enum):
    """§5 typed cell status — non-terminal lifecycle + the eight terminals."""

    # non-terminal lifecycle
    blocked = "blocked"
    pending = "pending"
    running = "running"
    # terminal — P0 active set (the seven of §5, plus NotApplicable from 0002)
    Answered = "Answered"
    InsufficientData = "InsufficientData"
    NotFound = "NotFound"
    SourceUnavailable = "SourceUnavailable"
    ConflictingEvidence = "ConflictingEvidence"
    Error = "Error"
    NeedsReview = "NeedsReview"
    NotApplicable = "NotApplicable"
    # terminal — DORMANT (§5): deferred Merge / row-gating only
    Rejected = "Rejected"


#: §5 lock table. Terminal-empty inputs lock downstream to InsufficientData.
TERMINAL_EMPTY: frozenset[CellStatus] = frozenset(
    {
        CellStatus.InsufficientData,
        CellStatus.NotFound,
        CellStatus.SourceUnavailable,
    }
)

#: §5 "structurally void" — propagates as ITSELF, never downgraded.
STRUCTURALLY_VOID: frozenset[CellStatus] = frozenset({CellStatus.NotApplicable})

#: §5 needs-a-human — no lock, a person may resolve it.
NEEDS_HUMAN: frozenset[CellStatus] = frozenset(
    {
        CellStatus.ConflictingEvidence,
        CellStatus.Error,
        CellStatus.NeedsReview,
    }
)

#: Everything that ends an operation. `Rejected` is dormant but still terminal.
TERMINAL: frozenset[CellStatus] = (
    frozenset({CellStatus.Answered, CellStatus.Rejected})
    | TERMINAL_EMPTY
    | STRUCTURALLY_VOID
    | NEEDS_HUMAN
)


class ColumnStatus(str, Enum):
    """§5 rollup derived from cells — not a second source of truth."""

    pending = "pending"
    running = "running"
    partial = "partial"
    done = "done"
    stale = "stale"


class RecipeExecType(str, Enum):
    """§3 — func = deterministic, agent = tool-using LLM loop."""

    func = "func"
    agent = "agent"


class RecipeShape(str, Enum):
    """§6 three shapes."""

    cell = "cell"
    row = "row"
    cross_row = "cross_row"


class RowOrigin(str, Enum):
    """§16 #7, extended by 0002 with `derived` (§2a)."""

    connector = "connector"
    upload = "upload"
    generated = "generated"
    derived = "derived"


class RowState(str, Enum):
    """DORMANT axis — P0 rows are always `active` (§5)."""

    active = "active"
    merged = "merged"


class TerminalScope(str, Enum):
    """DORMANT — P0 is always `cell` (§5)."""

    cell = "cell"
    row = "row"


class CaseRole(str, Enum):
    """§11 — reviewer is Stretch."""

    owner = "owner"
    editor = "editor"
    viewer = "viewer"


class SheetKind(str, Enum):
    """§2a — a case is a set of sheets."""

    source = "source"
    derived = "derived"


class RowLinkRelation(str, Enum):
    """§2a lineage."""

    expanded_from = "expanded_from"
    pair_member = "pair_member"


class InputConsumption(str, Enum):
    """§2a expansion gate — declared per DAG edge, not per recipe."""

    whole_list = "whole_list"
    per_item = "per_item"
