"""The four app-side invariants of §2 that the schema deliberately drops.

All four need cross-table state, which is why 0002's closing block lists them as
*app-side* rather than encoding them (same reasoning that put the DAG acyclicity
check in the app in 0001). Invariant 1 — the §2a list gate — lives in
`validation.py`, because it fires at edge-add while the user is still composing.
The other three fire at *write* time, which is here:

    2. a cell's row and column must agree on `sheet_id`;
    3. a cell exists only where `row.depth == column.target_depth` (§4 step 5);
    4. `inline` expanded children share their parent's sheet, `new_table`
       children do not.

These are assertions, not user-facing rejections: reaching one means the engine
tried to write a cell it should never have created, so they raise rather than
returning a typed status.
"""

from __future__ import annotations

import uuid

from app.models import Column, Row


class InvariantViolation(Exception):
    """An engine bug — a write that the §2 invariants forbid."""


def cell_is_placeable(row: Row, column: Column) -> bool:
    """Invariants 2 + 3 as a predicate — "should this cell exist at all?"

    The wavefront calls this to *decide*, so an off-grain row simply gets no
    cell (§2a) instead of an error. `check_cell_placement` is the same pair of
    rules for code that has already decided and must not be wrong.
    """
    return row.sheet_id == column.sheet_id and row.depth == column.target_depth


def check_cell_placement(row: Row, column: Column) -> None:
    """Invariants 2 + 3, enforced. Raises `InvariantViolation`."""
    if row.sheet_id != column.sheet_id:
        raise InvariantViolation(
            f"cell({row.id}, {column.id}): row is on sheet {row.sheet_id} but "
            f"column is on sheet {column.sheet_id} — invariant 2 (§2)"
        )
    if row.depth != column.target_depth:
        raise InvariantViolation(
            f"cell({row.id}, {column.id}): row.depth={row.depth} but "
            f"column.target_depth={column.target_depth} — a column runs on ONE "
            f"grain, invariant 3 (§2a, §4 step 5)"
        )


def check_expand_child(
    *,
    mode: str,
    parent_sheet_id: uuid.UUID,
    child_sheet_id: uuid.UUID,
) -> None:
    """Invariant 4 — the two Expand modes differ exactly in sheet identity.

    `inline` keeps the children in the source sheet (at `depth=1`, rendered
    under their parent); `new_table` makes them rows of a *derived* sheet. A
    child on the wrong side of that line silently breaks the grain rules every
    other check depends on.
    """
    if mode == "inline" and child_sheet_id != parent_sheet_id:
        raise InvariantViolation(
            f"inline expand put a child on sheet {child_sheet_id}, not the "
            f"parent's {parent_sheet_id} — invariant 4 (§2a)"
        )
    if mode == "new_table" and child_sheet_id == parent_sheet_id:
        raise InvariantViolation(
            f"new_table expand left the children on the parent sheet "
            f"{parent_sheet_id} — invariant 4 (§2a)"
        )
    if mode not in ("inline", "new_table"):
        raise InvariantViolation(f"unknown expand mode {mode!r} (§2a)")
