# Handoff — role-2/wk2-chained-columns

Task: **Column-dependency support for derived-column inputs** (§4 + §6).
Deliverable is `backend/app/tests/test_chained_columns.py` — the proof that a
recipe consuming an already-derived column resolves link by link, N deep.

## What already worked (no engine change needed)

The task turned out to be *verification*, not construction. Two pieces already
in the tree carry a chain end to end:

- **Wavefront chaining via `on_cell_terminal`.** `dispatch_column` gates a cell
  on its input cells' statuses (`_input_statuses` → `inputs_ready`), and a
  terminal write wakes only the dependents whose inputs are now ready
  (`_wake_dependents` in `cell_execution.py`). So a 3-deep chain runs strictly
  L1 → L2 → L3 no matter what order the columns were dispatched — the order
  lives in the `column_input` edges, not in enqueue order. The test dispatches
  in reverse and drains a real worker loop over the enqueue seam to prove it.

- **Per-input-column `cache_key`.** `resolve_input_hashes` already hashes each
  input cell's value, so two links that share recipe/version/params/model_id
  **and `output_slot`** still get distinct keys — `resolved_input_hashes` is the
  only term that differs. The test isolates exactly that term (holds every other
  constant) and asserts three distinct, non-NULL keys plus `ChainStep` running
  exactly three times (a collision would have cache-hit a neighbour).

## What I fixed

Nothing in the engine. The test as inherited passes clean: `3 passed, 0
skipped` on the Verify line, `149 passed` full suite (DB URL set). No teardown,
alias, or drain fix was required — the likely-failure spots the resume note
flagged (output_slot alias in `dead_end_status`, worker-loop drain, teardown
order) all already hold.

## Full-suite note

The resume note expected `test_sse.py::test_stream_route_is_registered` to
FAIL as the in-progress SSE task. It does **not** — the SSE work has since been
committed onto this branch (commits `fa1f320`, `acfa4b6`, `cf611bd`) and its 14
tests all pass. So the whole suite is green; there is no known-failing test to
carry. The SSE code lives in tracked commits, not the working tree — untouched.

## Seam to watch — recipe-input name binding (`column_input` has no `input_slot`)

`_assemble_row_context` (`cell_execution.py:299`) keys a recipe's inputs by the
**input column's name**, because `column_input` records the edge but not which
declared `InputSpec` it satisfies. It also aliases each input under the upstream
column's `output_slot` *when that slot doesn't already shadow a real column
name* (`slot not in inputs`). Already noted in the wavefront handoff; the
chained test leans on it and exposes its limits:

- `ChainStep` declares its input by the `output_slot` alias (`InputSpec(SLOT)`),
  not by column name — which is the **only** thing that lets one declaration
  resolve the required input at every depth, since the input column is a
  different name (`L1`, `L2`, …) at each link. A required-input recipe in a real
  chain must do the same: **declare inputs by `output_slot` alias, not by the
  journalist-facing column name**, or a rename anywhere upstream silently starts
  reading `None` (→ `InsufficientData`, → dead-end lock).
- The alias binds only the *first* upstream column with a given slot
  (`slot not in inputs`). Two upstream inputs sharing an `output_slot` collide on
  the alias — fine for a single-input chain, a latent bug for a multi-input
  recipe whose inputs happen to share a slot. The real fix is a per-edge
  `input_slot` column on `column_input` (a new numbered migration + team
  agreement, `0001` is locked); until then the mapping is name/slot-heuristic,
  not declared.

## State on stop

- `test_chained_columns.py` committed (`d11447d`), that file only.
- `role-2.md` chained-task Status set to `REVIEW` — **uncommitted** (shared
  dirty file; SSE's status line already committed, don't co-commit mine).
- `_docs/API.md` untracked, not mine — left alone.
- No push, no PR.
