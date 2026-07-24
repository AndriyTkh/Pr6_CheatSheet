# Role 5 — Frontend developer/designer

> Part of `_docs/TASKS.md` (index: gates, people, tracking rules, cross-role notes). Read the index once, then work only in this file. Edit only the `Status` line of a task you own.

Mandate: the spreadsheet UX is core product, not decoration — it has to hold up at hundreds of live-filling rows across multiple sheets, not just look right in a screenshot. Folder: `frontend/src/`. Primary references: §1, §2a, §4 step 7, §15.

**Verify lines** run from `frontend/`. There is no test runner in the pilot stack — `npm run build` (which is `tsc -b && vite build`) is the machine half, and each task names the one manual check that actually proves it. Do both before `REVIEW`. If a task's manual check keeps costing more than writing a test would, say so rather than skipping it.

### Week 1 (2026-07-22 – 2026-07-28)

- **Task: Grid skeleton**
  - **Status:** `TODO`
  - **Target date:** `2026-07-22`
  - Description: `components/grid/` — TanStack Table + virtual scroll, rows/columns rendering, basic sort/filter, source-context view stub. Can run against mocked/static data before Role 2's API is ready.
  - Inputs: none to start (mock data); real API later this week.
  - Deliverable: a grid that renders rows and columns.
  - **Verify:** `npm run build` clean + 500 mock rows scroll without dropping frames or unmounting the header.
  - Depends on: nothing blocking to start; switch to real API once Role 2's routes exist.
  - Reference: §1, §15.

- **Task: Rowspan-under-virtualization spike (§1 week-1 risk)**
  - **Status:** `TODO`
  - **Target date:** `2026-07-23`
  - Description: ARCHITECTURE.md §1 flags this explicitly as a week-1 spike, not a week-3 nice-to-have: confirm whether TanStack's virtual scroll can render a parent cell spanning its `inline`-expanded child band (§2a) when the span crosses the virtual window boundary. If it can't, the fallback is repeating the parent value per child row visually (storage is unaffected either way — parent cells are stored once regardless, §2a). Decide now so the recipe-builder/Expand UI (week 3) isn't designed against an assumption that doesn't hold.
  - Inputs: grid skeleton.
  - Deliverable: written spike result (rowspan works / fallback needed) feeding the week-3 Expand UI task.
  - **Verify:** the spike doc states a decision, not a maybe, and names the case tested — a parent band scrolled across the virtual window boundary in both directions.
  - Depends on: grid skeleton.
  - Reference: §1 "Week-1 spike", §2a.

- **Task: Generate TS API types from OpenAPI**
  - **Status:** `TODO`
  - **Target date:** `2026-07-24`
  - Description: Set up `openapi-typescript` (or equivalent) against Role 2's FastAPI-generated OpenAPI spec so frontend types don't hand-drift from backend schemas.
  - Inputs: Role 2's OpenAPI spec.
  - Deliverable: `types/` generated/kept in sync.
  - **Verify:** regenerate from the live spec, then `npm run build` clean — a regenerated diff that breaks the build is the signal working, not a failure.
  - Depends on: Role 2's API routes existing.
  - Reference: tech-stack-decision.md "Shared FE/BE types."

- **Task: Wire to real backend for the week 1 gate**
  - **Status:** `TODO`
  - **Target date:** `2026-07-26`
  - Description: Once Role 2 has one recipe running through Preview→run→column→Result, point the grid at the real API so the week 1 gate is a real demo, not a mock.
  - Inputs: Role 2's API routes + first working recipe.
  - Deliverable: one real lot row's recipe result visible in the grid.
  - **Verify:** `npm run build` clean + one real lot row rendered from the live API with zero mock modules imported in the built bundle.
  - Depends on: Role 2.
  - Reference: §14 week 1 gate.

### Week 2 (2026-07-29 – 2026-08-04) — merges the original plan's weeks 2+3

- **Task: SSE hook + streaming cell fill**
  - **Status:** `TODO`
  - **Target date:** `2026-07-29`
  - Description: `hooks/` — subscribe to Role 2's SSE endpoint, update grid cells as they stream in, without re-rendering the whole grid per message (backend batches flushes, but the frontend must still apply them efficiently).
  - Inputs: Role 2's SSE endpoint.
  - Deliverable: cells visibly fill in live during a background run.
  - **Verify:** `npm run build` clean + React Profiler on a live run shows only touched cells re-rendering, not the grid.
  - Depends on: Role 2's SSE task.
  - Reference: §4 step 7.

