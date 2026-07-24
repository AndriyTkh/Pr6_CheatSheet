"""The recipe contract — ARCHITECTURE.md §3.

Every recipe in the catalog (§6), whatever its shape, implements this one
interface. Two rules are structural rather than documented here:

* **A recipe never reaches outside `row_context`.** The framework assembles the
  context and hands it in, so isolation cannot be broken by a coding slip.
* **`output` is a JSON Schema and it is enforced server-side.** A model that
  returns malformed JSON produces `Error`/`NeedsReview` carrying the validation
  message — never a silent malformed `value_jsonb` (§3 last bullet, Principle 4).
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar, Iterable, Mapping, Sequence

from jsonschema import Draft202012Validator
from jsonschema import ValidationError as JsonSchemaValidationError

from app.models.enums import (
    STRUCTURALLY_VOID,
    TERMINAL_EMPTY,
    CellStatus,
    InputConsumption,
    RecipeExecType,
    RecipeShape,
)

# =====================================================================
# Declarations — what a recipe says about itself
# =====================================================================


@dataclass(frozen=True, slots=True)
class InputSpec:
    """One declared input column ref (§3).

    `required` drives the dead-end lock (§6): a recipe whose *any* required input
    is terminal-empty is guaranteed `InsufficientData`, so it is never dispatched
    and never spends. Optional inputs missing → the recipe still runs, degraded.

    `consumes` is what the §2a expansion gate reads at edge-add. `per_item`
    pointed at a list column is rejected while the user is still composing the
    column — the recipe is saying "I need one row per value", and the engine's
    answer is "then Expand it first."
    """

    name: str
    required: bool = True
    consumes: InputConsumption = InputConsumption.whole_list
    description: str = ""


@dataclass(frozen=True, slots=True)
class OutputSlot:
    """One produced column (§3 — the engine is N→M from day 1).

    `slot` is the `output_slot` term of the cache key (§4 step6) — it is what
    keeps a 1→M recipe's M columns from colliding on one key.
    """

    slot: str
    value_type: str
    #: set only when value_type == 'list' and the list is typed (§2a)
    item_type: str | None = None
    description: str = ""


@dataclass(frozen=True, slots=True)
class Preset:
    """A named, *editable* param default bundled per case type (§3).

    A preset is never a hardcode: it is shown to the journalist before the run
    and recorded in `column.params_jsonb`, so the run log shows the rubric that
    was actually used.
    """

    name: str
    label: str
    params: Mapping[str, Any]


# =====================================================================
# Execution values
# =====================================================================


@dataclass(slots=True)
class Citation:
    """How one value anchors to a source (§9).

    The quote is verbatim and the offset is found by string-searching it back
    into the source — a model-reported page number is never trusted.
    """

    source_type: str  # 'document' | 'api' | 'web'
    quote: str | None = None
    document_id: uuid.UUID | None = None
    page: int | None = None
    char_start: int | None = None
    char_end: int | None = None
    url: str | None = None
    api_path: str | None = None
    match_confidence: float | None = None

    def to_jsonb(self) -> dict[str, Any]:
        return {
            "source_type": self.source_type,
            "quote": self.quote,
            "document_id": str(self.document_id) if self.document_id else None,
            "page": self.page,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "url": self.url,
            "api_path": self.api_path,
            "match_confidence": self.match_confidence,
        }


@dataclass(slots=True)
class CellResult:
    """One produced cell: value + typed status + citations (§3 `exec()`).

    `citations` is aligned index-for-index to a list value (§9). An empty list
    value with status `Answered` is a real answer ("we looked, there are none"),
    not an empty cell (§5).
    """

    slot: str
    value: Any
    status: CellStatus
    citations: list[Citation] = field(default_factory=list)
    #: surfaced to the journalist when the status needs explaining
    message: str | None = None

    def citation_jsonb(self) -> list[dict[str, Any]]:
        return [c.to_jsonb() for c in self.citations]


@dataclass(slots=True)
class InputCell:
    """One input cell as handed to a recipe — value plus its typed status."""

    column_name: str
    value: Any
    status: CellStatus
    citations: list[dict[str, Any]] = field(default_factory=list)

    @property
    def is_terminal_empty(self) -> bool:
        return self.status in TERMINAL_EMPTY

    @property
    def is_structurally_void(self) -> bool:
        return self.status in STRUCTURALLY_VOID


@dataclass(slots=True)
class RowContext:
    """Everything a recipe is allowed to see — assembled by the framework.

    A recipe reads this and nothing else. There is no session, no repository,
    and no row lookup on the object, which is what makes isolation structural
    rather than a convention (§3).
    """

    row_id: uuid.UUID
    sheet_id: uuid.UUID
    depth: int
    provenance: Mapping[str, Any]
    inputs: Mapping[str, InputCell]
    #: only documents that passed the §11 `external_ok` gate reach here
    documents: Sequence[Mapping[str, Any]] = ()

    def get(self, name: str) -> InputCell | None:
        return self.inputs.get(name)

    def value(self, name: str, default: Any = None) -> Any:
        cell = self.inputs.get(name)
        return default if cell is None else cell.value


class RecipeError(Exception):
    """Raised for a recipe-declaration bug — never for a bad *cell* result."""


class OutputValidationError(RecipeError):
    """Model returned JSON that does not satisfy the recipe's output schema."""


