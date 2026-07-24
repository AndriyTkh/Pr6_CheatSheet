"""Edge-add rejections (§4 step 2).

Both checks fail the *add-column action*, before anything exists: no cell is
created, nothing is enqueued, nothing is spent. That is the whole point of
catching them at composition time rather than as a runtime cell status.
"""

import uuid


class EdgeRejected(Exception):
    """Base for an add-column rejection. Carries a journalist-readable message."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class CycleRejected(EdgeRejected):
    """The new edge would close a loop — the column graph must stay acyclic."""

    def __init__(self, cycle_names: list[str]) -> None:
        self.cycle_names = cycle_names
        super().__init__(
            "Ця колонка створила б цикл: " + " → ".join(cycle_names)
        )


class ListGateRejected(EdgeRejected):
    """§2a — a `per_item` input pointed at a list column.

    The message names the column and offers the two Expand modes, because the
    fix is a user action ("expand it first"), not a retry.
    """

    def __init__(self, column_id: uuid.UUID, column_name: str) -> None:
        self.column_id = column_id
        self.column_name = column_name
        super().__init__(
            f"Колонка «{column_name}» містить списки, а цей рецепт потребує "
            f"один рядок на елемент. Спочатку розгорніть її (Expand): "
            f"«inline» — дочірні рядки в цьому ж аркуші, "
            f"«new_table» — окремий похідний аркуш."
        )


class GrainRejected(EdgeRejected):
    """§2a — inputs must live on the same sheet and the same grain.

    A column runs on ONE grain; the wavefront creates cells only for rows at
    `target_depth`, so an edge across grains could never produce a cell.
    """