- **Task: Reconcile-on-reconnect**
  - **Status:** `TODO`
  - **Target date:** `2026-07-30`
  - Description: On reconnect, call Role 2's `?since=<version>` endpoint before resuming the live stream, so a dropped connection doesn't lose cell updates.
  - Inputs: Role 2's reconcile endpoint.
  - Deliverable: verified no data loss across a simulated disconnect.
  - **Verify:** kill the network mid-run in devtools, restore it, and confirm the grid matches a fresh page load cell-for-cell.
  - Depends on: Role 2's reconcile task.
  - Reference: §4 step 7.

- **Task: Source/citation view (first pass)**
  - **Status:** `TODO`
  - **Target date:** `2026-07-31`
  - Description: `components/citations/` — clicking a cell opens its citation(s): source locator, quote, link back to the document/API field. Needs to handle the list-in-cell case (one citation per array item, not one per cell) eventually — first pass can handle single citations.
  - Inputs: Track A's citation data shape (Role 3/4) — coordinate on the `citation_jsonb` array format.
  - Deliverable: basic source view working.
  - **Verify:** `npm run build` clean + on a real cited cell, the quote shown matches the source at the given locator (open the source and check).
  - Depends on: Role 3/4's citation anchoring landing enough to have real data to show.
  - Reference: §9.

- **Task: Recipe builder UI + Preview gate**
  - **Status:** `TODO`
  - **Target date:** `2026-08-02`
  - Description: `components/recipes/` — pick input column(s), pick a recipe, set params, run Preview on a stratified sample (§4 step 4 — not first-N), see preview results, confirm to run full background job. Surface the §2a list-gate rejection clearly when it fires (name the column, offer the two Expand modes) rather than a generic error. This is what Oksana uses for the week 2 gate (building a 2-column sequence herself), so usability here matters more than polish.
  - Inputs: Role 2's recipe/preview API.
  - Deliverable: a non-technical user can add a recipe and confirm a run without help.
  - **Verify:** trigger the §2a list gate deliberately and confirm the message names the column and both Expand modes; confirm no full run fires without an explicit confirm click.
  - Depends on: Role 2's API + at least 2 working recipes (Role 3/4).
  - Reference: §4 step 4, §2a.

- **Task: Typed status display (all eight) + feedback controls**
  - **Status:** `TODO`
  - **Target date:** `2026-08-04`
  - Description: Show all **eight** terminal statuses distinctly (not just "done"/"error") — rev. 3 adds `NotApplicable` alongside the original seven, and it must read visually distinct from `InsufficientData` (§5: "nothing to check" vs. "couldn't find"). Wire the correct/partial/incorrect/cannot-judge + relevance + error-type feedback form to Role 2's `cell_feedback` endpoint.
  - Inputs: Role 2's feedback endpoint; Role 1's rubric.
  - Deliverable: Oksana can leave feedback from the grid.
  - **Verify:** render all eight statuses side by side on one screen and confirm each is distinguishable (`NotApplicable` vs. `InsufficientData` especially); submit one feedback form and confirm it persisted server-side.
  - Depends on: Role 2's feedback API.
  - Reference: §5, §12.

### Week 3 (2026-08-05 – 2026-08-11)

- **Task: Sheet switcher UI**
  - **Status:** `TODO`
  - **Target date:** `2026-08-05`
  - Description: A case is now a set of sheets (§2a), not one grid — add tab/switcher navigation between the source `@tenders` sheet and derived sheets (Companies, Pairs) as they come online, each with its own columns/sort/filter state.
  - Inputs: Role 2's sheets API.
  - Deliverable: user can switch sheets within a case without losing per-sheet grid state.
  - **Verify:** sort + filter sheet A, switch to B and back, confirm A's state survived.
  - Depends on: Role 2's sheets-aware API routes.
  - Reference: §2a.