# =====================================================================
# The contract
# =====================================================================


class Recipe(ABC):
    """Base class for every recipe (§3).

    Subclasses declare the metadata as class attributes and implement `exec()`.
    `run()` — not `exec()` — is what the engine calls: it applies the dead-end
    lock and validates every produced value against `output_schema` before the
    result is allowed anywhere near a cell.
    """

    # --- identity ---
    id: ClassVar[str]
    name: ClassVar[str]
    version: ClassVar[int] = 1

    # --- shape / execution ---
    exec_type: ClassVar[RecipeExecType]
    shape: ClassVar[RecipeShape] = RecipeShape.cell
    #: §4 step6 — agent/web/LLM results are not re-queried on identical inputs
    volatile: ClassVar[bool] = False

    # --- interface ---
    inputs: ClassVar[Sequence[InputSpec]] = ()
    outputs: ClassVar[Sequence[OutputSlot]] = ()
    params_schema: ClassVar[Mapping[str, Any]] = {"type": "object"}
    output_schema: ClassVar[Mapping[str, Any]] = {"type": "object"}
    presets: ClassVar[Sequence[Preset]] = ()
    cite_spec: ClassVar[Mapping[str, Any]] = {}
    eval_spec: ClassVar[Mapping[str, Any]] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        # only the shape base classes declare __abstract__ on themselves;
        # inherited truth must not exempt a concrete recipe
        if cls.__dict__.get("__abstract__", False):
            return
        for attr in ("id", "name", "exec_type"):
            if not hasattr(cls, attr):
                raise RecipeError(f"{cls.__name__} must declare `{attr}` (§3)")
        slots = [o.slot for o in cls.outputs]
        if len(slots) != len(set(slots)):
            raise RecipeError(
                f"{cls.__name__}: duplicate output_slot — slots are the cache-key "
                f"term that keeps a 1→M recipe's columns from colliding (§4 step6)"
            )
        for out in cls.outputs:
            if out.item_type is not None and out.value_type != "list":
                raise RecipeError(
                    f"{cls.__name__}: output '{out.slot}' sets item_type on a "
                    f"non-list value_type (§2a)"
                )

    # ---------------------------------------------------------------
    # Implemented by each recipe
    # ---------------------------------------------------------------

    @abstractmethod
    async def exec(
        self, row_context: RowContext, params: Mapping[str, Any]
    ) -> Sequence[CellResult]:
        """(row_context, params) → [{value, status, citation}] — one per output slot.

        Never raise for a data problem: return the typed status that describes
        it (§5 — uncertainty is data, not an empty cell). Raising is for a real
        crash, which the engine turns into `Error` with the traceback logged.
        """

    # ---------------------------------------------------------------
    # Engine-side — do not override
    # ---------------------------------------------------------------

    @classmethod
    def required_inputs(cls) -> list[InputSpec]:
        return [i for i in cls.inputs if i.required]

    @classmethod
    def input_spec(cls, name: str) -> InputSpec | None:
        return next((i for i in cls.inputs if i.name == name), None)

    @classmethod
    def dead_end_status(cls, row_context: RowContext) -> CellStatus | None:
        """§6 dead-end lock. Returns the locked status, or None to dispatch.

        Fires on **any** required input. `NotApplicable` propagates as itself so
        the reason survives the hop; terminal-empty inputs lock to
        `InsufficientData` (§5). Optional inputs missing never lock.
        """
        for spec in cls.required_inputs():
            cell = row_context.get(spec.name)
            if cell is None:
                return CellStatus.InsufficientData
            if cell.is_structurally_void:
                return CellStatus.NotApplicable
            if cell.is_terminal_empty:
                return CellStatus.InsufficientData
        return None

    @classmethod
    def validate_params(cls, params: Mapping[str, Any]) -> None:
        """Validate params against `params_schema` before a run is dispatched."""
        try:
            Draft202012Validator(dict(cls.params_schema)).validate(dict(params))
        except JsonSchemaValidationError as exc:
            raise RecipeError(f"{cls.name}: invalid params — {exc.message}") from exc

    @classmethod
    def validate_output(cls, payload: Mapping[str, Any]) -> None:
        """§3 — enforce `output_schema` server-side at the model edge.

        Callers turn the raised error into `Error`/`NeedsReview` on the cell,
        carrying the validation message. A malformed model response must never
        reach `value_jsonb`.
        """
        try:
            Draft202012Validator(dict(cls.output_schema)).validate(dict(payload))
        except JsonSchemaValidationError as exc:
            raise OutputValidationError(
                f"{cls.name} v{cls.version}: output failed schema at "
                f"{'/'.join(str(p) for p in exc.absolute_path) or '<root>'} — {exc.message}"
            ) from exc

    async def run(
        self, row_context: RowContext, params: Mapping[str, Any]
    ) -> list[CellResult]:
        """What the engine calls: lock check → exec → schema enforcement.

        A recipe that crashes yields `Error` on every declared slot rather than
        taking the worker down — a partial failure must stay visible per cell
        (§4 step7).
        """
        locked = self.dead_end_status(row_context)
        if locked is not None:
            return [
                CellResult(
                    slot=out.slot,
                    value=None,
                    status=locked,
                    message="required input is terminal-empty — not dispatched (§6)",
                )
                for out in self.outputs
            ]

        self.validate_params(params)

        try:
            results = list(await self.exec(row_context, params))
        except Exception as exc:  # noqa: BLE001 — a crash is a cell status, not a 500
            return self._error_results(f"{type(exc).__name__}: {exc}")

        try:
            self._check_slots(results)
            self.validate_output(self._as_payload(results))
        except OutputValidationError as exc:
            return self._error_results(str(exc), status=CellStatus.NeedsReview)
        except RecipeError as exc:
            return self._error_results(str(exc))

        return results

    # ---------------------------------------------------------------

    def _check_slots(self, results: Iterable[CellResult]) -> None:
        produced = {r.slot for r in results}
        declared = {o.slot for o in self.outputs}
        if produced != declared:
            raise RecipeError(
                f"{self.name}: exec() returned slots {sorted(produced)}, "
                f"declared {sorted(declared)}"
            )

    def _as_payload(self, results: Iterable[CellResult]) -> dict[str, Any]:
        """The shape `output_schema` describes: one property per output slot."""
        return {r.slot: r.value for r in results}

    def _error_results(
        self, message: str, status: CellStatus = CellStatus.Error
    ) -> list[CellResult]:
        return [
            CellResult(slot=out.slot, value=None, status=status, message=message)
            for out in self.outputs
        ]


