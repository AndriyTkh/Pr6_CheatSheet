"""The recipe catalog (§6). One contract for all three shapes — `base.py`."""

from app.recipes.base import (
    CellRecipe,
    CellResult,
    Citation,
    CrossRowRecipe,
    InputCell,
    InputSpec,
    OutputSlot,
    OutputValidationError,
    Preset,
    ProducedRow,
    Recipe,
    RecipeError,
    RowContext,
    RowProducingRecipe,
)

__all__ = [
    "CellRecipe",
    "CellResult",
    "Citation",
    "CrossRowRecipe",
    "InputCell",
    "InputSpec",
    "OutputSlot",
    "OutputValidationError",
    "Preset",
    "ProducedRow",
    "Recipe",
    "RecipeError",
    "RowContext",
    "RowProducingRecipe",
]
