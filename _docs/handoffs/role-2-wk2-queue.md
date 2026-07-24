# role-2/wk2-queue — Procrastinate as the real job queue

Task: `_docs/tasks/role-2.md` week 2, "Wire Procrastinate as the real job queue" (§4, §15).
Status at handoff: `REVIEW`. Verify green, full suite green, nothing skipped.

## What landed

| File | Owns |
|---|---|
| `backend/app/tasks/app.py` | The Procrastinate `App`, a lazily-built `PsycopgConnector`, `queue_dsn()`, `build_app()`, `use_selector_event_loop()`. |
| `backend/app/tasks/cells.py` | The `cheatsheet.execute_cell` task (queue `cells`) + `enqueue_cell()`. |
| `backend/app/services/cell_execution.py` | What running a cell *means*: claim → assemble `row_context` → `recipe.run()` → write `value/status/citation/run_id`. |
| `backend/app/recipes/registry.py` | `catalog()` + `recipe_class()` — `column.recipe_id/version` → the Python class. |
| `backend/scripts/apply_queue_schema.py` | Procrastinate's own tables. Deliberately not a numbered migration. |
| `backend/app/tests/test_queue.py` | The Verify. |

## The seam the wavefront task needs

`enqueue_cell(row_id: UUID, column_id: UUID, *, cache_bust: bool = False) -> int`.

That is the whole contract. §4 splits it cleanly and this branch stayed on its
side of the split:

* **When** a cell's job is created is §4 step 5 — the wavefront task. Nothing on
  this branch calls `enqueue_cell()` automatically; it is offered, not wired.
* **Which worker** runs it is Procrastinate — this branch.

So the wavefront's job is: find the cells whose inputs are all terminal, **at the
column's `target_depth`** (§2a), and `await enqueue_cell(...)` for each, inside an
open app (`async with procrastinate_app.open_async():` in a script/test; the
FastAPI process opens it once at startup). It never touches `procrastinate_jobs`
and never reads `cell.status` to decide anything.

Two things the wavefront inherits and should not re-solve:

* `cell.cache_key` is left **NULL** by `_write()` on purpose — §4 step 6 is the
  next task, and NULL means "not hittable", the safe default until a key exists.
* `_claim()` creates the cell if it does not exist, because the Preview path
  (§4 step 4) runs cells the wavefront never inserted. A wavefront that inserts
  `blocked` cells first is compatible with this, not in conflict with it.

## Spec friction — flag, do not silently diverge

**`column_input` records the DAG edge but not which declared `InputSpec` it
satisfies.** A recipe declares `inputs = (InputSpec("src"), InputSpec("hint"))`;
the schema records only "column X feeds column Y", with `is_required` and
`consumes` on the edge. There is no column saying *X is the `src` input*.

`_assemble_row_context()` currently bridges that by keying `row_context.inputs`
on the **input column's name**, plus an `output_slot` alias when it does not
shadow a real column name. That works for the pilot because a journalist tends
to leave the column named after the slot — but it breaks the moment they rename
a column, and the dead-end lock (§6) reads `row_context.get(spec.name)`, so a
rename would silently turn a required input into "missing" → `InsufficientData`.

This wants a `column_input.input_slot` (or equivalent) in a **new numbered
migration** plus team agreement (CLAUDE.md §5) — not an in-place schema edit and
not a quiet convention in the service layer. Noted in the module docstring too.
Whoever takes §4 step 5 or the recipe-catalog work should raise it.

## Dead ends / environment notes

* **Branch collision, and how it was resolved.** The main checkout
  `C:\ProjectsC\KSE\Pr6_CheatSheet` was on `role-2/wk2-api-routes` with another
  session actively committing to it. Per CLAUDE.md §4 ("don't switch branches
  under them"), this work was done in a **separate git worktree** at
  `C:\ProjectsC\KSE\Pr6_CheatSheet-wk2-queue` on `role-2/wk2-queue`, based on
  `dd0d965`. That worktree has no `.venv`; it reuses the main checkout's
  (`/c/ProjectsC/KSE/Pr6_CheatSheet/backend/.venv`). This is the pattern
  CLAUDE.md §4a's "one agent per checkout" points at — it works, use it again.
  * Residue: the main checkout still carries uncommitted duplicate copies of
    these files from before the worktree existed. Harmless (that branch does not
    `git add -A`), but someone should `git checkout -- backend/pyproject.toml
    backend/app/recipes/registry.py _docs/tasks/role-2.md` and delete the
    untracked `backend/app/tasks/`, `backend/app/services/cell_execution.py`,
    `backend/scripts/apply_queue_schema.py` there once `role-2/wk2-queue` merges.
  * The `.claude/hooks/verify-backend.sh` hook resolves paths against
    `$CLAUDE_PROJECT_DIR` = the **main** checkout, so every edit in the worktree
    fails it with `E902 The system cannot find the file specified`. The hook is
    not wrong about the code; it is blind to worktrees. `ruff check app` and
    `pytest` were run by hand in the worktree instead. If worktrees become
    normal here, the hook should resolve against `git rev-parse --show-toplevel`.

* **`psycopg[binary]` is installed but not declared.** Procrastinate's
  `PsycopgConnector` requires psycopg 3; `pyproject.toml` declares
  `procrastinate` and `sse-starlette` but *not* `psycopg[binary]`, which was
  pip-installed by hand in a previous session. Deliberately left undeclared
  rather than silently added — Procrastinate documents the extra as
  `procrastinate[psycopg_binary]` vs. a source build, and which one this project
  wants is a team call, not a coding-agent call. **A fresh checkout will not run
  the queue until this is resolved.** Raise it.

* **Windows: the selector event loop is not optional.** psycopg's async stack
  never completes on `ProactorEventLoop` (the Windows default) — the pool just
  times out after ~30s, which reads as "Postgres is unreachable" rather than
  "wrong loop". `use_selector_event_loop()` must be called before any
  `asyncio.run()` that touches the queue: the schema script does it, the queue
  test does it. A worker entrypoint (not written yet) must too.

* **`CS_DATABASE_URL`, not just `CS_TEST_DATABASE_URL`.** `Settings` uses
  `env_prefix="CS_"`, and both `app.db.session.async_session_factory` and
  `app.tasks.app.procrastinate_app` are module-level singletons reading
  `settings.database_url` at **import** time. Running `test_queue.py` needs both
  vars pointed at the same database.

* **The queue tests use their own committing fixtures, not `conftest.session`.**
  That fixture rolls back; a worker on its own connection cannot see uncommitted
  rows, so the test would hang or fail on a missing row. `test_queue.py` seeds
  with an explicit `commit()` and cleans up in a `finally:` — deleting the `Case`
  (cascades sheet/row/column/cell) plus the `Run` and `Recipe` rows, which do not
  cascade from it.

* **The DB-backed test ran against an isolated database `cheatsheet_queue`** (both
  numbered migrations + the Procrastinate schema), not the main `cheatsheet` one,
  so queue tables never mix into the dev database.

* **The lock check is an AST scan, not a grep.** A grep for `FOR UPDATE` trips on
  the prose in `cell_execution.py` that *promises* there is no `FOR UPDATE`. The
  test parses each module, drops docstrings, and then looks for
  `with_for_update` names and `FOR UPDATE` / `SKIP LOCKED` inside non-docstring
  string literals — so real raw SQL is still caught. Two parametrized
  "guards the guard" cases keep it from passing vacuously.
