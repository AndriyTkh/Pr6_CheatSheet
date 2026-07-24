# role-2/wk2-wavefront — wavefront-gated enqueue + `cache_key`

Task: `_docs/tasks/role-2.md` week 2, "Wavefront-gated enqueue + `cache_key`
(depth-aware)" (§4 steps 5–6, §2a).
Status at handoff: `REVIEW`. Verify green; full suite **132 passed, 0 skipped, 0
failed** against the dev `cheatsheet` database.

## What landed

| File | Owns |
|---|---|
| `backend/app/services/wavefront.py` | §4 step 5 — `dispatch_column()`, `on_cell_terminal()`, `inputs_ready()`, `invalidate_cell()`, `publish_cell_terminal()`. |
| `backend/app/services/cache_key.py` | §4 step 6 — the key, `resolve_input_hashes()`, `resolve_model_id()`, `find_cache_hit()`. |
| `backend/app/services/cell_execution.py` | Rewired: cache check → claim → run → write, plus the wake-up after every terminal write. |
| `backend/app/tests/test_wavefront.py` | Readiness, grain, the wake-up. |
| `backend/app/tests/test_cache_key.py` | Key purity, the one-paid-call hit, cache-bust, `invalidate_cell`. |

## The seam for the SSE task (§4 step 7)

`publish_cell_terminal(session, row_id, column_id)` emits `pg_notify` on channel
**`cheatsheet_cell`** with payload `{"row_id": ..., "column_id": ...}`. The
payload is deliberately tiny — a listener re-reads the cell rather than trusting
a NOTIFY body (8000-byte limit, and the body would be stale by design). It is
fire-and-forget: a failed notify is logged and never costs a completed cell, so
the SSE layer must treat a missed message as normal and reconcile by version.

**Every terminal write already bumps `cell.version`** (`cell_version_seq`), on
the real-run path, the cache-hit path, the `_fail` path and the wavefront's own
`blocked → pending` promotion. So `GET /case/:id/cells?since=<version>` has a
complete, monotonic stream to page on and the notify is only a wake-up, never
the transport.

## The seam for the chained-columns task

Three functions, all in `wavefront.py`:

* `dispatch_column(session, column, *, cache_bust=False, enqueue=None)` — creates
  this column's cells across its sheet (`pending` + deferred, or `blocked`) and
  returns a `WavefrontPlan`. Commits the cells **before** deferring any job.
* `on_cell_terminal(session, row_id, column_id, *, enqueue=None)` — the wake-up.
  Scoped to the same row and to columns declaring an edge from the one that
  finished. Never re-enqueues a cell that is not `blocked`; that is how a paid
  cell gets run twice.
* `inputs_ready(statuses)` — pure. All inputs terminal, and a missing cell is not
  terminal. Terminal-*empty* counts as ready on purpose: the dead-end lock (§6,
  week 3) is what makes it cheap, and the lock needs the cell dispatched to fire.

`enqueue=` is the injection point the tests use (an `EnqueueSpy`); production
falls through to `app.tasks.cells.enqueue_cell`, imported late so the
`tasks → services` dependency stays one-way.

