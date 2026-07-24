"""The §2 app-side invariants 2–4. Pure — transient ORM objects, no session.

(Invariant 1, the list gate, is an edge-add rejection and lives in
`test_dag_validation.py`.)
"""

from __future__ import annotations

import uuid

import pytest

from app.dag.invariants import (
    InvariantViolation,
    cell_is_placeable,
    check_cell_placement,
    check_expand_child,
)
from app.models import Column, Row
from app.models.enums import RowOrigin


def _row(sheet_id: uuid.UUID, depth: int = 0) -> Row:
    return Row(
        id=uuid.uuid4(),
        case_id=uuid.uuid4(),
        sheet_id=sheet_id,
        origin=RowOrigin.connector,
        provenance_jsonb={},
        depth=depth,
    )


def _column(sheet_id: uuid.UUID, target_depth: int = 0) -> Column:
    return Column(
        id=uuid.uuid4(),
        case_id=uuid.uuid4(),
        sheet_id=sheet_id,
        name="c",
        value_type="text",
        target_depth=target_depth,
    )


def test_matching_sheet_and_grain_is_placeable():
    sheet = uuid.uuid4()
    assert cell_is_placeable(_row(sheet), _column(sheet)) is True
    check_cell_placement(_row(sheet), _column(sheet))


def test_invariant_2_row_and_column_must_agree_on_sheet():
    row, column = _row(uuid.uuid4()), _column(uuid.uuid4())
    assert cell_is_placeable(row, column) is False
    with pytest.raises(InvariantViolation, match="invariant 2"):
        check_cell_placement(row, column)


def test_invariant_3_cell_only_at_the_columns_target_depth():
    """§2a — a column runs on ONE grain; an off-grain row gets no cell."""
    sheet = uuid.uuid4()
    row, column = _row(sheet, depth=1), _column(sheet, target_depth=0)
    assert cell_is_placeable(row, column) is False
    with pytest.raises(InvariantViolation, match="invariant 3"):
        check_cell_placement(row, column)


def test_invariant_3_expanded_child_grain_matches_its_own_column():
    sheet = uuid.uuid4()
    assert cell_is_placeable(_row(sheet, depth=1), _column(sheet, target_depth=1))


def test_invariant_4_inline_children_stay_on_the_parent_sheet():
    parent = uuid.uuid4()
    check_expand_child(mode="inline", parent_sheet_id=parent, child_sheet_id=parent)
    with pytest.raises(InvariantViolation, match="invariant 4"):
        check_expand_child(
            mode="inline", parent_sheet_id=parent, child_sheet_id=uuid.uuid4()
        )


def test_invariant_4_new_table_children_get_their_own_sheet():
    parent = uuid.uuid4()
    check_expand_child(
        mode="new_table", parent_sheet_id=parent, child_sheet_id=uuid.uuid4()
    )
    with pytest.raises(InvariantViolation, match="invariant 4"):
        check_expand_child(
            mode="new_table", parent_sheet_id=parent, child_sheet_id=parent
        )


def test_unknown_expand_mode_is_rejected():
    sheet = uuid.uuid4()
    with pytest.raises(InvariantViolation):
        check_expand_child(mode="explode", parent_sheet_id=sheet, child_sheet_id=sheet)
