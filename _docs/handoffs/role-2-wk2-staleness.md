# Handoff — role-2/wk2-staleness

Task: **Staleness walk on column edit** (`_docs/tasks/role-2.md`, week 2). Status → `REVIEW`.

## What landed

- `backend/app/services/staleness.py` — `mark_downstream_stale(session, changed_column_id) -> StalenessResult`.
- `backend/app/tests/test_staleness.py` — 6 DB-backed tests.

The §4 recursive CTE walks **downstream** over `column_input` edges (`UNION`, not
`UNION ALL`) and returns the reachable column ids; the greying is then a separate
ORM `update(...).values(status=stale)`. Result carries `stale_column_ids` +
`new_version_available` — the "new version available" prompt §4 asks for. Nothing
is enqueued and no cell is written: only the `column.status` rollup greys; cells
keep value/citation/version (§5). The caller owns the commit.

## Verify

- `pytest app/tests/test_staleness.py -q` → **6 passed**.
- Full suite `pytest -q` with `CS_TEST_DATABASE_URL` set → **93 passed, 0 skipped, 0 failed** (wk1's 87 + 6 new).
- DB: docker `backend-db-1`, host `127.0.0.1:55432` (never `localhost`).

## Decisions / seams worth knowing

- **Why not a single `UPDATE ... RETURNING` CTE.** First cut did the raw CTE
  `UPDATE` directly. Problem: it bypasses the ORM identity map, so a caller
  holding `Column` objects (or calling `session.get`) still reads the pre-edit
  status. `expire_all()` "fixed" it but then expired the *caller's own* held
  objects → accessing `col.id` triggered a sync lazy-load → `MissingGreenlet`
  under asyncpg. Final shape: **CTE as the walk (SELECT), ORM update with
  `synchronize_session="fetch"` as the mark** — updates the greyed columns in the
  identity map without touching anything else. If you later call this from a route
  that holds no ORM state, the raw single-statement CTE would be marginally
  cheaper; the split is there for session coherence, not correctness of the DB row.
- **Cross-sheet is free, by construction.** The walk never mentions `sheet_id`, so
  §2a's "DAG spans sheets at the sheet boundary only" needs no special code — an
  edge from a source column to a derived-sheet column is just another edge.
  `test_walk_crosses_the_sheet_boundary` builds `@participants` (source) →
  `companies_expand` → `owner`/`creation_date` (derived) and asserts the derived
  columns grey *and* actually live on the derived sheet.
- **Derived sheets need a parent.** Constraint `sheet_parent_iff_derived`: a
  `kind='derived'` sheet must set `parent_sheet_id` (a source must not). The test
  helper `_derived_sheet` sets it — worth remembering for any derived-sheet fixture.
- **The changed column is not greyed** — only its dependents. The CTE base case is
  `WHERE input_column_id = :changed`, so `:changed` never enters the stale set.
  Asserted in `test_direct_and_transitive_dependents_are_marked_stale`.
- **"Nothing re-executed" is proved by cell immutability**, not a provider spy —
  this path has no provider call to spy on. An `Answered` cell with value +
  citation is byte-for-byte unchanged (incl. `version`) after the walk.

## Not in scope (left for the confirm/rerun path)

`mark_downstream_stale` only greys. The actual rerun-on-confirm is
`invalidate_cell` / `dispatch_column` (§4 step 6, wavefront branch) — a confirmed
stale-column rerun cache-busts the affected cells there. This task deliberately
stops at surfacing the prompt.

## Environment note

Built in a **git worktree** (`../Pr6_CheatSheet_wt_staleness`, branch
`role-2/wk2-staleness` off `role-2/wk1-models-recipe-dag`) because another agent
was actively switching branches in the main checkout when this task started
(reflog showed a live `chained-columns → wk2-reconcile` checkout). The repo-root
`verify-backend.sh` hook is pinned to `$CLAUDE_PROJECT_DIR` (the main checkout),
so it `E902`'d on every edit here — ruff + the suite were run manually against the
worktree instead. Nothing was routed around; the hook simply can't see a sibling
worktree. Remove the worktree after merge: `git worktree remove ../Pr6_CheatSheet_wt_staleness`.
