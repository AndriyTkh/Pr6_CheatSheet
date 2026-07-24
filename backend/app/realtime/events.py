"""The wire shape of a streamed cell update (§4 step 7).

Deliberately tiny: the frontend re-reads nothing on a normal update — the value,
status and citation the grid needs already rode in on the update. `version` is
the load-bearing field. It is the cell's `cell_version_seq` value, strictly
monotonic across every terminal write (real run, cache hit, `_fail`, and the
wavefront's own `blocked → pending` promotion — see the wavefront handoff), so
the reconcile-on-reconnect task can page the whole stream on
`GET /case/:id/cells?since=<version>`. Coalescing keeps the **highest** version
per cell, never a lower one, so the number the client last saw never goes
backwards.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CellUpdate:
    """One cell reached a terminal status. Addressable by `(row_id, column_id)`."""

    case_id: uuid.UUID
    row_id: uuid.UUID
    column_id: uuid.UUID
    #: `cell.version` — monotonic, the reconcile cursor. Never decreases per cell.
    version: int
    #: the §5 terminal status, as its enum value (`"Answered"`, `"NotFound"`, …)
    status: str

    @property
    def key(self) -> tuple[uuid.UUID, uuid.UUID]:
        """The coalescing identity — two updates to the same cell collapse to one."""
        return (self.row_id, self.column_id)

    def as_dict(self) -> dict[str, str | int]:
        return {
            "row_id": str(self.row_id),
            "column_id": str(self.column_id),
            "version": self.version,
            "status": self.status,
        }
