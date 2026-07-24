"""§3 — the recipe contract's two enforced rules: the dead-end lock and the
server-side output-schema check."""

import uuid
from typing import Any, ClassVar, Mapping, Sequence

import pytest

from app.models.enums import CellStatus, RecipeExecType
from app.recipes.base import (
    CellRecipe,
    CellResult,
    InputCell,
    InputSpec,
    OutputSlot,
    RecipeError,
    RowContext,
)


class Echo(CellRecipe):
    id: ClassVar[str] = "echo"
    name: ClassVar[str] = "Echo"
    exec_type: ClassVar[RecipeExecType] = RecipeExecType.func
    inputs: ClassVar[Sequence[InputSpec]] = (
        InputSpec("src", required=True),
        InputSpec("hint", required=False),
    )
    outputs: ClassVar[Sequence[OutputSlot]] = (OutputSlot("out", "text"),)
    output_schema: ClassVar[Mapping[str, Any]] = {
        "type": "object",
        "properties": {"out": {"type": ["string", "null"]}},
        "required": ["out"],
    }

    def __init__(self, value: Any = "ok") -> None:
        self._value = value

    async def exec(self, row_context, params):
        return [CellResult(slot="out", value=self._value, status=CellStatus.Answered)]


def ctx(**inputs: InputCell) -> RowContext:
    return RowContext(
        row_id=uuid.uuid4(),
        sheet_id=uuid.uuid4(),
        depth=0,
        provenance={},
        inputs=inputs,
    )


async def test_answered_input_dispatches_normally():
    context = ctx(src=InputCell("src", "хтось", CellStatus.Answered))
    [result] = await Echo().run(context, {})
    assert result.status is CellStatus.Answered
    assert result.value == "ok"


@pytest.mark.parametrize(
    "empty",
    [CellStatus.InsufficientData, CellStatus.NotFound, CellStatus.SourceUnavailable],
)
async def test_terminal_empty_required_input_locks_to_insufficient_data(empty):
    context = ctx(src=InputCell("src", None, empty))
    [result] = await Echo().run(context, {})
    assert result.status is CellStatus.InsufficientData
    assert result.value is None


async def test_not_applicable_propagates_as_itself():
    # §5/§6 — the reason must survive the hop, not be downgraded.
    context = ctx(src=InputCell("src", None, CellStatus.NotApplicable))
    [result] = await Echo().run(context, {})
    assert result.status is CellStatus.NotApplicable


async def test_missing_optional_input_does_not_lock():
    context = ctx(src=InputCell("src", "є", CellStatus.Answered))
    [result] = await Echo().run(context, {})
    assert result.status is CellStatus.Answered


async def test_empty_list_answered_is_a_real_answer_and_does_not_lock():
    # §5 — "we looked, there are none" is distinct from NotFound.
    context = ctx(src=InputCell("src", [], CellStatus.Answered))
    [result] = await Echo().run(context, {})
    assert result.status is CellStatus.Answered


async def test_schema_violation_becomes_needs_review_not_a_silent_value():
    context = ctx(src=InputCell("src", "x", CellStatus.Answered))
    [result] = await Echo(value={"not": "a string"}).run(context, {})
    assert result.status is CellStatus.NeedsReview
    assert result.value is None
    assert "output failed schema" in (result.message or "")


async def test_a_crashing_recipe_yields_error_per_cell_not_a_500():
    class Boom(Echo):
        id: ClassVar[str] = "boom"
        name: ClassVar[str] = "Boom"

        async def exec(self, row_context, params):
            raise RuntimeError("provider exploded")

    context = ctx(src=InputCell("src", "x", CellStatus.Answered))
    [result] = await Boom().run(context, {})
    assert result.status is CellStatus.Error
    assert "provider exploded" in (result.message or "")


def test_duplicate_output_slots_are_a_declaration_error():
    with pytest.raises(RecipeError):

        class Colliding(CellRecipe):
            id: ClassVar[str] = "dup"
            name: ClassVar[str] = "Dup"
            exec_type: ClassVar[RecipeExecType] = RecipeExecType.func
            outputs: ClassVar[Sequence[OutputSlot]] = (
                OutputSlot("same", "text"),
                OutputSlot("same", "number"),
            )

            async def exec(self, row_context, params):
                return []


class Bounded(Echo):
    id: ClassVar[str] = "bounded"
    name: ClassVar[str] = "Bounded"
    params_schema: ClassVar[Mapping[str, Any]] = {
        "type": "object",
        "properties": {"n": {"type": "integer", "minimum": 0}},
        "required": ["n"],
        "additionalProperties": False,
    }


def test_validate_params_accepts_a_conforming_payload():
    Bounded.validate_params({"n": 3})  # no raise


def test_validate_params_rejects_a_missing_required_field():
    with pytest.raises(RecipeError):
        Bounded.validate_params({})


def test_validate_params_rejects_the_wrong_type():
    with pytest.raises(RecipeError):
        Bounded.validate_params({"n": "three"})


async def test_run_rejects_bad_params_before_exec_is_called():
    # dispatched (input present) but params fail the schema — exec() must not run.
    called = False

    class Spy(Bounded):
        id: ClassVar[str] = "spy"
        name: ClassVar[str] = "Spy"

        async def exec(self, row_context, params):
            nonlocal called
            called = True
            return await super().exec(row_context, params)

    context = ctx(src=InputCell("src", "x", CellStatus.Answered))
    with pytest.raises(RecipeError):
        await Spy().run(context, {"n": -1})
    assert called is False


def test_item_type_on_a_non_list_output_is_rejected():
    with pytest.raises(RecipeError):

        class BadList(CellRecipe):
            id: ClassVar[str] = "badlist"
            name: ClassVar[str] = "BadList"
            exec_type: ClassVar[RecipeExecType] = RecipeExecType.func
            outputs: ClassVar[Sequence[OutputSlot]] = (
                OutputSlot("x", "text", item_type="identifier"),
            )

            async def exec(self, row_context, params):
                return []
