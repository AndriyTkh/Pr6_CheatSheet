"""§4 step 6 — the memo key, and what a hit is allowed to skip.

    cache_key = hash(recipe_version + resolved_input_hashes + params
                     + model_id + output_slot)

Every term earns its place:

* **`recipe_version`** — a shipped version is immutable (§3), so a new version is
  a genuinely different computation and must not read the old one's memo.
* **`resolved_input_hashes`** — the row's *data*. Two rows carrying identical
  inputs are the same question asked twice; that is the whole saving (600
  participant rows collapse to ~180 paid calls, §2a).
* **`params`** — the rubric the journalist actually chose (§3 presets are
  editable, so they are data, not a constant).
* **`model_id`** — a pinned concrete id (§10). The same prompt on a different
  model is a different answer.
* **`output_slot`** — the term that keeps a 1→M recipe's M columns from
  colliding on one key. Dropping it makes every slot of a multi-output recipe
  read the first slot's value. Do not drop it.

**Two spec gaps are resolved here explicitly rather than silently** (§4 names the
terms, not their encoding):

1. *An input-less column has no `resolved_input_hashes`.* A connector/seed column
   would then produce one key for every row on the sheet, and row 2 would
   cache-hit row 1's value. So when a column has **no DAG input edges** the row's
   `provenance_jsonb` stands in as its resolved input — it is what identifies
   that row's data. With ≥1 edge the edges *are* the row's data and provenance is
   deliberately left out, because including it would defeat the cross-row hit
   that the saving depends on.
2. *Nothing in the schema or the recipe contract records which model a recipe
   pins.* `resolve_model_id()` reads `column.params_jsonb['model_id']` first, then
   a `model_id` class attribute on the recipe, else `None` (deterministic `func`
   recipes have no model). If a `recipe.model_id` column is ever added, this is
   the one place to change.

A `NULL` `cell.cache_key` means **not hittable** — the safe default. Fallback-model
runs keep it NULL by §10; that path does not exist yet.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any, Mapping, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Cell, Column, ColumnInput, Row
from app.models.enums import TERMINAL

#: Bumped only if the canonical payload *shape* below changes — that would make
#: every existing key un-hittable, which is safe (a miss re-runs) but not free.
CACHE_KEY_SCHEMA = 1


def canonical(value: Any) -> str:
    """Stable JSON: key order and separators fixed, so equal data hashes equal."""
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
    )


def _digest(payload: Any) -> str:
    return hashlib.sha256(canonical(payload).encode("utf-8")).hexdigest()


def input_hash(input_column_id: uuid.UUID, status: Any, value: Any) -> str:
    """One resolved input: which column it came from, its status, its value.

    The status is part of the hash because `NotFound` and `Answered: null` are
    different answers (§5) and must not share a memo.
    """
    return _digest(
        {
            "column": str(input_column_id),
            "status": getattr(status, "value", status),
            "value": value,
        }
    )


def provenance_hash(provenance: Mapping[str, Any] | None) -> str:
    """The stand-in resolved input for a column with no DAG edges (gap 1 above)."""
    return _digest({"provenance": dict(provenance or {})})


def compute_cache_key(
    *,
    recipe_version: int,
    input_hashes: Sequence[str],
    params: Mapping[str, Any] | None,
    model_id: str | None,
    output_slot: str,
) -> str:
    """The §4 step 6 hash. Input hashes are sorted — edge order is not data."""
    return _digest(
        {
            "schema": CACHE_KEY_SCHEMA,
            "recipe_version": recipe_version,
            "inputs": sorted(input_hashes),
            "params": dict(params or {}),
            "model_id": model_id,
            "output_slot": output_slot,
        }
    )


def resolve_model_id(recipe_cls: type, params: Mapping[str, Any] | None) -> str | None:
    """Which concrete model this run pins (§10) — see gap 2 in the module docstring."""
    chosen = (params or {}).get("model_id")
    if chosen:
        return str(chosen)
    declared = getattr(recipe_cls, "model_id", None)
    return str(declared) if declared else None


async def resolve_input_hashes(
    session: AsyncSession, row: Row, column: Column
) -> list[str]:
    """Hash each input cell this column's edges point at, for this row.

    Keyed on the input **column id**, not its name: a journalist renaming a column
    must not silently change every downstream cache key (the rename hazard the
    `role-2/wk2-queue` handoff flagged for `row_context`).
    """
    input_column_ids = (
        (
            await session.execute(
                select(ColumnInput.input_column_id).where(
                    ColumnInput.column_id == column.id
                )
            )
        )
        .scalars()
        .all()
    )
    if not input_column_ids:
        return [provenance_hash(row.provenance_jsonb)]

    hashes: list[str] = []
    for input_column_id in sorted(input_column_ids, key=str):
        cell = await session.get(Cell, (row.id, input_column_id))
        hashes.append(
            input_hash(
                input_column_id,
                None if cell is None else cell.status,
                None if cell is None else cell.value_jsonb,
            )
        )
    return hashes


async def find_cache_hit(session: AsyncSession, cache_key: str) -> Cell | None:
    """The newest terminal cell already memoized under this key, if any.

    Newest wins (`version` is the monotonic write counter, §4 step 7): after a
    force-refresh rewrites a key, later lookups must not resurrect the value the
    bust was meant to replace. Only terminal cells are hittable — a `running` or
    `blocked` cell holds no answer.
    """
    stmt = (
        select(Cell)
        .where(Cell.cache_key == cache_key, Cell.status.in_(tuple(TERMINAL)))
        .order_by(Cell.version.desc())
        .limit(1)
    )
    return (await session.execute(stmt)).scalars().first()
