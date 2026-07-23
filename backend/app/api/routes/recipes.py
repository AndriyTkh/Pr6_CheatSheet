"""§3 recipe catalog — what a column can be built from.

Not sheet-scoped: recipes are global to the installation, not to a case. The
catalog is what the "add column" picker reads.
"""

import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.deps import DbSession, Paging
from app.models import Recipe
from app.schemas import Page, RecipeOut
from app.services import grid_query

router = APIRouter(prefix="/recipes", tags=["recipes"])


@router.get("", response_model=Page[RecipeOut], summary="List recipe versions")
async def list_recipes(db: DbSession, paging: Paging) -> Page[RecipeOut]:
    """Every `(id, version)`, newest version first.

    Versions are listed rather than collapsed to a latest: a shipped version is
    never mutated, and an existing column stays pinned to the exact one that
    produced its results (§3, §10).
    """
    stmt = select(Recipe).order_by(Recipe.name, Recipe.version.desc())
    total = await grid_query.count_of(db, stmt)
    result = await db.scalars(stmt.limit(paging.limit).offset(paging.offset))
    return Page[RecipeOut](
        items=[RecipeOut.model_validate(r) for r in result],
        total=total,
        limit=paging.limit,
        offset=paging.offset,
    )


@router.get(
    "/{recipe_id}/versions/{version}",
    response_model=RecipeOut,
    summary="Get one pinned recipe version",
)
async def get_recipe_version(
    db: DbSession, recipe_id: uuid.UUID, version: int
) -> RecipeOut:
    recipe = await db.get(Recipe, (recipe_id, version))
    if recipe is None:
        raise HTTPException(status_code=404, detail=f"No recipe {recipe_id} v{version}")
    return RecipeOut.model_validate(recipe)
