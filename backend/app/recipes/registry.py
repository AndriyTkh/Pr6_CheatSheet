"""Recipe class → the `recipe` table row that `column`/`run` FK against.

A recipe's Python identity is a slug (`prozorro_lots`); the schema's identity is
`(uuid, version)`. `uuid5` over a fixed namespace bridges the two deterministically
— the same slug is the same uuid in every environment, so a column written in dev
still points at the right recipe row after a fresh migrate (§3, §10).
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Recipe as RecipeRow
from app.recipes.base import Recipe

#: Fixed — changing it re-identifies every shipped recipe. Don't.
RECIPE_NAMESPACE = uuid.UUID("6f9b3a1e-0c4d-5e2a-9b7f-1d3c5a7e9b11")


def recipe_uuid(recipe_id: str) -> uuid.UUID:
    return uuid.uuid5(RECIPE_NAMESPACE, recipe_id)


async def ensure_registered(
    session: AsyncSession, recipe: type[Recipe] | Recipe
) -> RecipeRow:
    """Insert this recipe version if the catalog doesn't have it yet.

    Never *updates* an existing `(id, version)` — a shipped version is immutable
    (CLAUDE.md §5), so a changed schema means a new `version`, not an edit here.
    """
    cls = recipe if isinstance(recipe, type) else type(recipe)
    rid = recipe_uuid(cls.id)
    existing = await session.get(RecipeRow, (rid, cls.version))
    if existing is not None:
        return existing

    row = RecipeRow(
        id=rid,
        version=cls.version,
        name=cls.name,
        exec_type=cls.exec_type,
        shape=cls.shape,
        volatile=cls.volatile,
        params_schema=dict(cls.params_schema),
        output_schema=dict(cls.output_schema),
        cite_spec=dict(cls.cite_spec),
        eval_spec=dict(cls.eval_spec),
    )
    session.add(row)
    await session.flush()
    return row


def catalog() -> dict[tuple[uuid.UUID, int], type[Recipe]]:
    """`(recipe_uuid, version)` → the Python class, for every *imported* recipe.

    Walked from `Recipe.__subclasses__()` rather than kept in a hand-maintained
    list: adding a recipe should not mean remembering to edit this file. The
    shape base classes mark themselves `__abstract__` and are skipped.
    """
    found: dict[tuple[uuid.UUID, int], type[Recipe]] = {}

    def walk(cls: type[Recipe]) -> None:
        for sub in cls.__subclasses__():
            if not sub.__dict__.get("__abstract__", False) and hasattr(sub, "id"):
                found[(recipe_uuid(sub.id), sub.version)] = sub
            walk(sub)

    walk(Recipe)
    return found


def recipe_class(recipe_id: uuid.UUID, version: int) -> type[Recipe] | None:
    """The class a `column.recipe_id`/`recipe_version` pair points at.

    Returns None when nothing has imported that recipe — the caller turns that
    into a cell `Error` rather than crashing a worker (§4 step 7).
    """
    return catalog().get((recipe_id, version))


async def get_registered(
    session: AsyncSession, recipe_id: str, version: int
) -> RecipeRow | None:
    stmt = select(RecipeRow).where(
        RecipeRow.id == recipe_uuid(recipe_id), RecipeRow.version == version
    )
    return (await session.execute(stmt)).scalar_one_or_none()