**Distinct cache keys per link come for free.** A chain's second column has a
different `recipe_version`, different input hashes (its inputs are the first
column's cells) and a different `output_slot`, so links never collide — no
per-link namespacing is needed, and nothing in a chain should add any.

## Spec ambiguities — flagged, not buried

**(a) §4 names the cache-key terms but not their encoding.** An input-less column
(connector/seed) has no `resolved_input_hashes` at all, so every row on the sheet
would share one key and row 2 would cache-hit row 1's value. Resolved by
substituting the row's `provenance_jsonb` as the resolved input **only** when the
column has no DAG edges; with ≥1 edge the edges *are* the row's data and
provenance is deliberately excluded, because including it would defeat the
cross-row hit the §2a saving depends on. Both halves are asserted in
`test_cache_key.py`.

**(b) Nothing in the schema or the recipe contract records which model a recipe
pins**, yet `model_id` is a required cache-key term (§10 wants a pinned concrete
id). `resolve_model_id()` reads `column.params_jsonb['model_id']` first, then a
`model_id` class attribute on the recipe, else `None` (a deterministic `func`
recipe has no model). A real `recipe.model_id` column would want a **new numbered
migration + team agreement** (CLAUDE.md §5) — not an in-place schema edit. If it
ever lands, `resolve_model_id()` is the one place to change.

**(c) §4 says `LISTEN/NOTIFY` fires the re-check**, but a DB trigger would need a
migration and the schema is locked. Since the only writer of a terminal cell
status is the worker running that cell, the re-check is called **in-process at
the end of that job** — the same event, no round trip, no second poller — and
`pg_notify` is emitted alongside for out-of-process listeners. If a second writer
of terminal statuses ever appears (a backfill script, a manual override route),
it must call `on_cell_terminal()` too or its dependents will sit `blocked`.

## Resolved on this branch (were open on `role-2/wk2-queue`)

* **`psycopg[binary]` is now declared** — `pyproject.toml` carries
  `procrastinate[psycopg_binary]` (psycopg 3 is the connector's driver;
  SQLAlchemy stays on asyncpg). Team-agreed. Run `pip install -e .[dev]` to repair
  an env that predates it — editing the file does not touch installed packages.
  Deployment note left in the file: psycopg upstream wants `psycopg[c]` or system
  libpq rather than the binary wheel for production.
* **The dev `cheatsheet` database now carries the Procrastinate schema**
  (`python scripts/apply_queue_schema.py --database-url …/cheatsheet`), so the
  full suite is green against the same database `backend/CLAUDE.md` walks you
  into — one `CS_TEST_DATABASE_URL`, no second queue database. The isolated
  `cheatsheet_queue` database was dropped. Enqueue is transactional with the cell
  write (§4), so the queue schema belongs *in* the app database, not beside it.

## Inherited, still unresolved

* **`column_input` records the DAG edge but not which declared `InputSpec` it
  satisfies**, so `_assemble_row_context()` keys `row_context.inputs` on the input
  column's *name* (plus an `output_slot` alias). A journalist renaming a column
  silently turns a required input into "missing" → `InsufficientData` via the
  dead-end lock. Note that `cache_key` does **not** share this hazard:
  `resolve_input_hashes()` keys on the input **column id**, so a rename never
  invalidates a memo. Wants a `column_input.input_slot` in a new numbered
  migration. Still open.

## Dead ends / environment notes

* **Two pre-existing test defects were fixed here, both in files this branch
  touched.**
  * `test_wavefront.py` seeded `depth=1` rows with `ordinal=NULL`, violating
    0002's `row_depth_implies_parent` check (`depth > 0 AND ordinal IS NOT
    NULL`). Note the constraint permits `parent_row_id IS NULL` at depth > 0 —
    it is the *ordinal* that is mandatory. The helper now sets it.
  * `test_queue.py` asserted `cell.cache_key IS NULL` with the comment "§4 step 6
    belongs to the next task". Step 6 is this task, so a successful run is now
    memoized; the assertion is inverted. NULL is still what an engine-side
    `_fail()` writes, and what §10's fallback path will write.
* **A column cannot point at a recipe that is not in the `recipe` table** —
  `column.recipe_id/recipe_version` FKs at it. A DB test seeding a column with a
  recipe must `await ensure_registered(db, TheRecipe)` before the flush, and its
  teardown must delete the `run` rows **before** the `recipe` row and **after**
  the `case` (cells FK at `run`; neither `run` nor `recipe` cascades from `case`).
* **The DB tests own committed data.** `dispatch_column()`/`execute_cell()`
  commit, so the shared rolled-back `conftest.session` fixture cannot be used —
  both new test files carry their own committing `db` fixture that deletes what
  it created in teardown.
* **`CS_DATABASE_URL` as well as `CS_TEST_DATABASE_URL`**, pointed at the same
  database: `async_session_factory` and `procrastinate_app` are module-level
  singletons read at import time. Host is `127.0.0.1`, never `localhost`
  (backend/CLAUDE.md).
* **A fresh Postgres needs the queue schema before the full suite is green** —
  `test_queue.py`'s end-to-end case fails on `type
  "procrastinate_job_to_defer_v1[]" does not exist` without it. One command, on
  the *same* database `CS_TEST_DATABASE_URL` points at:
  `python scripts/apply_queue_schema.py --database-url <that url>` (it is already
  step in `backend/CLAUDE.md`). Done for the current dev `cheatsheet`.
* **The untracked `_docs/API.md` in this checkout belongs to
  `role-2/wk2-api-routes`** and was deliberately left uncommitted.