class CellRecipe(Recipe):
    """N columns → M columns over existing rows (§6). Shape default."""

    __abstract__ = True
    shape: ClassVar[RecipeShape] = RecipeShape.cell


@dataclass(slots=True)
class ProducedRow:
    """One row a row-producing recipe emits (§6, §2a).

    `parent_row_id` is the 1:1 tree edge; `links` is the N-ary lineage graph.
    An expanded child writes both (§16 #2).
    """

    provenance: Mapping[str, Any]
    values: Mapping[str, CellResult] = field(default_factory=dict)
    parent_row_id: uuid.UUID | None = None
    depth: int = 0
    ordinal: int | None = None
    links: Sequence[Mapping[str, Any]] = ()


class RowProducingRecipe(Recipe):
    """Emits new rows — onto this sheet or a derived one (§6, §2a).

    Row production never happens as a side effect of a cell run: it is its own
    recipe shape, gated by Preview like any other (§4 step 4).
    """

    __abstract__ = True
    shape: ClassVar[RecipeShape] = RecipeShape.row

    @abstractmethod
    async def produce(
        self, case_id: uuid.UUID, sheet_id: uuid.UUID, params: Mapping[str, Any]
    ) -> Sequence[ProducedRow]:
        """Emit the rows for this sheet. Called instead of `exec()`."""

    async def exec(
        self, row_context: RowContext, params: Mapping[str, Any]
    ) -> Sequence[CellResult]:  # pragma: no cover - not the entry point
        raise RecipeError(
            f"{self.name} is row-producing — call produce(), not exec() (§6)"
        )


class CrossRowRecipe(Recipe):
    """→ `cross_row_result`, no row shape at all (§8, §16 #6).

    Scope is narrowed by rev. 3: anything with a stable pair grain belongs on
    the Pairs sheet instead. This shape is for genuinely one-off signals.
    """

    __abstract__ = True
    shape: ClassVar[RecipeShape] = RecipeShape.cross_row

    @abstractmethod
    async def analyze(
        self,
        row_contexts: Sequence[RowContext],
        params: Mapping[str, Any],
    ) -> Sequence[Mapping[str, Any]]:
        """Explicit, user-declared input row set in → typed signals out (§8)."""

    async def exec(
        self, row_context: RowContext, params: Mapping[str, Any]
    ) -> Sequence[CellResult]:  # pragma: no cover - not the entry point
        raise RecipeError(f"{self.name} is cross-row — call analyze(), not exec() (§8)")
