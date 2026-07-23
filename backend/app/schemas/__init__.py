"""Wire shapes. The OpenAPI spec built from these is Role 5's TypeScript source.

Model names become TS type names via `openapi-typescript`
(tech-stack-decision.md, "Shared FE/BE types") — renaming one is a frontend
break, so treat these names as the published surface.
"""

from app.schemas.case import CaseOut
from app.schemas.cell import CellFeedbackOut, CellOut
from app.schemas.column import ColumnInputOut, ColumnOut
from app.schemas.common import Page, PageParams
from app.schemas.document import DocumentOut
from app.schemas.grid import GridOut
from app.schemas.recipe import RecipeOut, RunOut
from app.schemas.sheet import RowLinkOut, RowOut, SheetOut

__all__ = [
    "CaseOut",
    "CellFeedbackOut",
    "CellOut",
    "ColumnInputOut",
    "ColumnOut",
    "DocumentOut",
    "GridOut",
    "Page",
    "PageParams",
    "RecipeOut",
    "RowLinkOut",
    "RowOut",
    "RunOut",
    "SheetOut",
]
