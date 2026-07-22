# CheatSheet — Technical Architecture Plan

**Status:** working draft (rev. 3 — workflow-integration pass) · derived from `_docs/archive/rough-outline.md` + product/owner briefs + `recipe-catalog-annotated.md` (rev. 2 + Maryna's 21.07 review) + `_docs/desired-workflow.md`
**Scope:** summer pilot vertical slice (Prozorro + YouControl, procurement case — entity/role/period set in case config)

**rev. 3 changes (all previously-open catalog decisions now closed here):** row grain → **tender lot** (§16 #3) · `NotApplicable` added as 8th cell status (§5, §16 #9) · **typed list cells + the expansion gate**, with two expand modes, inline and new-table (§2a, §16 #2) · dead-end lock now fires on **any required** input (§3, §6) · five recipes added: Structured Extract promoted + fully specced, Formula/Compute, Start router, Expand, Pair builder (§6) · UI **Ukrainian only** for pilot, Translation recipe dropped from P0 (§6).
**This is the technical contract.** Every `§N` reference in `TASKS.md` and the other docs points here. Who-does-what-when lives in `_docs/TASKS.md`; read-order and git rules in `CLAUDE.md`.

---

## 0. Core idea in one line

CheatSheet is a **columnar, lineage-tracked compute graph over rows**, where each column is the memoized output of a versioned operation ("recipe"), and every cell carries provenance and a typed status. Spreadsheet on the surface; a build-system/DAG engine underneath.

Get this engine **generic** (row / column / recipe / run / result know nothing about tenders). Prozorro and YouControl are just connectors. This is the single most important constraint — it protects against the "tender pipeline instead of a product" failure.

---

## 1. Components

| # | Component | Choice | Notes |
|---|-----------|--------|-------|
| 1 | Database | **Postgres** (+ `pgvector`, `jsonb`) | One source of truth. DAG, cells, chunks, provenance, eval — all here. No second DB. |
| 2 | Recipe format | N input cols → M output cols; `func` or `agent`; versioned | Generality **is** the product. |
| 3 | Task runner | **Procrastinate** (Postgres `LISTEN/NOTIFY` + `SKIP LOCKED`), wavefront-gated per cell → Redis/Celery only if scale hits | One queue. `cell.status` is data, not the lock target. See §4. |
| 4 | UI | **TanStack Table + virtual scroll**, streaming cell updates (SSE + reconcile-on-reconnect) | Headless grid, own the render, handles 100s of rows filling live. Headless matters for §2a `inline` expand: the parent-cell vertical span across a child band is our render decision, not the library's. **Week-1 spike:** confirm rowspan works with virtualization — a spanning cell crossing the virtual window is the risk; fallback is repeating the parent value per child row (same stored data, §2a). |
| 5 | One-pass recipes | Structured Extract, Formula/Compute, Connector(API), WebSearch, Summarize, Classify/Score, Match&Verify, Aggregate/Fold, Compare/Diff · Start(router), Unnest/Explode, Pair builder, Generate/Seed rows · Custom Prompt | The recipe catalog (§6): cell-producing, row-producing, cross-row. |
| 6 | Provenance / citations | quote→locate anchoring, source-language, per emitted item | Product soul. Principle 2. See §9. |
| 7 | Versioning + staleness | `recipe_version`, `cache_key`, DAG staleness walk | Principle 5. |
| 8 | Eval hooks | per-recipe metrics + cell-level human feedback | Oksana = ground truth. Wire from week 1. |
| 9 | Document processing | 3 distinct modes (retrieve / enumerate / extract) | See §7. |
| 10 | Agentic | bounded (WebSearch, Match&Verify, explicit cross-row) | Unbounded Assistant Plan/Auto = Deferred. See §8. |

---

## 2. Data model (Postgres)

**Locked Day 1-2. Committed migration: `migrations/0001_core_schema.sql`** — that file is the frozen contract; this section is its map. Change only by team agreement + a new numbered migration.

| Table | Grain | Key columns | Notes |
|---|---|---|---|
| `case` | one investigation | `owner_id`, `is_private` (default true) | §11 private by default |
| `case_member` | (case, user) | `role` ∈ owner/editor/viewer | §11 (reviewer = Stretch) |
| `recipe` | (id, **version**) | `exec_type` func/agent, `shape` cell/row/cross_row, `volatile`, `params_schema` (may carry **presets**, §3), `output_schema` (JSON Schema), `cite_spec`, `eval_spec` | §3. Old results stay pinned to the exact version; never mutate a shipped one. |
| `sheet` | one grid/tab in a case | `case_id`, `kind` source/derived, `grain_label` (`lot` / `company` / `pair` / `document`), `produced_by_run_id`, `parent_sheet_id` | §2a. A case has ≥1 sheet; every row belongs to exactly one. An `inline` expand adds rows to an existing sheet; a `new_table` expand creates one. |
| `row` | one **tender lot** on the source sheet (§16 #3); one company / one pair on derived sheets | `sheet_id`, `origin` connector/upload/generated/derived, `provenance_jsonb` (keyed by `tenderID`+`lotID`), `parent_row_id`, `depth`, `ordinal`, `position`, `generated_by_run_id`, `state`†, `merged_into_row_id`† | §2a. `depth` 0 = source, 1 = expanded child; `ordinal` = index in the source list, carrying that item's citation. †dormant — P0 always `active` (§5) |
| `row_link` | (child row, parent row) | `child_row_id`, `parent_row_id`, `relation` (`expanded_from` / `pair_member`), `source_cell_*` | §2a **N-ary lineage** — a deduplicated company links to every lot it bid on; a pair row links to both members. `row.parent_row_id` is the 1:1 **tree** edge (drives grain, order, rendering); `row_link` is the **graph** (drives evidence + traceability). Every child writes both. |
| `column` | one derived (or source) column | `sheet_id`, `recipe_id`+`recipe_version`, `output_slot`, `params_jsonb`, `value_type` + `item_type` (§2a lists), `target_depth`, `output_lang`, `status` (rollup) | source/seed columns have NULL recipe; `target_depth` picks which grain the column runs on in an `inline`-expanded sheet |
| `column_input` | DAG edge | `(column_id, input_column_id)`, `is_required`, `consumes` (`whole_list`/`per_item`) | acyclicity **and the §2a list gate** both enforced in app at edge-add (§4 step2); CTE walks staleness/lineage |
| `cell` | (row, column) | `value_jsonb` (**may be a typed list**, §2a), `status` (`cell_status` enum), `citation_jsonb` (array aligned by index, §9), `cache_key`, `run_id`, `version` (monotonic, for SSE `?since=`), `terminal_scope`† | the memoized result; `cache_key` app-computed (§4 step6) |
| `run` | one execution | `model_id` (pinned), `provider_endpoint`, `prompt_hash`, `used_fallback`, `cache_bust`, `cost_usd` | §10 provenance log |
| `document` | one source file/API doc | `row_id`, `external_ok` (hard gate §11), `source_lang`, `ocr_status`, `storage_key` (R2) | §7/§9/§11 |
| `chunk` | one text chunk | `embedding vector(1024)`, `embed_model_id` (pinned), `page`, `char_start/end` | §10 same-model-only retrieval; ANN index added wk2 |
| `cross_row_result` | one pairwise signal | `row_ids[]`, `column_ids[]`, `signal`, `evidence_jsonb`, `input_versions_jsonb`, `is_stale` | §8/§16 #6 — outside the DAG, preserves row isolation |
| `cell_feedback` | one human verdict | `verdict`, `relevance` 0-3, `error_type`, `correct_value`, `judge_id` | §12 eval |

**Enums (locked):** `cell_status` (§5 — one enum spanning `blocked/pending/running` + the **eight** terminals + dormant `Rejected`), `column_status` (`pending/running/partial/done/stale`), `recipe_exec_type`, `recipe_shape`, `row_origin`, `sheet_kind`, `row_link_relation`, `row_state`†, `terminal_scope`†, `case_role`.

**Migration note (rev. 3).** `0001_core_schema.sql` is frozen and predates lot grain, sheets, and `NotApplicable`. The delta ships as **`migrations/0002_sheets_and_lot_grain.sql`** — a new numbered migration, never an in-place edit of 0001 (`CLAUDE.md` §5). It:

| Change | Serves |
|---|---|
| `cell_status` += `NotApplicable`; `row_origin` += `derived` | §5, §16 #9 · §2a |
| new `sheet` (+ `sheet_kind`) and `row_link` (+ `row_link_relation`, `source_ordinal`) tables | §2a, §16 #10 |
| `row.sheet_id` / `column.sheet_id`, backfilled to one implicit source sheet per case, then `NOT NULL` | §2a |
| `row.parent_row_id` / `depth` / `ordinal` / `position`, and `column.target_depth` | §2a inline expand — grain, order, rendering |
| `column.item_type` (only when `value_type='list'`) | §2a typed lists |
| `column_input.consumes` (`whole_list` default) | §2a expansion gate |
| `row.tender_id` / `row.lot_id` generated from `provenance_jsonb`, + unique `(sheet_id, tender_id, lot_id)` | §16 #3 lot grain, connector dedup |
| `column_input.is_required` (default `true`) | §3, §6 — the dead-end lock's `any(required)` rule |

`cross_row_result` is untouched: its scope narrows (§8) but that is a usage rule, not a schema change. Merge/`row_state`/`terminal_scope`/`Rejected` stay dormant.

**Four invariants stay in the app, not the DB** — all need cross-table state, and 0001 already put the DAG acyclicity check app-side for the same reason: (1) the **list gate** itself — `consumes='per_item'` against a list column, rejected at edge-add (§4 step 2), because it must fail while the user is *composing*, before any row exists for a constraint to fire on; (2) a cell's row and column must agree on `sheet_id`; (3) a cell exists only where `row.depth = column.target_depth`; (4) `inline` children share their parent's sheet, `new_table` children do not. Owner: backend/DB role, week 1, before any recipe assumes a sheet.

---

## 2a. Lists, the expansion gate, and sheets

A recipe returning several values per row does **not** create rows. It writes **one cell holding a typed list**. Rows are created only by an explicit user action. The rule that connects the two is a **block**:

> **A list cell can feed any recipe that consumes the list as a whole. Any action that needs one row per list value is BLOCKED until the user expands that list.**

This is the core of §16 #2 and it exists so the row set never changes as a side effect of a column running. The block is not a failure — it is the prompt that offers the two expand modes below.

### The list cell

- `cell.value_jsonb` holds a JSON array; `citation_jsonb` is an array **aligned by index** to it (§9), so item *i* has its own locator. A list cell is not a joined string — items keep their identity and their provenance.
- The **column** declares the shape: `value_type = 'list'` plus an optional `item_type` (`number | date | money | text | entity`). A list may be **typed** (`list<entity>` — sortable by length, foldable, safe to expand into entity rows) or **untyped** (`list` — heterogeneous or unknown items, still citable, but Formula/Compute and typed expansion refuse it). Typing the items is what makes downstream work legal; leaving it untyped is allowed and simply buys fewer operations.
- **Empty list ≠ missing.** `[]` with status `Answered` means "we looked, there are none" (an uncontested lot has no other bidders). That is different from `NotFound` (couldn't determine) and from `NotApplicable` (the question doesn't apply here, §5). Expanding an empty list produces zero child rows and is not an error.

### The gate — where the block fires

Every recipe input declares how it consumes its column (§3): **`whole_list`** or **`per_item`**. The check runs at **edge-add time — when the user adds the recipe/column, alongside the §4 step 2 cycle check** — not at execution:

- input is `per_item` **and** the referenced column is a list → **the action is rejected before any cell exists**, with the message naming the column and offering the two expand modes.
- input is `whole_list` → allowed; the recipe receives the array in `row_context`.

Because it fires at edge-add, **the block is a validation error on the add-column action, not a `cell_status`.** Do not add a `Blocked` terminal to the §5 enum for it — no cell is created, nothing is enqueued, nothing is spent, and the journalist finds out while composing the column rather than after a run. (`cell.status='blocked'` in §4 is unrelated: that is the ordinary wavefront wait state.)

A column's declared `value_type` is fixed at creation and enforced by `output_schema` at the model edge (§3), so a scalar column cannot silently become a list and invalidate an edge that was legal when added.

### Expand — two modes, one recipe

**Expand** (§6) is a row-producing recipe with a `mode` param. Both modes set each child's `parent_row_id` to the row the list came from, and each child's `ordinal` to its **index in the source array** — which is what carries the item's citation across to the child row.

**Mode 1 — `inline`: children land in the same sheet, between the original rows.**
Row *n* with a 3-item list becomes a band of 3 child rows sitting directly under it; a 2-item list next to it yields 2. Fan-out is ragged by nature and that is fine.

- **Rendering duplicates; storage does not.** The parent's other cells are *displayed* across the band — as a vertical span if the grid supports rowspan, otherwise repeated values — but they are **stored once, on the parent row**. This deliberately avoids Power Query's fan-out trap where expanding triples every parent value and every later `SUM` silently triples with it. An aggregate over `@amount` still sees 200 lot values, not 600 copies.
- The sheet now holds **two grains**. This is handled by depth, not by row typing: source rows are `depth = 0`, their children `depth = 1`. A column declares its `target_depth`, and the wavefront (§4 step 5) only creates cells for rows at that depth. Cells simply do not exist off-grain, so "run YouControl on the participants" cannot accidentally fire on lot rows.
- **`inline` cannot deduplicate.** It is positional: one child per list slot, per parent. A company bidding on three lots gets three child rows. That is the honest cost of keeping children next to their parent, and on external-API columns it is paid per duplicate.

**Mode 2 — `new_table`: children become the rows of a new sheet.**
Cleaner: uniform grain, no duplicate rendering, its own column DAG.

- **This is the mode that can deduplicate,** via an optional `dedup_by` param naming the identity key (e.g. the `(scheme, id)` pair). Deduplicating is what turns 600 participant entries into ~180 company rows — and 600 paid YouControl calls into 180.
- Dedup is exactly why child rows need more than one parent: a deduplicated company belongs to every lot it bid on. `parent_row_id` cannot hold three values, so **multi-parent lineage lives in `row_link`** (§2). Un-deduplicated children keep the simple 1:1 `parent_row_id` and get one `row_link` row too, so downstream code has a single path to walk.

**Choosing:** `inline` keeps the evidence beside its source and reads well for small, per-row inspection. `new_table` is right when the child grain is a subject in its own right — you want to sort, score, and enrich companies as companies — and it is the only mode that avoids paying for duplicates. The pilot workflow (`desired-workflow.md` §7) uses `new_table` with dedup.

### Sheets

A case is therefore a set of sheets, not one grid. Each has its own row grain and column DAG:

| Sheet | Grain | Produced by | Typical columns |
|---|---|---|---|
| `@tenders` (source) | one **tender lot** | Connector: Prozorro / Start router | `@winner`, `@amount`, `@participants` (list), `@requirements`, `@review_priority` |
| `@documents` (source) | one uploaded source document | Manual upload | extract columns |
| Companies (derived) | one canonical company | **Expand** `new_table` + dedup over `@participants` | `@owner`, `@creation_date`, `@media_mentions`, … |
| Pairs (derived) | one unordered company pair | **Pair builder** | `@shared_lots`, `@wins_A`, `@wins_B`, `@shared_owner_or_address`, `@evidence` |

Rules that keep this from becoming a second engine:

- **Derived sheets re-enter the core unchanged.** Same `row`/`column`/`cell`/`recipe` tables, same wavefront (§4), same citations (§9), same export. "Run YouControl on the Companies sheet" is the ordinary cell-producing recipe — there is no company-specific or pair-specific code path.
- **Row isolation holds in both modes.** A recipe still sees exactly one row's `row_context`, child or parent. Aggregation back up to the parent is an ordinary Aggregate/Fold grouped by `parent_row_id` — not a special case.
- **The DAG spans sheets at the sheet boundary only.** The producing Expand/Pair-builder recipe is one node whose inputs are parent-sheet columns; downstream columns depend on the new sheet's own columns. Staleness walks through: rerun `@participants` → the derived sheet is marked `stale`, never silently rebuilt (§4, "never auto-rerun").
- **`cross_row_result` survives, narrowed** — only for signals with **no row shape** (§8). Anything with a stable pair grain belongs on a Pairs sheet where the journalist can sort it.

---

## 3. Recipe format

A recipe is a **pure-ish function signature** wrapped in versioning metadata:

```
Recipe {
  id, name, version
  exec_type:     func | agent
  input:         list of column refs (N ≥ 1), each flagged
                   required | optional      (dead-end lock, §6)
                   whole_list | per_item    (list gate, §2a)
  params:        typed schema (rubric, target entity, language, model_id, …)
                 + optional per-case-type presets (editable defaults, not hardcodes)
  output:        typed schema (M ≥ 1 columns) + per-cell status enum
  exec():        (row_context, params) → [{value, status, citation}]
  cite:          how each value anchors to a source
  eval:          which metrics apply
}
```

Rules:
- **Inputs are `required` or `optional`, declared in the recipe.** This is not documentation — it drives the dead-end lock (§6): a recipe whose *any* required input is terminal-empty is guaranteed `InsufficientData`, so it is never dispatched and never spends. Optional inputs missing → the recipe still runs, degraded. (Example: Classify/Score reads `@amount` required, `@media_mentions` optional.)
- **Each input also declares `whole_list` or `per_item`.** This is what the §2a expansion gate reads. `per_item` pointed at a list column is rejected at edge-add — the recipe is telling the engine it needs one row per value, and the engine's answer is "then expand it first." Recipes that fold, compare, count, or merely read a list as context declare `whole_list` and are unaffected. See the per-recipe table in §6.
- **Params may ship presets.** A preset is a named param default bundled per case type (e.g. the Score rubric "procurement v0" of `_docs/desired-workflow.md` §3) — **visible and editable by the journalist before the run**, and recorded in `column.params_jsonb` so the run log shows the rubric actually used. A preset is never a hardcode: no recipe reads a rubric the user cannot see and change.
- **Engine is N→M from day 1** (data model). First shipped *recipe* may be 1→1 (scope ramp). Don't confuse the two — one is permanent, one is temporary.
- A recipe never reaches outside `row_context`. The framework **assembles** the context and hands it in, so isolation is structural, not a coding convention.
- `func` = deterministic (API extract, counts, pattern match). `agent` = tool-using LLM loop. Same signature, same eval, same logging.
- Not everything is an LLM. Exact counts / frequencies / matches → code (owner brief §9).
- **`output` is a JSON Schema, and it is enforced at the model edge.** LLM recipes constrain generation with provider structured-output / function-calling to that schema, then the framework **validates the returned JSON against it server-side**. Validation failure → cell status `Error` (or `NeedsReview`) carrying the validation message — never a silent malformed `value_jsonb`. This is where Principle 4 ("uncertainty is data, not an empty cell") is enforced, not just declared.

---

## 4. Execution + DAG

**Flow when user adds a recipe:**
1. New column node + edges (`column_input`).
2. **Validate the new edges — reject before anything exists.** Two checks, same place, same failure mode (an error on the add-column action, no cells, no spend):
   - **Cycle check** (DFS/Kahn) — reject if the new edge closes a loop. Keeps the graph acyclic.
   - **List gate (§2a)** — reject if a `per_item` input points at a list column, with a message naming the column and offering the two Expand modes. This is deliberately *not* a runtime status: catching it at composition time is what keeps the row set from ever changing as a side effect of a run.
3. Topo-sort the affected subgraph.
4. **Preview** on a few rows (gate before spend). Sample **stratified**, not first-N — a few connector-flagged hard/edge rows + a few random — so an easy sample doesn't give false confidence. Preview rows run for real; on confirm they **cache-hit** (same `cache_key`) instead of re-spending.
5. On confirm → **wavefront-gated enqueue** (topo order of *enqueue* ≠ topo order of *execution* under parallel workers, so ordering must be enforced by data, not queue insertion order):
   - For each row **at the column's `target_depth`** (§2a — off-grain rows get no cell at all, so an `inline`-expanded sheet's two grains never cross): if all input cells are already terminal → enqueue the cell job now; else insert the cell as `status='blocked'`.
   - When any cell reaches a terminal status, `LISTEN/NOTIFY` fires → re-check `blocked` cells in the *same row* whose column depends on the just-finished column → enqueue those now ready. A cell never runs before its inputs are ready.
   - Skip rows where `row.state != 'active'` (dormant in P0 — all rows are `active` until deferred Merge/gating ships).
6. Each cell: compute `cache_key = hash(recipe_version + resolved_input_hashes + params + model_id + output_slot)`. The **`output_slot`** term is what keeps a 1→M recipe's M columns from colliding on one key. Cache hit → skip. Miss → run → write `value + status + citation + run_id`.
   - **Force-refresh (cache-bust):** `volatile` recipes (agent/web/LLM, §2) never re-query on identical inputs otherwise. A user (or a stale-column confirm) can invalidate a single cell → `status='pending'` + a `cache_bust` flag on the job → that one cell bypasses cache, writes a **new** `run` (old run retained in the log → Principle 5 history). No `recipe_version` bump needed to re-run one row.
7. Fill streams into the grid in the background; partial failures are visible.
   - At pilot ceiling (~10-15k cells/case), don't push one SSE message per completed cell — batch/coalesce flushes (e.g. every 150-250ms or N cells) so the grid isn't re-rendering thousands of times in a burst.
   - **Reconnect has no replay by itself.** Each streamed update carries a monotonic version. On reconnect the client issues one `GET /case/:id/cells?since=<version>` reconcile-fetch, then resumes the live stream — so cells that filled during a multi-minute disconnect are not silently lost.

**Staleness (upstream edited):** walk edges *downstream*, mark reachable columns `stale`. **Do not auto-rerun** — surface "new version available", user confirms.

```sql
-- staleness: walk down
WITH RECURSIVE stale AS (
  SELECT column_id FROM column_input WHERE input_column_id = :changed
  UNION
  SELECT ci.column_id FROM column_input ci JOIN stale s ON ci.input_column_id = s.column_id
)
UPDATE column SET status='stale' WHERE id IN (SELECT column_id FROM stale);

-- lineage: walk up (flip the join)
WITH RECURSIVE origin AS (
  SELECT input_column_id FROM column_input WHERE column_id = :target
  UNION
  SELECT ci.input_column_id FROM column_input ci JOIN origin o ON ci.column_id = o.input_column_id
)
SELECT * FROM column WHERE id IN (SELECT input_column_id FROM origin);
```

Use `UNION` (not `UNION ALL`) so diamonds/accidental cycles terminate.

**One queue — Procrastinate, not a hand-rolled poller.** Procrastinate *is* the Postgres `LISTEN/NOTIFY` + `SKIP LOCKED` queue (tech-stack §15); do not also poll `cell.status` for locking — that would be two queues fighting. `cell.status` is **data/display** (`blocked → pending → running → <terminal enum>`), never the lock target. Procrastinate owns the job: on pick it flips the cell to `running`; on finish it writes `value + status + citation + run_id`. Wavefront readiness (step 5) decides *when* a cell's job is created; Procrastinate decides *which worker* runs it. Enough for pilot scale (10-15k cells/case); promote to Redis/Celery only on an order-of-magnitude load jump.

---

## 5. Typed cell status

Never a nullable string. Enum (Principle 4 — uncertainty is data). **P0 active set = the owner brief's seven, plus `NotApplicable` (rev. 3, §16 #9):**

`Answered · InsufficientData · NotFound · SourceUnavailable · ConflictingEvidence · Error · NeedsReview · NotApplicable`

Status describes the result of *one operation*. "Not found" ≠ "the fact doesn't exist in the world."

**`NotApplicable` = "there is nothing to check here."** The question is structurally void for this row, not unanswered: a direct-award lot has no competitors, so a pair recipe on it has no pair to build; a single-bidder lot has no co-bid. It must stay distinguishable from `InsufficientData` ("the question applies, the data is missing") — collapsing them would tell the journalist to go hunting for evidence that cannot exist, and would poison eval, where a `NotApplicable` row is *excluded* from the denominator while an `InsufficientData` row is a **miss counted against recall**.

Classification of the eight terminals:

| Group | Statuses | Dead-end lock (§6) |
|---|---|---|
| answered | `Answered` | no lock |
| terminal-empty | `InsufficientData` · `NotFound` · `SourceUnavailable` | locks downstream → `InsufficientData` |
| structurally void | `NotApplicable` | locks downstream → **`NotApplicable`** (propagates its own kind, so the reason survives the hop) |
| needs a human | `ConflictingEvidence` · `Error` · `NeedsReview` | no lock — a human may resolve it |

**An empty list is `Answered`, not an empty cell.** A list-valued cell holding `[]` with status `Answered` asserts a fact — "we looked, there are none" (an uncontested lot really has no other bidders). It is distinct from `NotFound` (couldn't determine), from `InsufficientData` (couldn't look), and from `NotApplicable` (the question doesn't apply). Only the last three are terminal-empty for lock purposes; `[]`+`Answered` is a real answer and propagates nothing (§2a).

`NotApplicable` therefore gets the full cost saving of the lock (no downstream dispatch, negative-cached on `cache_key`) without lying about why the cell is empty.

**Column status is a rollup, not a second source of truth.** `cell.status` is the per-operation truth (the enum above). `column.status` is *derived* from its cells + version state — `pending / running / partial / done / stale` — where `partial` = some cells terminal-error while others Answered. The grid greys a `stale` column by joining `column.status`; cells keep their old values and citations until a confirmed rerun (§4).

**Deferred (dormant schema, not P0 behavior):** `Rejected` status + `terminal_scope='row'` + `row.state`/`merged_into_row_id` exist in the schema (§2) only for the deferred Merge / row-gating features (§8). In P0 every row stays `active`, no recipe locks a row, and `Rejected` is never emitted — row lifecycle is a single-state axis until those features ship.

---

## 6. Recipe catalog (P0)

Three shapes, one contract (§3): **cell-producing** (N cols → M cols over existing rows), **row-producing** (emit new rows — onto this sheet or a **derived sheet**, §2a), **cross-row** (→ `cross_row_result`, no row shape at all). Same `exec()`/`cite`/`eval` metadata for all three.

**Shape is a property of the recipe, not the connector.** A connector can back a recipe of either shape — Prozorro is row-producing in P0 (search params → lot rows) but a `Connector: Prozorro (fields)` cell-producing variant (lot ref in row → fill fields) is equally valid on the same contract. Symmetrically, YouControl is cell-producing in P0 (company or person key in row → registry fields) but a row-producing YouControl variant that *iterates* (founders → their founders → …) is the same connector, opposite direction — that variant *is* the deferred **Recursive/Expand walk** (§13): depth-iteration, not single-pass, so it stays out of P0 (§6b). When Expand walk ships it reuses this contract, no new plumbing.

**Cell-producing** (ordered by pilot-workflow weight — Structured Extract first, it is the most-used recipe in the real workflow and the one whose interface must be stable before parallel work starts, §16 #4):

| Recipe | exec | Input → Output | Eval metric |
|--------|------|----------------|-------------|
| **Structured Extract** | func + LLM | doc/fields → typed columns (deterministic from API; LLM only for unstructured fragments). **Full spec below.** | precision/recall/F1 on critical fields |
| **Formula / Compute** | func | referenced cols → computed column (arithmetic / date diff / ratio — e.g. days between company registration and tender date) | correctness vs manual calc |
| **Connector: YouControl** | func | **two modes**, same recipe family: (a) company key → registry fields; (b) **person key → that person's companies** (fixed 2-step, *not* a recursive walk — §6b) | success rate, match accuracy on human sample |
| **Web Search** | agent | query cols + explicit time window → external-context column | precision@k, authoritative-source share, dup/broken-link rate |
| **Summarize** | LLM | text col → short column | citation-entailment rate, unsupported-claim rate, key-fact recall |
| **Classify / Score** | LLM | cols → label/score column + explanation; **editable preset rubric per case type** (§3 presets) | per-class P/R/F1; weighted agreement / MAE for ordinal; P@k / NDCG for ranking |
| **Match & Verify** | agent | company in row → typed link status | match accuracy, wrong-entity rate, explanation/source completeness |
| **Aggregate / Fold** | func | list-in-cell **or** rows grouped by key col → scalar (sum / count / avg / min / max) per group | correctness vs manual tally; group-completeness |
| **Compare / Diff** | func / LLM | 2+ cols → match / mismatch / delta + typed status (func for exact/numeric, LLM for semantic) | agreement with human; false-match rate |
| **Custom Prompt** *(Stretch)* | LLM | cols → column | per-use rubric |

**How each recipe consumes a list column** (§2a gate — this table is the normative `consumes` declaration; a `per_item` row is one the gate blocks until the user expands):

| Recipe | consumes | Behavior on a list input |
|---|---|---|
| **Aggregate / Fold** | `whole_list` | the native list consumer — `count` / `sum` / `avg` / `min` / `max` over items, or over child rows grouped by `parent_row_id` after an expand. Both directions, one recipe. |
| **Formula / Compute** | `whole_list` | `length()`, `contains()`, index access; arithmetic over items **requires a typed list** (`list<number|money|date>`) — untyped list is rejected at edge-add, same gate |
| **Compare / Diff** | `whole_list` | set operations over two lists — intersection (shared bidders between two lots), symmetric difference, added/removed |
| **Summarize** | `whole_list` | the list is context; output is one summary cell |
| **Classify / Score** | `whole_list` | the list is one signal among several (e.g. bidder count feeds `@review_priority`); output is one label/score for the row |
| **Structured Extract** | `whole_list` | may also *produce* a list — that is what `output type = list` means |
| **Connector: YouControl** | **`per_item`** | one registry lookup per company — **blocked on a list**. Expand `@participants` first. |
| **Web Search** | **`per_item`** | one row-isolated search per entity — **blocked on a list** |
| **Match & Verify** | **`per_item`** | one verification per entity — **blocked on a list** |
| **Pair builder** | `whole_list` (over child rows) | consumes expanded child rows, not the raw list — so it is reachable only after an Expand |

The pattern: **everything that folds, compares, or reads context takes the list as-is; everything that spends a paid external call per entity is blocked.** That is not a coincidence — the per-item recipes are exactly the ones where an implicit fan-out would have silently multiplied cost, and the gate makes the user look at the fan-out factor before paying it.

**Structured Extract — full spec** (the workflow's "one declared question per column" step, `desired-workflow.md` §2):
- **input:** one or more @-referenced columns.
- **param — the question:** exactly **ONE** question in free text ("what is the total contract amount?"). **One question = one output column**, always 1:1. A batch of questions is a batch of columns, not a multi-answer cell — this is what keeps every column independently sortable, cacheable, and re-runnable.
- **param — output type (required):** `number | date | money | text | entity | list` — and for `list`, an optional **item type** from that same set (§2a). Required, not inferred: the declared type is what makes the column sortable and Formula/Compute-compatible, it is the JSON Schema enforced at the model edge (§3), and for lists it decides which downstream operations are legal.
- **several answers → one list cell, never several rows.** If the question has n answers for a row ("who else participated?"), they land as a typed list in one cell with one citation per item. Rows come only from an explicit Expand (§2a).
- **behavior on absence:** answer not present in the source → **`NotFound` with zero citations**. Never guess, never fill from world knowledge, never answer from the model's priors. An empty cell with a typed status is the correct output. For a list question, "we looked and there are none" is `[]` + `Answered`, which is a different fact from `NotFound`.
- **cite:** every value anchors to the exact source locator (§9) — API field path for connector data, page + offset/bbox for documents.

**Row-producing** (emit rows, not cells — onto this sheet or a **derived sheet**, §2a; a produced row with no parent input cells is a *generated* row, §16 #7):

| Recipe | exec | Input → Output | Eval metric |
|--------|------|----------------|-------------|
| **Start** | func + LLM router | two fields — the journalist's question + the new column name → router picks a connector (Prozorro / web search / …) or asks for an upload → rows. Router proposes; **the journalist approves before any run** (§4 step 4 gate). | router accuracy (right connector picked), success rate |
| **Connector: Prozorro** | func | search params → rows, **one row per tender LOT** (§16 #3); winner = `award.status='active' → award.suppliers[].identifier.id` where `identifier.scheme='UA-EDR'` (EDRPOU) + `award.value` (§6a) | success rate, stable-ID completeness, provenance |
| **Manual upload** | func | file → normalized row on `@documents` (docling parse; other formats native, OCR only if no text layer, §7) | ingest success, OCR status |
| **Expand** | func | a **list column** → child rows, one per element, each carrying `parent_row_id` + `ordinal` (= its index in the source array, which brings its citation along) and a `row_link`. Two modes (§2a): `inline` (children between the original rows, same sheet, `depth=1`, no dedup) or `new_table` (children become a new sheet, optional `dedup_by`). **Explicit, user-invoked only** — it is the sole way to unblock a `per_item` recipe (§16 #2). | fan-out completeness, key integrity, dedup correctness |
| **Pair builder** | func | child rows grouped by lot key → **pair rows on a derived Pairs sheet**: unique unordered pairs within each lot, then aggregated across all selected lots (co-bid count, win split). Lot with <2 bidders → `NotApplicable`, not a missing row. | pair completeness vs manual, count correctness |
| **Generate / Seed rows** | agent | prompt/params (+ optional seed col) → **new rows**, first col filled, `origin='generated'` | list precision/recall, dup rate, hallucinated-entity rate |

> **Priority note.** `Generate / Seed rows` sits **after the connectors** and is **not on the pilot critical path**: in the procurement case competitors derive deterministically from Prozorro co-bids (Unnest → Pair builder), so no LLM row generation is needed for the demo. Build it when connectors and the derived-sheet path are green.

**Cross-row** (→ `cross_row_result`, not a grid column, §8):

| Recipe | exec | Input → Output | Eval metric |
|--------|------|----------------|-------------|
| **Cross-row connect** | func→agent | explicit row/col set → signal + evidence. **Scope narrowed (rev. 3):** non-pair, no-row-shape signals only — anything with a stable pair grain goes to a Pairs sheet instead (§2a) | signal precision/recall, false-positive rate |

**Engine feature (not a recipe) — Dead-end lock:** when a cell reaches a status that cannot support downstream work, downstream cells are auto-set and **never enqueued** — the empty result is **negative-cached** on `cache_key` so identical inputs don't re-hit a paid external provider. Only force-refresh (§4 step 6) overrides.

- **Fires on ANY required input, not all.** A recipe with one missing *required* input (§3) is guaranteed `InsufficientData` — running it only burns the LLM call. Waiting for *every* input to be empty before locking is the expensive bug; `any(required)` is the rule.
- **Optional inputs never lock.** A missing optional input degrades the run, it doesn't cancel it.
- **The propagated status matches its cause** (§5): terminal-empty (`NotFound` / `InsufficientData` / `SourceUnavailable`) → downstream `InsufficientData`; `NotApplicable` → downstream **`NotApplicable`**.
- **Human-resolvable terminals do not lock:** `ConflictingEvidence` / `Error` / `NeedsReview` (and `Answered`) propagate nothing.

This is the cost-safety complement to the wavefront gate (§4 step 5): the wavefront decides *when inputs are ready*, dead-end lock decides *when a ready-but-empty input means "don't bother spending."*

**Deferred:**
- **Merge** (func→agent, one column/explicit row set → canonical row + merged-to links, eval: wrong-merge rate / missed-duplicate rate) — same shape as Cross-row connect, deferred to keep P0 to additive signals only; row-lifecycle mutation (canonical pick + `merged_into_row_id`) waits until Cross-row connect is proven. *Note:* Expand's `dedup_by` is **not** Merge — it dedups at insert time on a deterministic key, before any row exists, and never mutates an existing row's lifecycle.
- **Recursive / Expand walk** (agent, bounded depth) — follow chains (owner → owner's owner, beneficiary drill-down). New depth-iteration pattern; deferred to keep P0 recipes single-pass (rough-outline §5: "one pass"). The YouControl person-mode above is **fixed 2-step, not this**: person → their companies, one hop, no iteration.
- **Fixed row-class system** — a base taxonomy of row types for law-focused sheets (§16 #8). P0 rows are untyped; run-subset is manual queue selection only.

**Language — Ukrainian only for the pilot** (Maryna's decision, 21.07). Interface, recipe names/params, and AI output are Ukrainian. English is at most a post-demo layer, not a P0 requirement. **The Translation recipe is removed from P0 entirely.** Unchanged and non-negotiable: **originals and citations always stay in the source language** (§9) — the quote that `locate()` searches is the original string, never a translation.

---

## 6b. Recipe scope guards

Two recipes in the table above sit one step away from a Deferred feature. The line is drawn here so implementations don't drift across it:

- **YouControl person-mode is 2-step, not a walk.** `person key → companies where that person is founder/director` is a single fixed hop, serving the workflow's `@companies_owned_by_owner` column (`desired-workflow.md` §3). It must not iterate (owner → owner's owner → …); that is the deferred Recursive/Expand walk (§13). **Week-1 risk gate:** if verifying the person-search endpoint (license, quota, field shape — §6a) takes more than one day, move this column to stretch. The pilot workflow survives without it; the address-link and co-bid signals still carry Act 2.
- **Expand is explicit, never automatic.** It runs because the journalist invoked it on a named list column and chose a mode (§2a). No recipe ever turns a list into rows as a side effect of some other operation — that is the invariant §16 #2 protects, and the expansion gate is what enforces it.

---

## 6a. Connector API map (pilot connectors)

Verified against live API docs (week-1 spike still confirms license/quota).

**Prozorro** — public, no auth for read. `func` connector, no LLM on clean structured parts (§7 hybrid).

| Need | Endpoint / path |
|---|---|
| Row feed | `GET /tenders` — sorted by `dateModified`, batch 100 (`limit`), cursor `next_page.offset`; sync-by-modification-date, poll ~5 min |
| Full tender | `GET /tenders/{id}` |
| **Lots** | `tender.lots[]` → `lot.id`, `lot.title`, `lot.value`, `lot.status`. **One lot = one row** (§16 #3). A tender with no `lots[]` yields exactly one row keyed `(tenderID, null)`. |
| Docs | `GET /tenders/{id}/documents` → `url`, `documentType`, `format`, `datePublished` (feeds upload/OCR/Extract) |
| Winner (deterministic, per lot) | `award.status == 'active'` **and** `award.lotID == lot.id` → `award.suppliers[].identifier.id` (+ `legalName`, `address`, `contactPoint`) |
| Bidders (per lot) | `bids[]` filtered by `lotValues[].relatedLot == lot.id` → `bid.tenderers[].identifier` — this is the `@participants` list that Unnest/Explode consumes |
| Amount | `award.value` = `{amount, currency}`; bid via `award.bid_id` |

**Identifier discipline.** `identifier` is `{scheme, id, legalName}`. **`id` is an EDRPOU only when `scheme == 'UA-EDR'`.** Foreign and non-registry bidders carry other schemes; a recipe that assumes every `identifier.id` is an EDRPOU will silently send garbage keys to YouControl. Store the pair `(scheme, id)`, key YouControl lookups on `UA-EDR` only, and set `NotApplicable` (§5) for rows whose bidder is out of registry scope — not `NotFound`.

→ **row = one tender lot** (decision #3 — resolved §16 #3). Winner EDRPOU + amount pulled with zero LLM.

**YouControl / YouScore** — REST JSON, API key (server-side only, §11), **per-module quota/license**.

| Module | Path / note |
|---|---|
| Registry (USR) | `/v1/usr/{EDRPOU}` — legal entity, founders, directors, address, KVED, status |
| Person → companies | person-search endpoint backing the 2-step person mode (§6b) — **existence, license, and quota unverified; week-1 spike, 1-day timebox, else the column moves to stretch** |
| Metered add-ons (separate license each) | sanctions/PEP, court cases, tax debt, beneficiaries, corporate-group affiliation, due-diligence score |

Key = EDRPOU (`scheme='UA-EDR'`). **Having a key ≠ having all modules** (§11) — week-1 spike verifies which modules the license grants + quota before recipes assume them.

Docs: [Prozorro tenders](https://prozorro-api-docs.readthedocs.io/en/master/tendering/basic-actions/tenders.html) · [Prozorro award](https://prozorro-api-docs.readthedocs.io/en/master/standard/award.html) · [YouScore endpoints](https://youscore.com.ua/en/faq/detailed-information-on-endpoints/) · [YouScore swagger](https://api.youscore.com.ua/swagger/index.html)

---

## 7. Document processing — three distinct modes

Do **not** call all of this "RAG." Three different problems:

| Mode | Question | Technique | Failure mode to avoid |
|------|----------|-----------|-----------------------|
| **Retrieve** (RAG) | "what does the doc say about Y?" | embed query → top-k chunks | — (this is Q&A → largely **Deferred**) |
| **Enumerate** | "list **all** mentions of X" | **map-reduce sweep over every chunk** | top-k silently under-counts; recall failure |
| **Structured Extract** | "pull fields into a schema" | hybrid (deterministic ingest + lazy LLM) | eager full-JSON extraction (see below) |

**Enumerate — the important one:**
```
if doc fits context:  single-shot on whole doc  ("list all X, quote + page each")
else:                 MAP each chunk → extract candidates
                      REDUCE → dedup / entity-resolve → cite
```
Every chunk is visited → full recall. 10 pages fits context → single-shot. 300-page court file → sweep. Eval **recall**, not just precision — the miss is the failure.

The Enumerate cell value is a **list** (§16 list-in-cell), so its citation is **per item, not per cell**: `citation_jsonb` is an array aligned to `value_jsonb` (§2), each entry anchoring one enumerated item back to the chunk/page it came from. After REDUCE/dedup, an item merged from several chunks carries all its supporting locators.

**Extraction strategy — hybrid, lazy default (not eager full-JSON):**
- **Ingest time, deterministic, cheap:** API connectors are already structured (Prozorro/YouControl) → store known fields as `jsonb`, no LLM.
- **Accepted P0 upload formats** (`desired-workflow.md` §1 Input B): PDF (text-layer or OCR-ready scan), DOCX/XLSX/PPTX/HTML, images, and **conversation / video / audio transcripts and subtitles** as text. Transcript locators are timecodes (§9). Raw video and image *imagery* is not analyzed in the pilot (§13) — a subtitle file is text, a video file is not.
- **On demand, LLM, lazy:** unstructured text or a new user-requested tag → run an extraction recipe → new column.
- Reject the "extract everything into one predetermined JSON upfront" idea: schemas differ wildly across doc types, it extracts things nobody asked for, and it fights the composable/user-driven model. Also **no separate document DB** — `jsonb` + `pgvector` in Postgres, keep lineage intact.

---

## 8. Agentic — bounded, in P0

Agentic **is** P0. The line is **bounded vs unbounded**, not agentic vs not.

| | P0 (allowed) | Deferred |
|---|---|---|
| scope | fixed input set (one row, or *explicitly selected* rows/cols) | roams everything itself |
| control | human picks the operation + inputs | agent plans + auto-runs steps |
| output | typed, cited, logged, eval'd | freeform synthesis |

**In P0:**
- **Web Search** — tool loop, row-scoped.
- **Match & Verify** — agent loop, row-scoped, fixed tool (YouControl): strategy → call → compare → typed status + evidence.
- **Cross-row connect** — *explicit* operation. User declares the row/column set. Two phases:

```
PHASE 1  CANDIDATE GEN (deterministic, no LLM):
  index rows by shared attributes (phone / email / address / EDRPOU /
  director / owner). Blocking: only pairs sharing a key become candidates.
  Cuts N² down to a handful.

PHASE 2  VERIFY (agentic, per candidate pair):
  agent compares the pair, explores YouControl/web to confirm/deny
  → typed status + per-signal citations.
```
Deterministic narrows; agent judges. Never agent-scans-everything (breaks isolation, blows context, kills citations). Every claimed connection cites the shared attribute **and both source records** — no naked assertions.

Each verified signal writes a **`cross_row_result`** row (§2), *not* a cell in the grid — such a result has no single-row home, and keeping it out of `cell(row_id, column_id)` is what preserves the per-row isolation invariant (§3) for normal recipes. It records its input row/column versions; if an input column is rerun, the signal flags `is_stale` and waits for a user-confirmed re-verify (same "never auto-rerun" rule as §4).

**Rev. 3 — scope split between `cross_row_result` and the Pairs sheet.** Once **Pair builder** + derived sheets (§2a) land, most of what P0 originally routed here has a proper row shape and belongs on a sheet, where the journalist can sort it, score it, cite it, and export it. The split:

| Result | Home | Why |
|---|---|---|
| Repeated co-bidding, win split, shared owner/address **per company pair** | **Pairs sheet** (row = pair) | Stable grain, needs sorting/scoring/export — must be journalist-visible, not buried in a side table |
| One-off explicit signal over an ad-hoc row/col set with no repeating grain | `cross_row_result` | Genuinely has no row shape |

Phase 1 candidate-gen (blocking on shared attributes) is unchanged and is **shared code**: Pair builder uses the same deterministic blocking, then materializes pairs as rows instead of signals. Phase 2 agentic verify then runs as an ordinary cell-producing recipe **on the Pairs sheet** — one pair row, one `row_context`, isolation intact.

**Deferred:** Assistant Plan/Auto (plans the whole investigation, auto-executes multi-step). Trust the core first, autonomy later.
- **Merge** — same shape as Cross-row connect (explicit, user-declared row set, deterministic-candidate → agent-verify), but the outcome changes row lifecycle instead of just adding a signal column: for each confirmed duplicate pair, one row is picked canonical, the other gets `merged_into_row_id` set + `state='merged'` (§5). **User confirms before merge commits** — same Preview gate as any other run (§4 step 4), because unlike a signal column this is not trivially undoable without an explicit unlock. Losing row's existing cells are untouched, just excluded from future enqueue batches (§4 step 5). Schema (`row.state`, `merged_into_row_id`) stays in place now so Cross-row connect's candidate-gen logic is reusable later — only the commit action is deferred.

Every agentic step: one bounded scope, logged, same eval as any recipe.

---

## 9. Provenance / citations

Principle 2 — every claim has an address.

- Store per emitted item: source locator (API field path / URL / page + char offset / timecode) in `citation_jsonb` — an **array** aligned to `value_jsonb` (§2), so list-in-cell / Enumerate results cite each item, not the cell as a whole.
- **Quote → locate anchoring:** model returns a verbatim quote; code string-searches it back in the source to get the offset. **Never trust model-reported page numbers** — verify the quote exists before storing.
- **Anchor in the source language, always.** The quote is captured in the source language even when the cell value is translated or summarized into the UI language (brief §10: originals + citations stay in source language). Translating the value must not break `locate()` — the quote searched is the original-language string, not the AI output.
- **OCR is noisy → fuzzy locate.** For OCR'd docs an exact string match will fail. Normalize (lowercase, collapse whitespace, strip punctuation) then token-window / edit-distance match; store the best offset **plus a `match_confidence`**. Below threshold → don't store a guessed offset; set the cell `NeedsReview`. A wrong-but-confident locator is worse than an honest "couldn't anchor."
- **Ingest via docling, not raw pytesseract.** Docling wraps Tesseract (ukr+rus+eng traineddata kept, §15) as its OCR backend but checks for a text layer first — OCR runs only on pages that actually lack one — and parses PDF/DOCX/XLSX/PPTX/HTML natively (raw pytesseract handles images only; owner brief P0 upload path needs docx/xlsx too). Docling also returns per-element **page + bbox**, a stronger citation locator than char-offset alone on scanned pages.
- Web results store at minimum: URL, title, fetched-at, supporting snippet.
- Chunks stay a technical layer, surfaced only via citation / verification view.

---

## 10. Models / OpenRouter (owner brief §9)

- Model + allowed provider endpoint configured by owner/admin **per recipe** — not a user-facing model switcher for Oksana.
- Per run, log: `model_id`, actual provider endpoint, recipe version, prompt hash (exact model revision if the provider exposes it).
- **Pin models to concrete IDs** — no floating `auto`/`latest`.
- Fallback **off by default**; if needed, only a pre-validated model+provider combo that passed the same eval. **Fallback-produced cells are not cached** (`run.used_fallback=true` → `cache_key` left non-hittable): otherwise a later run with the primary model up would serve a fallback value mislabeled as the primary model's, corrupting provenance. Next run misses cache → primary runs.
- Changing the model in a critical recipe → re-run eval.
- Fast models for simple row tasks; stronger model only for harder synthesis. Exact counts/patterns → code.
- **Embedding models are pinned too.** The same "no floating model" discipline applies to embeddings: `chunk.embed_model_id` (§2) records which model produced each vector. Retrieval compares only same-model vectors; swapping the embedding model is a versioned re-embed, never a silent mixed-vector-space drift.
- Providers: allowlist, no data collection, Zero Data Retention where a compatible endpoint exists. No keys or full payloads in logs.

---

## 11. Security / access / secrets

- Case **private by default**; share only by explicit action. Roles: owner / editor / viewer (reviewer = Stretch).
- Pilot uses **public data only**. If a user accidentally uploads a non-public file, it must **not** be silently sent to an external provider. **Enforced in P0, not deferred:** every document carries `external_ok` (§2) — connector-sourced rows (Prozorro/YouControl API) are inherently public → `true`; manual uploads are `false` until the user explicitly attests the file is public. Any recipe that calls an external provider (LLM / web / YouControl) checks `external_ok` on **every** source document in `row_context` at dispatch; any un-attested source → the run is **blocked** with "needs public attestation," never silently sent. This is the enforcement point for the brief §10 rule; full per-case/per-row private mode stays deferred (tech-stack §3), but the hard rule is met now, not aspirationally.
- **Secrets server-side only.** YouControl key lives behind one controlled server endpoint with rate limits + logging (no secret in logs, client, or repo). Week 1: verify the API contract, fields, license rights, and quota of that specific access — having a key ≠ having all modules.
- **External calls are idempotent across retries.** A worker can crash after incurring a paid/quota'd external call but before writing the cell; Procrastinate then retries → a naive design double-charges YouControl quota. The server-side proxy keeps a short-TTL idempotency cache keyed `(recipe_version, row_id, column_id, call_args_hash)`; an identical retried call reuses the stored response instead of re-hitting the provider. TTL is minutes (crash-retry window), not a data cache.
- Cost cap + caching + Preview gate spend before any full run.

---

## 12. Eval (owner brief §8)

- For each P0 recipe: a small representative real set. Part for tuning/validation, part **frozen held-out** until one final Demo-Day run.
- Cell-level feedback: verdict (correct/partial/incorrect/cannot-judge) + relevance 0–3 + error type (wrong entity / missed evidence / unsupported claim / wrong classification / citation mismatch / incomplete / source problem / other) + optional correct value.
- Metrics are **per component** (§6 table) — 90% is not a universal target.
- **`NotApplicable` cells leave the denominator; `InsufficientData` cells do not.** A structurally void question (§5) is not a recall miss and must not be scored as one — counting direct-award lots as failed pair detections would understate the recipe by exactly the share of non-competitive lots in the sample. Missing data *is* a miss and stays counted.
- **Human labels persist and are restorable.** The workflow's Correct / Error / Needs-review marks (`desired-workflow.md` §6) write `cell_feedback` (§2) and survive the session: reopening the case restores both the labels and the review progress, and the same rows feed recipe tuning. Review state is data, not UI state.
- LLM-judge may scale open-answer checks **only after** measuring its agreement with Oksana; versioned prompt, audited, never replaces deterministic metrics.
- **Ground truth is a single-human dependency — name a backup.** Acceptance rests on Oksana across weeks 3-6; if she's unavailable, gates 3/5 can't be met. Brief §8 already invites a second domain annotator "за можливості" — make that a *named* second judge for a slice of critical examples (also gives human-agreement numbers), and front-load Oksana's critical build sessions into weeks 1-3 rather than back-loading them.

---

## 13. Deferred (must not block the pilot)

Q&A / large text synthesis as a required layer · Assistant Plan/Auto · **Merge** (row-lifecycle mutation, §6/§8) · **Recursive/Expand walk** (bounded-depth owner/beneficiary chains, §6/§6b) · **fixed row-class taxonomy** for law-focused sheets (§16 #8) · **Translation recipe + English UI layer** (rev. 3 — pilot is Ukrainian-only, §6) · nested cases / case-as-row · auto source refresh + diff · multimedia — raw video/image *imagery* is not analyzed in the pilot, though video/audio **transcripts and subtitles** are an accepted P0 upload format (§7) · handwriting OCR / bad photos · sensitive or unpublished material · CMS / monitoring / alerts / auto-publish · open source.

---

## 14. Build order (4 weeks + buffer, gates)

**rev. 4 (this pass) — compressed from 6 weeks to 4: tighter external deadline.** The two calendar weeks this removes are not deleted — they move to an explicit **1.5-week buffer** (§14a) held for whatever the compressed run surfaces, not pre-assigned to new scope. Content is unchanged from rev. 3; weeks 2+3 and weeks 5+6 of the original plan each merge into one week below. `Target date` is a plan fact (this section); the *live* `Gate status` (PENDING/MET) stays in `TASKS.md` per `CLAUDE.md §3` — don't duplicate that column here.

| Week | Target date | Goal | Gate |
|------|------|------|------|
| 1 | 2026-07-22 – 2026-07-28 | Product+tech vertical: fix the case entity/role/period, **confirm lot-grain fields + failure states on real data** (grain itself is locked, §16 #3), land migration `0002` (§2). Spike **Prozorro** (lots, per-lot bids/awards — official API/feed, not fragile scraping) + **YouControl** (incl. the 1-day person-endpoint timebox, §6b). Grid skeleton (rows, cols, sort/filter, source view). **Structured Extract** through Preview→run→column→Result. First eval rubric + dependency register. | One real lot row completes the whole core loop, no manual data substitution. |
| 2 | 2026-07-29 – 2026-08-04 | *(merges original weeks 2+3)* Real volume + recipe engine: connectors build tens→hundreds of rows. Stabilize Web Search + column dependencies. Provenance, partial failures, retry/caching, versioned runs. Add Summarize + Classify/Score; recipes accept derived columns as inputs. Typed statuses (all eight, §5), citation opening, feedback controls. dev/held-out split per recipe. | Web Search produces a verifiable column on a representative subset, **and** Oksana builds a ≥2-column recipe sequence herself. |
| 3 | 2026-08-05 – 2026-08-11 | Useful tender analysis (workflow Act 2): **Expand `@participants` (`new_table` + dedup) → Companies sheet**, then **Pair builder → Pairs sheet** (§2a) — deterministic comparisons find repeated companies/attributes/patterns. Explicit cross-row op emits any remaining no-row-shape signal with evidence. Rerun Score with pair signals. Tune recipes on Oksana's marks. Result + Google Sheets export on full volume, **all sheets**. | First Result is already useful in the pilot investigation. |
| 4 | 2026-08-12 – 2026-08-18 | *(merges original weeks 5+6)* Hardening + acceptance rehearsal, held-out frozen mid-week: fix citation mismatch / source errors / stale deps; verify permissions, secrets, cost, recovery; full run without dev help. Then Demo Day, same week: freeze version, one final run on frozen held-out (no further tuning), full real-case run, saved Result + export, honest metrics/active hours/typical errors+limits, backup dataset/run for external failure, post-pilot decision. | Oksana does the core loop solo and critical recipes pass agreed eval thresholds mid-week; end-to-end real-case run stands on its own at Demo Day (2026-08-18). |

### 14a. Buffer — 2026-08-19 – 2026-08-28 (~1.5 weeks)

Intentionally **not** pre-planned into tasks. This is where the two weeks recovered by the compression go — not deleted, held back. Use:
- **First**, to absorb slip: whichever week-1–4 gate above is not `MET` on schedule finishes here before anything else starts.
- **Then**, spare-capacity items in the old rev. 3 order: Custom Prompt recipe, court/declaration sources, other P0 hardening — never new Deferred-list scope (§13).
- The coordinator decides at the start of this window whether it's absorbing slip or is genuinely spare; either way it is not a second Demo Day — the committed demo is the Week 4 gate.

---

## 15. Tech stack

| Layer | Pick |
|---|---|
| Database | Postgres (+ `pgvector`, `jsonb`) |
| Backend language | Python |
| Backend framework | FastAPI |
| Frontend | React + TypeScript, Vite |
| Grid UI | TanStack Table + virtual scroll |
| DB access | SQLAlchemy 2.0 (async) + raw SQL for CTEs |
| Job queue | Procrastinate (Postgres `SKIP LOCKED`-based) |
| Realtime transport | SSE |
| LLM access | openai SDK → OpenRouter |
| Doc parsing / OCR | **docling** (Tesseract backend for OCR, ukr+rus+eng) | multi-format (PDF/DOCX/XLSX/PPTX/HTML/img), text-layer check → OCR only pages that lack one, bbox-level locators feed §9 citation anchoring. Pin docling + model versions (§10 discipline). |
| File storage | Cloudflare R2 |
| Auth | fastapi-users |
| Hosting | Railway |
| Desktop wrap (future) | Tauri |

Full rationale + alternatives considered: `tech-stack-decision.md`.

**Unresolved (production, not pilot-blocking):** private mode / external-call gating for non-public data; local-vs-cloud deployment split. See `tech-stack-decision.md` §3.

---

## 16. Open decisions — resolved

1. **Doc ops P0 set — resolved:** Enumerate (sweep) + Structured Extract only. RAG retrieval (Q&A) stays out of P0 — consistent with §13, which already defers Q&A/large-text-synthesis as a required layer.
2. **Multi-valued results — RESOLVED (rev. 3), full model:** *a recipe returning n values per row writes **one typed list cell**; a list cell may feed any recipe that consumes it whole; any recipe needing **one row per value** is **blocked** until the user explicitly **expands** the list.* Expansion has two modes: **`inline`** (child rows inserted between the originals in the same sheet, parent cells rendered spanning but stored once, no dedup) and **`new_table`** (children become a new sheet, optional `dedup_by`). Full spec in §2a; `consumes` declaration per recipe in §6; the check runs at edge-add next to the cycle check (§4 step 2).
   - **Why a block rather than an automatic fan-out.** The row set must never change as a side effect of a column running: otherwise adding one column silently multiplies the sheet, re-enqueues every existing column over the new rows, mixes grains under the journalist's sort, and — because a recipe only sees its own `row_context` (§3) — the fan-out could not deduplicate even in principle. Every mainstream spreadsheet lands in the same place: Excel's dynamic arrays raise `#SPILL!` rather than overwrite, and Power Query's expand is an explicit recorded step, never implicit. The block turns an invisible modeling mistake into a visible choice with two labeled exits.
   - **Why two modes rather than one.** They differ in what they optimize and neither dominates. `inline` keeps evidence beside its source, which is what per-row inspection wants; it is positional, so it structurally cannot dedup and pays external-API cost per duplicate. `new_table` gives a uniform grain, no duplicate rendering, and is the **only** mode that can dedup — ~600 participant entries → ~180 company rows, and 600 paid YouControl calls → 180. Forcing one mode would either cost 3× on the pilot's main enrichment or exile every child row to a separate tab even when the journalist just wants to glance at it.
   - **Consequence, accepted:** dedup means a child has several parents, so lineage is two mechanisms — `row.parent_row_id` as the 1:1 **tree** edge (grain, ordering, rendering) and `row_link` as the N-ary **graph** (evidence, traceability). Every child writes both, so downstream code has one path to walk.
   - **What is still rejected, unchanged:** implicit explosion. No recipe turns a list into rows as a side effect. This is the invariant; the two modes are only ways for the *user* to ask.
3. **Logical row v0 — RESOLVED, CHANGED in rev. 3: row = one tender LOT.** Fixed at kick-off, superseding the rev. 2 tender-package grain. Row = **one Prozorro tender lot**, keyed `(tenderID, lotID)`; a tender with no `lots[]` yields one row with `lotID = null`. Not per-award, per-participant, per-document, or per-chunk.
   - **Why the change:** the lot is where the money, the winner, and the bidder set actually live. Award, `award.value`, and the bid list are all lot-scoped in the Prozorro model (§6a) — at tender grain a multi-lot procurement forces winner and amount into parallel lists, and every downstream Score, Compare, and Formula column then has to re-index those lists by hand. That is per-lot logic smeared across every recipe instead of resolved once in the grain. Rev. 2 already anticipated exactly this and named it as the week-1 escalation path; the workflow doc and the catalog both fixed it at kick-off, so it is fixed here now rather than re-litigated in week 1.
   - **What it costs:** a multi-lot tender occupies several rows. Accepted — tender-level facts stay addressable via `row.provenance_jsonb.tenderID`, and a tender-level view is an Aggregate/Fold over the lot rows grouped by `tenderID`, which is an ordinary recipe (§6), not new plumbing.
   - **What attaches to a lot row:** that lot's bidders and bids as list-in-cell, its award, and the package's documents via `document.row_id`.
   - Cross-row connect (§8), Match & Verify, and the derived Companies/Pairs sheets stay keyed on the company identifier, so lot grain does not change their scoping.
   - Schema impact: `row.provenance_jsonb` keyed by `(tenderID, lotID)` — see the §2 migration note (`0002`).
4. **First P0 recipe — resolved:** no fixed pick. Team (3-4 devs) builds the P0 recipe candidates in parallel; week 1 gate is satisfied by whichever completes Preview→run→column→Result first. Precondition: the recipe interface (§3) must be stable before parallel work starts, so implementers aren't blocked on shared plumbing.
5. **Queue — resolved:** **Procrastinate** (Postgres `LISTEN/NOTIFY` + `SKIP LOCKED`) is the single queue — not a hand-rolled `cell.status` poller (§4). At estimated ceiling (~200-300 rows × ~50 columns/case ≈ 10-15k cells/case) this is comfortably within range; Redis/Celery only on an order-of-magnitude jump. The real subtlety is **not** throughput but *ordering*: parallel workers need DAG readiness enforced in data (wavefront-gated enqueue, §4 step 5), because Procrastinate has no built-in dependency ordering. Frontend (TanStack virtual scroll) also comfortable at this row count; the frontend risk is update *rate*, handled by batched flushes + reconcile-on-reconnect (§4 step 7).
6. **Cross-row result home — resolved:** signals land in a dedicated `cross_row_result` table (§2/§8), outside the column DAG — a pairwise result has no single-row home, and this keeps the per-row isolation invariant (§3) intact. Merge (which mutates row lifecycle) stays Deferred; its schema (`row.state`, `merged_into_row_id`, `terminal_scope`, `Rejected`) sits dormant.
7. **Can a recipe create rows? — resolved: yes.** A **row-producing** recipe shape (§6) emits rows, alongside cell-producing and cross-row shapes — same `exec()`/`cite`/`eval` contract (§3). Connectors already produce rows; **Generate / Seed rows** (agent) does it from a prompt (e.g. "find top-10 Ukrainian universities → 10 rows"). A produced row with **no parent input cells** is a *generated* row: `origin='generated'` + `generated_by_run_id` (§2) so it's visibly distinct from connector/upload rows and its provenance traces to the run. **This does not reopen decision #2** — #2 rejects *automatic per-item explosion* of a list-in-cell into child rows (implicit, breaks the isolation model); row-producing recipes are *explicit, user-invoked* operations whose product **is** rows. Per-item verification of a list still follows the #2 rule (explicit op over selected items), not auto-explosion.
8. **Row class / tag — deferred, partially superseded:** P0 rows stay **untyped within a sheet**, and "run rows of same class" is still served by **manual queue selection**. Rev. 3 note: **derived sheets (§2a) absorb most of the pressure** this decision was holding back — "run all rows of type *company*" is now "run the column on the Companies sheet," because grain is carried by the sheet rather than by a per-row tag. The full fixed row-class taxonomy stays **deferred** (§13); reassess only if a single sheet turns out to need heterogeneous row types.
9. **`NotApplicable` status — resolved (rev. 3): add it, as the 8th `cell_status`.** The alternative, skip-with-reason, was rejected: a skipped cell has no status to sort, filter, or roll up, so the journalist cannot tell "no competitors exist for this direct award" from "we never ran it," and `column.status` (§5) could not roll it up. Silently mapping it to `InsufficientData` was rejected outright — the catalog's exact requirement is that "nothing to check here" and "not enough data" stay distinguishable, and eval depends on it (`NotApplicable` leaves the denominator; `InsufficientData` counts as a recall miss). Emitters in P0: **Pair builder** (lot with <2 bidders), **Connector: YouControl** (bidder whose `identifier.scheme != 'UA-EDR'`, §6a). Lock behavior is defined in §5 — it propagates as itself, not as `InsufficientData`. Schema: added by migration `0002` (§2).
10. **Where pair results live — resolved (rev. 3): a derived Pairs sheet, with `cross_row_result` narrowed.** Pairs must be journalist-visible — sortable, scoreable, citable, exportable — and a side table outside the grid gives none of that. Pairs therefore land on a **derived sheet** (§2a, the `new_table` shape) that re-enters the core: same recipes, same sorting, same citations, same export, no parallel code path. `cross_row_result` (§8) survives strictly for one-off signals that have **no row shape**. This does not weaken row isolation: a pair row is a real row with its own `row_context`, and the cross-lot aggregation happens inside the Pair-builder recipe, not inside downstream ones. Pair rows are inherently multi-parent (two members), so they use `row_link` only — `parent_row_id` is null on a pair row, since a pair has no single tree parent (§16 #2).
11. **Pilot UI language — resolved (Maryna, 21.07): Ukrainian only.** Interface, recipe surface, and AI output are Ukrainian for the pilot; English is at most a post-demo layer. The **Translation recipe is dropped from P0** (§6, §13) — it was carrying real risk (a translated value breaking citation `locate()`) for zero pilot value. Unchanged: **originals and citations always stay in the source language** (§9).
