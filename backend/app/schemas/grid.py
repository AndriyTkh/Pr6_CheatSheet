"""The one payload that renders a sheet.

Three round trips (columns, rows, cells) to paint a grid is three chances for
the client to hold a half-loaded sheet. `GridOut` is all three at one `sheet_id`
and one `as_of_version`, so a reconnecting client knows exactly where the live
stream should resume from (§4 step 7).
"""

from pydantic import BaseModel

from app.schemas.cell import CellOut
from app.schemas.column import ColumnOut
from app.schemas.sheet import RowOut, SheetOut


class GridOut(BaseModel):
    """One sheet's grid: its columns, its rows, and the cells between them."""

    sheet: SheetOut
    columns: list[ColumnOut]
    rows: list[RowOut]
    #: sparse — a cell exists only where `row.depth == column.target_depth` (§2a),
    #: so absence is normal and means "off-grain", not "not run yet"
    cells: list[CellOut]
    #: highest `cell.version` in this payload; 0 when the sheet has no cells
    as_of_version: int
    #: rows are paginated; columns are not (a sheet has tens, not thousands)
    row_total: int
    row_limit: int
    row_offset: int