- **Task: List-cell rendering + Expand UI**
  - **Status:** `TODO`
  - **Target date:** `2026-08-06`
  - Description: Render `value_type='list'` cells distinctly (count/preview of items, not a joined string), and surface the **Expand** action on a list column — the user picks `inline` or `new_table` (+ `dedup_by` for the latter), triggering Role 2's Expand recipe. Uses the week-1 rowspan spike result to decide how `inline` mode renders the parent-spans-children band.
  - Inputs: rowspan spike (week 1); Role 2's Expand recipe API.
  - Deliverable: a journalist can expand `@participants` into the Companies sheet from the grid, no manual API calls.
  - **Verify:** expand a real `@participants` cell in both modes from the UI alone; confirm `inline` renders per the spike's decision when the band crosses the virtual window.
  - Depends on: rowspan spike, Role 2's Expand backend.
  - Reference: §2a.

- **Task: Cross-row signal + Pairs sheet display**
  - **Status:** `TODO`
  - **Target date:** `2026-08-07`
  - Description: Pairs now render as an ordinary sheet (via the sheet switcher) — sortable/scoreable/citable like any other. Separately, surface any remaining `cross_row_result` signals (narrowed scope, §8) in their own small panel with evidence and links to both source rows, since those genuinely have no row/sheet home.
  - Inputs: Role 3/4's Pair builder + Cross-row connect output; sheet switcher.
  - Deliverable: Pairs sheet browsable like any sheet; leftover cross-row signals visible and explorable.
  - **Verify:** Pairs sheet sorts/filters/cites like any other sheet; a cross-row signal's links open both source rows.
  - Depends on: sheet switcher, Role 3/4.
  - Reference: §2a, §8.

- **Task: Result save + Google Sheets export UI**
  - **Status:** `TODO`
  - **Target date:** `2026-08-09`
  - Description: UI for saving the current grid slice as a Result (selected rows/columns/filters/version, per sheet) and triggering Role 2's multi-sheet Sheets export.
  - Inputs: Role 2's export endpoint.
  - Deliverable: working save + export on full volume, across sheets.
  - **Verify:** export the full dataset and confirm the produced Google Sheet's rows/columns match the on-screen filtered slice, per sheet.
  - Depends on: Role 2.
  - Reference: [owner-brief §4 P0, §11], §2a.

### Week 4 (2026-08-12 – 2026-08-18) — merges the original plan's weeks 5+6, ends on Demo Day

- **Task: Stale-column UI**
  - **Status:** `TODO`
  - **Target date:** `2026-08-12`
  - Description: Grey out `stale` columns (via `column.status` rollup), show "new version available," require explicit user confirm before rerun — never auto-rerun. Confirm this reads correctly across a sheet boundary (an upstream edit on `@participants` marks the Companies sheet stale, §2a).
  - Inputs: Role 2's staleness walk (week 2).
  - Deliverable: correct stale/confirm UX, including cross-sheet staleness.
  - **Verify:** edit an upstream column, confirm dependents grey out on both sheets and that nothing re-runs until the confirm is clicked (watch the network tab).
  - Depends on: Role 2.
  - Reference: §5, §4 "Staleness," §2a.

- **Task: Polish pass for solo Oksana run (week 4 gate)**
  - **Status:** `TODO`
  - **Target date:** `2026-08-15`
  - Description: Fix whatever UX friction blocks Oksana from running the full core loop *without developer help* — this is the literal week 4 gate (originally week 5's), now mid-week so there's runway left before Demo Day itself.
  - Inputs: feedback from Role 1's coordinated sessions.
  - Deliverable: gate met.
  - **Verify:** Oksana completes the core loop end to end with zero developer interventions — count them; one intervention means not met.
  - Depends on: all prior frontend tasks + Role 1's session scheduling.
  - Reference: §14 week 4 gate.

- **Task: Demo Day support**
  - **Status:** `TODO`
  - **Target date:** `2026-08-18`
  - Description: Be present/on-call for the live demo run, fix anything that breaks live, support the final Result save/export. If Demo Day slips into the buffer (§14a), this task slips with it.
  - Inputs: stable build.
  - Deliverable: clean live demo.
  - **Verify:** `npm run build` clean on the tagged commit; the demo runbook's happy path walked once before the live run.
  - Depends on: everything else.
  - Reference: §14 week 4 gate.
